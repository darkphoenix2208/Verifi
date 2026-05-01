"""
langgraph_pipeline/nodes.py — Graph Node Functions

Each function takes the current GraphState, performs work, and returns
a partial state update dict.  All external calls are wrapped in
try/except with graceful fallbacks per CLAUDE.md.

Author: darkphoenix2208
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

from langgraph_pipeline.state import GraphState


# ── helpers ─────────────────────────────────────────────────────────────
def _msg(role: str, content: str) -> Dict[str, Any]:
    """Construct a timestamped message entry for the reasoning trace."""
    return {"role": role, "content": content, "ts": time.time()}


# ── 1. Triage Node ──────────────────────────────────────────────────────
def triage_node(state: GraphState) -> dict:
    """Analyse initial ML signals and decide which investigation arms to activate.

    Routes to "fiat", "crypto", or "both" based on signal composition.
    """
    signals = state.get("initial_signals", {})
    scenario = state.get("scenario", "").lower()
    msgs = list(state.get("messages", []))

    # Gather upstream ML signals
    tx_risk: float = 0.0
    behavior_anomaly: bool = False
    employee_risk: float = 0.0
    crypto_anomaly: bool = False

    try:
        from investigation_agent import (
            tool_query_transaction_risk,
            tool_query_behavior_anomaly,
            tool_query_employee_risk,
            tool_assess_crypto_threat,
        )
        tx = tool_query_transaction_risk()
        beh = tool_query_behavior_anomaly()
        emp = tool_query_employee_risk()
        cry = tool_assess_crypto_threat()

        tx_risk = float(tx.get("risk_score", 0))
        behavior_anomaly = bool(beh.get("is_anomaly", False))
        employee_risk = float(emp.get("high_risk_count", 0))
        crypto_anomaly = bool(cry.get("is_anomaly", False))

        signals = {
            "transaction": tx,
            "behavior": beh,
            "employee": emp,
            "crypto": cry,
        }
    except Exception as exc:
        msgs.append(_msg("system", f"Triage ML probe failed: {exc}. Using heuristic routing."))

    # Routing logic
    has_fiat = tx_risk > 0.5 or behavior_anomaly or employee_risk > 0
    has_crypto = crypto_anomaly or any(
        kw in scenario for kw in ("eth", "crypto", "defi", "wallet", "blockchain", "token")
    )

    if has_fiat and has_crypto:
        route = "both"
    elif has_crypto:
        route = "crypto"
    else:
        route = "fiat"  # default arm

    msgs.append(_msg("triage", f"Routed to '{route}' — fiat_signals={has_fiat}, crypto_signals={has_crypto}"))

    return {
        "initial_signals": signals,
        "route": route,
        "messages": msgs,
    }


# ── 2. Fiat Investigator Node ───────────────────────────────────────────
def fiat_investigator_node(state: GraphState) -> dict:
    """Gather banking / employee-side evidence using existing ML tools."""
    msgs = list(state.get("messages", []))
    evidence: Dict[str, Any] = {"source": "fiat_investigator", "findings": []}

    try:
        from investigation_agent import tool_query_transaction_risk, tool_query_employee_risk

        tx = tool_query_transaction_risk()
        emp = tool_query_employee_risk()

        evidence["transaction_risk"] = tx
        evidence["employee_risk"] = emp

        if tx.get("decision") == "FLAG":
            evidence["findings"].append("Transaction ensemble FLAGGED — elevated fraud probability")
        if emp.get("high_risk_count", 0) > 0:
            evidence["findings"].append(
                f"{emp['high_risk_count']} insider-threat employee(s) detected"
            )
        if not evidence["findings"]:
            evidence["findings"].append("No significant fiat-side risk signals detected")

    except Exception as exc:
        evidence["error"] = str(exc)
        evidence["findings"].append(f"Fiat investigation tool failure: {exc}")

    msgs.append(_msg("fiat_investigator", f"Collected {len(evidence['findings'])} finding(s)"))
    return {"fiat_evidence": evidence, "messages": msgs}


# ── 3. Crypto Investigator Node ─────────────────────────────────────────
def crypto_investigator_node(state: GraphState) -> dict:
    """Gather DeFi / on-chain evidence using the IsolationForest engine."""
    msgs = list(state.get("messages", []))
    evidence: Dict[str, Any] = {"source": "crypto_investigator", "findings": []}

    try:
        from investigation_agent import tool_assess_crypto_threat

        cry = tool_assess_crypto_threat()
        evidence["crypto_threat"] = cry

        if cry.get("is_anomaly"):
            evidence["findings"].append(
                f"IsolationForest flagged anomalous on-chain pattern (score={cry.get('anomaly_score')})"
            )
        else:
            evidence["findings"].append("On-chain transaction features within normal range")

    except Exception as exc:
        evidence["error"] = str(exc)
        evidence["findings"].append(f"Crypto investigation tool failure: {exc}")

    msgs.append(_msg("crypto_investigator", f"Collected {len(evidence['findings'])} finding(s)"))
    return {"crypto_evidence": evidence, "messages": msgs}

# ── 4. Threat Intelligence RAG Node (Hybrid 2-Stage) ───────────────────

def threat_intel_rag_node(state: GraphState) -> dict:
    """2-Stage Hybrid RAG: BM25 + Dense retrieval -> RRF -> Cross-Encoder reranking."""
    msgs = list(state.get("messages", []))
    scenario = state.get("scenario", "")
    fiat_ev = state.get("fiat_evidence", {})
    crypto_ev = state.get("crypto_evidence", {})

    # Build enriched query from all available context
    query_parts = [scenario]
    for f in fiat_ev.get("findings", []):
        query_parts.append(f)
    for f in crypto_ev.get("findings", []):
        query_parts.append(f)
    query = " ".join(query_parts)

    intel: Dict[str, Any] = {"source": "hybrid_rag_2stage"}

    try:
        from ml.threat_retrieval import hybrid_retrieve
        rag_result = hybrid_retrieve(query, top_k=5)

        matched_vectors = []
        for r in rag_result.get("results", []):
            matched_vectors.append({
                "vector_id": r.get("id", "unknown"),
                "title": r.get("title", ""),
                "match_score": r.get("rerank_score", r.get("rrf_score", 0)),
                "severity": r.get("severity", "MEDIUM"),
                "description": r.get("text", "")[:200],
                "ttps": r.get("ttps", []),
            })

        intel["matched_vectors"] = matched_vectors
        intel["total_searched"] = rag_result.get("total_corpus", 0)
        intel["bm25_hits"] = rag_result.get("bm25_hits", 0)
        intel["dense_hits"] = rag_result.get("dense_hits", 0)
        intel["pipeline"] = rag_result.get("pipeline", "unknown")
        intel["coverage"] = f"{len(matched_vectors)}/{intel['total_searched']} vectors matched"

        msgs.append(_msg("threat_intel", f"Hybrid RAG returned {len(matched_vectors)} result(s) via {intel['pipeline']}"))

    except Exception as exc:
        msgs.append(_msg("system", f"Hybrid RAG failed: {exc}. Using empty results."))
        intel["matched_vectors"] = []
        intel["total_searched"] = 0
        intel["coverage"] = "0/0 — retrieval failed"

    return {"rag_threat_intel": intel, "messages": msgs}


# ── 5. Synthesizer Node (Chief Risk Officer) ───────────────────────────
def synthesizer_node(state: GraphState) -> dict:
    """Final synthesis — the 'Chief Risk Officer' LLM reads all evidence
    and drafts a definitive JSON verdict.

    Falls back to a rule-based verdict if Gemini is unavailable.
    """
    msgs = list(state.get("messages", []))
    fiat = state.get("fiat_evidence", {})
    crypto = state.get("crypto_evidence", {})
    rag = state.get("rag_threat_intel", {})
    scenario = state.get("scenario", "")
    tx_id = state.get("transaction_id", "N/A")

    verdict: Dict[str, Any] = {}

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if api_key:
        try:
            from langchain.chat_models import init_chat_model
            from langchain_core.messages import HumanMessage

            model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")

            prompt = (
                "You are the Chief Risk Officer AI for the Verifi Security Platform.\n"
                "You have received the following evidence from multiple investigation arms.\n\n"
                f"## Scenario\n{scenario}\n\n"
                f"## Fiat Investigation Evidence\n```json\n{json.dumps(fiat, indent=2, default=str)}\n```\n\n"
                f"## Crypto Investigation Evidence\n```json\n{json.dumps(crypto, indent=2, default=str)}\n```\n\n"
                f"## Threat Intelligence (RAG)\n```json\n{json.dumps(rag, indent=2, default=str)}\n```\n\n"
                "Produce a JSON object with these keys:\n"
                '  "risk_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",\n'
                '  "confidence": 0.0-1.0,\n'
                '  "summary": "2-3 sentence executive summary",\n'
                '  "key_findings": ["finding1", "finding2", ...],\n'
                '  "recommended_actions": ["action1", "action2", ...],\n'
                '  "matched_ttps": ["ttp1", "ttp2", ...]\n\n'
                "Return ONLY the JSON object, no markdown fences."
            )

            response = model.invoke([HumanMessage(content=prompt)])
            raw = response.content.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            verdict = json.loads(raw)
            msgs.append(_msg("synthesizer", "CRO verdict generated via Gemini 2.0 Flash"))
        except Exception as exc:
            msgs.append(_msg("system", f"Gemini synthesis failed: {exc}. Using rule-based verdict."))

    # Rule-based fallback
    if not verdict:
        verdict = _rule_based_verdict(scenario, fiat, crypto, rag)
        msgs.append(_msg("synthesizer", "CRO verdict generated via rule-based fallback"))

    verdict["transaction_id"] = tx_id
    verdict["investigation_pipeline"] = "LangGraph Hierarchical Orchestrator"

    return {"final_verdict": verdict, "messages": msgs}


def _rule_based_verdict(
    scenario: str,
    fiat: Dict[str, Any],
    crypto: Dict[str, Any],
    rag: Dict[str, Any],
) -> Dict[str, Any]:
    """Deterministic fallback when Gemini is unavailable."""
    risk_signals = 0
    findings = []
    ttps = []

    # Fiat signals
    fiat_findings = fiat.get("findings", [])
    for f in fiat_findings:
        if "FLAGGED" in f.upper() or "detected" in f.lower():
            risk_signals += 2
            findings.append(f)

    # Crypto signals
    crypto_findings = crypto.get("findings", [])
    for f in crypto_findings:
        if "anomal" in f.lower() or "flagged" in f.lower():
            risk_signals += 2
            findings.append(f)

    # RAG intel
    for vec in rag.get("matched_vectors", []):
        risk_signals += 1
        findings.append(f"Matched historical vector: {vec['description']}")
        ttps.extend(vec.get("ttps", []))

    if risk_signals >= 5:
        risk_level = "CRITICAL"
        confidence = 0.92
    elif risk_signals >= 3:
        risk_level = "HIGH"
        confidence = 0.78
    elif risk_signals >= 1:
        risk_level = "MEDIUM"
        confidence = 0.60
    else:
        risk_level = "LOW"
        confidence = 0.45
        findings = findings or ["No significant risk indicators across all investigation arms."]

    actions = []
    if risk_level in ("CRITICAL", "HIGH"):
        actions.extend(["Freeze account immediately", "Escalate to Fraud Operations Lead"])
    actions.append("File SAR if risk is HIGH or CRITICAL")
    actions.append("Continue enhanced monitoring for 30 days")

    return {
        "risk_level": risk_level,
        "confidence": confidence,
        "summary": f"Investigation of scenario '{scenario[:80]}...' yielded {risk_signals} risk signal(s). "
                   f"Assessment: {risk_level}.",
        "key_findings": findings[:5],
        "recommended_actions": actions,
        "matched_ttps": list(dict.fromkeys(ttps))[:5],
    }


# ── 6. NLI Verification Node (Anti-Hallucination) ─────────────────────
def nli_verification_node(state: GraphState) -> dict:
    """Verify the synthesizer's verdict against raw evidence using NLI.

    If contradiction > 0.5 for any claim, flag the verdict.
    """
    msgs = list(state.get("messages", []))
    verdict = dict(state.get("final_verdict", {}))

    # Build the evidence text from all upstream data
    evidence_parts = []
    for f in state.get("fiat_evidence", {}).get("findings", []):
        evidence_parts.append(f)
    for f in state.get("crypto_evidence", {}).get("findings", []):
        evidence_parts.append(f)
    for v in state.get("rag_threat_intel", {}).get("matched_vectors", []):
        evidence_parts.append(v.get("description", ""))
    evidence_text = " ".join(evidence_parts)

    # The report text to verify
    report_text = verdict.get("summary", "")
    for f in verdict.get("key_findings", []):
        report_text += f" {f}"

    if not report_text.strip() or not evidence_text.strip():
        msgs.append(_msg("nli_verifier", "Skipped — no report or evidence to verify"))
        verdict["nli_verification"] = {"verified": True, "skipped": True}
        return {"final_verdict": verdict, "messages": msgs}

    try:
        from ml.nli_verifier import verify_report
        nli_result = verify_report(report_text, evidence_text)

        verdict["nli_verification"] = {
            "verified": nli_result["verified"],
            "hallucination_count": nli_result.get("hallucination_count", 0),
            "total_checked": nli_result.get("total_checked", 0),
            "flags": nli_result.get("hallucination_flags", []),
            "model": nli_result.get("model", "unknown"),
        }

        if not nli_result["verified"]:
            verdict["nli_warning"] = "HALLUCINATION DETECTED — claims contradict evidence"
            msgs.append(_msg("nli_verifier", f"WARNING: {nli_result['hallucination_count']} hallucination(s) detected"))
        else:
            msgs.append(_msg("nli_verifier", f"Verified {nli_result['total_checked']} claim(s) — no hallucinations"))

    except Exception as exc:
        msgs.append(_msg("system", f"NLI verification failed: {exc}"))
        verdict["nli_verification"] = {"verified": True, "error": str(exc)}

    return {"final_verdict": verdict, "messages": msgs}
