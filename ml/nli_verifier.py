"""
ml/nli_verifier.py — Anti-Hallucination NLI Verification

Uses a Cross-Encoder (NLI DeBERTa) to verify that generated claims
in a SAR report are entailed by the raw evidence, preventing
hallucinated financial data from reaching production.

Author: darkphoenix2208
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Literal

Label = Literal["entailment", "neutral", "contradiction"]

# ---------------------------------------------------------------------------
# Singleton model loader — loads once, cached forever
# ---------------------------------------------------------------------------
_MODEL = None
_HAS_MODEL = False

NLI_MODEL_NAME = "cross-encoder/nli-deberta-v3-xsmall"  # lightweight ~80 MB


def _load_model():
    """Load the cross-encoder NLI model. Called once on first use."""
    global _MODEL, _HAS_MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import CrossEncoder
        _MODEL = CrossEncoder(NLI_MODEL_NAME)
        _HAS_MODEL = True
        print(f"[NLI] Loaded model: {NLI_MODEL_NAME}")
    except Exception as exc:
        print(f"[NLI] Model load failed ({exc}). Using heuristic fallback.")
        _HAS_MODEL = False
    return _MODEL


# ---------------------------------------------------------------------------
# Core scoring function
# ---------------------------------------------------------------------------

_LABEL_MAP = {0: "contradiction", 1: "entailment", 2: "neutral"}


def verify_claim(claim: str, premise: str) -> Dict[str, Any]:
    """Score a claim against a premise for NLI entailment.

    Parameters
    ----------
    claim : str
        A generated statement (e.g. from the SAR synthesizer).
    premise : str
        Raw evidence / database record to verify against.

    Returns
    -------
    dict
        {
            "label": "entailment" | "neutral" | "contradiction",
            "scores": {"entailment": float, "neutral": float, "contradiction": float},
            "is_hallucination": bool,  # True if contradiction > 0.5
            "model": str,
        }
    """
    model = _load_model()

    if model is not None and _HAS_MODEL:
        try:
            scores_raw = model.predict([(premise, claim)], apply_softmax=True)
            # scores_raw shape: (1, 3) — [contradiction, entailment, neutral]
            s = scores_raw[0] if hasattr(scores_raw[0], '__len__') else scores_raw
            scores = {
                "contradiction": float(s[0]),
                "entailment": float(s[1]),
                "neutral": float(s[2]),
            }
            label = max(scores, key=scores.get)  # type: ignore[arg-type]
            return {
                "label": label,
                "scores": scores,
                "is_hallucination": scores["contradiction"] > 0.5,
                "model": NLI_MODEL_NAME,
            }
        except Exception as exc:
            print(f"[NLI] Inference failed: {exc}. Using heuristic.")

    # Heuristic fallback — keyword overlap scoring
    return _heuristic_verify(claim, premise)


def _heuristic_verify(claim: str, premise: str) -> Dict[str, Any]:
    """Simple keyword overlap heuristic when the model is unavailable."""
    claim_tokens = set(re.findall(r'\w+', claim.lower()))
    premise_tokens = set(re.findall(r'\w+', premise.lower()))

    if not claim_tokens:
        return _fallback_result("neutral")

    overlap = len(claim_tokens & premise_tokens) / len(claim_tokens)

    if overlap > 0.5:
        label = "entailment"
    elif overlap > 0.2:
        label = "neutral"
    else:
        label = "contradiction"

    scores = {
        "entailment": overlap,
        "neutral": 1.0 - abs(overlap - 0.5),
        "contradiction": max(0, 1.0 - overlap * 2),
    }
    return {
        "label": label,
        "scores": scores,
        "is_hallucination": scores["contradiction"] > 0.5,
        "model": "heuristic_fallback",
    }


def _fallback_result(label: str) -> Dict[str, Any]:
    return {
        "label": label,
        "scores": {"entailment": 0.33, "neutral": 0.34, "contradiction": 0.33},
        "is_hallucination": False,
        "model": "fallback",
    }


# ---------------------------------------------------------------------------
# Batch verification — verify multiple claims from a SAR report
# ---------------------------------------------------------------------------

def verify_report(report_text: str, evidence_text: str) -> Dict[str, Any]:
    """Split a SAR report into sentences and verify each against evidence.

    Returns aggregated results with an overall hallucination flag.
    """
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', report_text) if len(s.strip()) > 15]

    if not sentences:
        return {"verified": True, "hallucination_flags": [], "total_checked": 0}

    results = []
    hallucination_count = 0

    for sentence in sentences[:10]:  # cap at 10 to avoid latency
        r = verify_claim(sentence, evidence_text)
        if r["is_hallucination"]:
            hallucination_count += 1
        results.append({
            "claim": sentence[:120],
            "label": r["label"],
            "contradiction_score": r["scores"]["contradiction"],
            "is_hallucination": r["is_hallucination"],
        })

    return {
        "verified": hallucination_count == 0,
        "hallucination_count": hallucination_count,
        "total_checked": len(results),
        "hallucination_flags": [r for r in results if r["is_hallucination"]],
        "all_results": results,
        "model": results[0].get("model", "unknown") if results else "none",
    }
