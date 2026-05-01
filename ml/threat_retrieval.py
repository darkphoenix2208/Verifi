"""
ml/threat_retrieval.py — 2-Stage Hybrid RAG with RRF & Reranking

Stage 1: Parallel BM25 (sparse) + cosine similarity (dense) retrieval
          fused via Reciprocal Rank Fusion (RRF).
Stage 2: Cross-Encoder reranking of top-K fused results.

Author: darkphoenix2208
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import numpy as np

# ---------------------------------------------------------------------------
# Threat intelligence corpus (expandable)
# ---------------------------------------------------------------------------
THREAT_CORPUS: List[Dict[str, Any]] = [
    {"id": "TC-001", "title": "Tornado Cash Mixer Interaction",
     "text": "Funds routed through Tornado Cash OFAC-sanctioned mixer protocol for obfuscation of transaction origin and destination addresses on Ethereum mainnet.",
     "severity": "CRITICAL", "ttps": ["T1027", "T1071"]},
    {"id": "TC-002", "title": "Flash Loan Oracle Manipulation",
     "text": "Flash-loan exploit targeting price oracles on decentralized exchanges. Attacker borrows, manipulates price, profits, and repays within a single block.",
     "severity": "CRITICAL", "ttps": ["T1190", "T1499"]},
    {"id": "TC-003", "title": "Credential Stuffing Account Takeover",
     "text": "Rapid credential stuffing attack with multiple failed logins followed by successful access and high-value wire transfer from compromised banking account.",
     "severity": "HIGH", "ttps": ["T1110", "T1078"]},
    {"id": "TC-004", "title": "Insider Data Exfiltration",
     "text": "Employee accessed sensitive financial records outside business hours with escalated privileges and exported customer PII and transaction data.",
     "severity": "HIGH", "ttps": ["T1078.003", "T1048"]},
    {"id": "TC-005", "title": "Pig Butchering Romance Scam",
     "text": "Long-duration social engineering scam grooming victim over weeks before directing repeated high-value cryptocurrency transfers to attacker wallets.",
     "severity": "MEDIUM", "ttps": ["T1566", "T1565"]},
    {"id": "TC-006", "title": "SIM Swap Fraud",
     "text": "Attacker ported victim phone number via SIM swap to intercept 2FA codes, then initiated unauthorized wire transfers from mobile banking application.",
     "severity": "HIGH", "ttps": ["T1111", "T1078"]},
    {"id": "TC-007", "title": "Smurfing / Structuring",
     "text": "Multiple sub-threshold deposits structured below $10,000 reporting limit to evade BSA/AML currency transaction reporting requirements.",
     "severity": "HIGH", "ttps": ["T1036", "T1070"]},
    {"id": "TC-008", "title": "Rug Pull Token Exit Scam",
     "text": "Token creator deployed smart contract with hidden mint function, inflated token supply, drained liquidity pool, and abandoned the project.",
     "severity": "CRITICAL", "ttps": ["T1195", "T1499"]},
    {"id": "TC-009", "title": "Business Email Compromise",
     "text": "Spoofed executive email requesting urgent wire transfer to fraudulent account. Targeted accounts payable department with convincing impersonation.",
     "severity": "HIGH", "ttps": ["T1566.001", "T1534"]},
    {"id": "TC-010", "title": "Unlimited Token Approval Exploit",
     "text": "Malicious dApp requested unlimited ERC-20 token approval allowing attacker smart contract to drain entire wallet balance at any time.",
     "severity": "CRITICAL", "ttps": ["T1190", "T1059"]},
]

_corpus_texts = [d["text"] for d in THREAT_CORPUS]


# ---------------------------------------------------------------------------
# Stage 1a: BM25 Sparse Retrieval
# ---------------------------------------------------------------------------
_bm25 = None


def _get_bm25():
    global _bm25
    if _bm25 is not None:
        return _bm25
    try:
        from rank_bm25 import BM25Okapi
        tokenized = [doc.lower().split() for doc in _corpus_texts]
        _bm25 = BM25Okapi(tokenized)
    except ImportError:
        print("[RAG] rank_bm25 not installed. BM25 sparse retrieval disabled.")
    return _bm25


def _bm25_retrieve(query: str, top_k: int = 10) -> List[tuple]:
    """Return (index, score) tuples sorted by BM25 score."""
    bm25 = _get_bm25()
    if bm25 is None:
        return []
    tokens = query.lower().split()
    scores = bm25.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


# ---------------------------------------------------------------------------
# Stage 1b: Dense Semantic Retrieval (sklearn cosine similarity)
# ---------------------------------------------------------------------------
_dense_embeddings: Optional[np.ndarray] = None
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
        print("[RAG] Dense embedder loaded: all-MiniLM-L6-v2")
    except Exception as exc:
        print(f"[RAG] SentenceTransformer load failed ({exc}). Dense retrieval disabled.")
    return _embedder


def _get_corpus_embeddings() -> Optional[np.ndarray]:
    global _dense_embeddings
    if _dense_embeddings is not None:
        return _dense_embeddings
    embedder = _get_embedder()
    if embedder is None:
        return None
    _dense_embeddings = embedder.encode(_corpus_texts, convert_to_numpy=True, normalize_embeddings=True)
    return _dense_embeddings


def _dense_retrieve(query: str, top_k: int = 10) -> List[tuple]:
    """Return (index, score) tuples sorted by cosine similarity."""
    embedder = _get_embedder()
    corpus_emb = _get_corpus_embeddings()
    if embedder is None or corpus_emb is None:
        return []
    q_emb = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    sims = (corpus_emb @ q_emb.T).flatten()
    ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)
    return ranked[:top_k]


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def _reciprocal_rank_fusion(
    *ranked_lists: List[tuple], k: int = 60
) -> List[tuple]:
    """Fuse multiple ranked lists via RRF. Returns (index, rrf_score) sorted."""
    scores: Dict[int, float] = {}
    for ranked in ranked_lists:
        for rank, (idx, _score) in enumerate(ranked):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused


# ---------------------------------------------------------------------------
# Stage 2: Cross-Encoder Reranking
# ---------------------------------------------------------------------------
_reranker = None

RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_reranker():
    global _reranker
    if _reranker is not None:
        return _reranker
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANKER_MODEL)
        print(f"[RAG] Reranker loaded: {RERANKER_MODEL}")
    except Exception as exc:
        print(f"[RAG] Reranker load failed ({exc}). Using RRF scores only.")
    return _reranker


def _rerank(query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
    """Rerank candidates using cross-encoder. Falls back to existing order."""
    reranker = _get_reranker()
    if reranker is None or not candidates:
        return candidates[:top_k]
    try:
        pairs = [(query, c["text"]) for c in candidates]
        scores = reranker.predict(pairs)
        for i, s in enumerate(scores):
            candidates[i]["rerank_score"] = float(s)
        candidates.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    except Exception as exc:
        print(f"[RAG] Reranking failed: {exc}")
    return candidates[:top_k]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def hybrid_retrieve(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Run the full 2-stage hybrid RAG pipeline.

    Stage 1: BM25 + Dense retrieval → RRF fusion
    Stage 2: Cross-encoder reranking

    Returns structured results with scores and metadata.
    """
    # Stage 1: Parallel retrieval
    bm25_results = _bm25_retrieve(query, top_k=10)
    dense_results = _dense_retrieve(query, top_k=10)

    # Fallback if both retrievers fail
    if not bm25_results and not dense_results:
        return _keyword_fallback(query, top_k)

    # RRF Fusion
    fused = _reciprocal_rank_fusion(bm25_results, dense_results)

    # Build candidate list
    candidates = []
    for idx, rrf_score in fused[:top_k * 2]:  # over-retrieve for reranking
        entry = dict(THREAT_CORPUS[idx])
        entry["rrf_score"] = round(rrf_score, 5)
        candidates.append(entry)

    # Stage 2: Reranking
    reranked = _rerank(query, candidates, top_k=top_k)

    return {
        "query": query,
        "results": reranked,
        "total_corpus": len(THREAT_CORPUS),
        "bm25_hits": len(bm25_results),
        "dense_hits": len(dense_results),
        "pipeline": "BM25 + Dense → RRF → CrossEncoder Reranking",
    }


def _keyword_fallback(query: str, top_k: int) -> Dict[str, Any]:
    """Simple keyword matching when both retrievers are unavailable."""
    query_lower = query.lower()
    scored = []
    for entry in THREAT_CORPUS:
        keywords = set(re.findall(r'\w+', entry["text"].lower()))
        query_tokens = set(re.findall(r'\w+', query_lower))
        overlap = len(keywords & query_tokens)
        if overlap > 0:
            scored.append((entry, overlap))
    scored.sort(key=lambda x: x[1], reverse=True)
    results = []
    for entry, score in scored[:top_k]:
        r = dict(entry)
        r["rrf_score"] = score / max(len(set(re.findall(r'\w+', query_lower))), 1)
        results.append(r)
    return {
        "query": query,
        "results": results,
        "total_corpus": len(THREAT_CORPUS),
        "bm25_hits": 0,
        "dense_hits": 0,
        "pipeline": "keyword_fallback",
    }
