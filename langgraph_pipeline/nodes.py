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


# ── 4. Threat Intelligence RAG Node ────────────────────────────────────
# Mock vector-search against a dictionary of historical attack vectors.
_HISTORICAL_ATTACK_VECTORS = {
    "tornado_cash": {
        "pattern": "mixer_interaction",
        "severity": "CRITICAL",
        "description": "Funds routed through Tornado Cash — known OFAC-sanctioned mixer.",
        "ttps": ["T1027 — Obfuscated Fund Flows", "T1071 — Mixer Protocol Abuse"],
    },
    "flash_loan_attack": {
        "pattern": "flash_loan",
        "severity": "CRITICAL",
        "description": "Flash-loan exploit detected: borrow→manipulate→repay in single block.",
        "ttps": ["T1190 — DeFi Protocol Exploitation", "T1499 — Price Oracle Manipulation"],
    },
    "account_takeover": {
        "pattern": "credential_stuffing",
        "severity": "HIGH",
        "description": "Rapid failed-login burst followed by high-value transfer from new device.",
        "ttps": ["T1110 — Brute Force", "T1078 — Valid Account Compromise"],
    },
    "insider_data_exfil": {
        "pattern": "insider_threat",
        "severity": "HIGH",
        "description": "Employee accessed sensitive records after hours with privilege escalation.",
        "ttps": ["T1078.003 — Insider Privilege Abuse", "T1048 — Data Exfiltration"],
    },
    "pig_butchering_scam": {
        "pattern": "social_engineering",
        "severity": "MEDIUM",
        "description": "Long-duration social engineering leading to repeated high-value transfers.",
        "ttps": ["T1566 — Phishing / Social Engineering", "T1565 — Victim Grooming"],
    },
}


def threat_intel_rag_node(state: GraphState) -> dict:
    """Compare current threat signatures against historical attack vectors.

    This is a mock vector-search: we keyword-match the scenario and
    ML signals against the known attack dictionary.
    """
    msgs = list(state.get("messages", []))
    scenario = state.get("scenario", "").lower()
    signals = state.get("initial_signals", {})
    fiat_ev = state.get("fiat_evidence", {})
    crypto_ev = state.get("crypto_evidence", {})

    matched: list = []

    # Build a searchable blob from all available context
    context_blob = " ".join([
        scenario,
        json.dumps(signals, default=str),
        json.dumps(fiat_ev, default=str),
        json.dumps(crypto_ev, default=str),
    ]).lower()

    try:
        for vector_id, vector in _HISTORICAL_ATTACK_VECTORS.items():
            # Simple keyword overlap scoring (mock embedding similarity)
            keywords = vector_id.split("_") + vector["pattern"].split("_")
            score = sum(1 for kw in keywords if kw in context_blob)
            if score >= 1:
                matched.append({
                    "vector_id": vector_id,
                    "match_score": score,
                    "severity": vector["severity"],
                    "description": vector["description"],
                    "ttps": vector["ttps"],
                })

        # Sort by match score descending
        matched.sort(key=lambda m: m["match_score"], reverse=True)
    except Exception as exc:
        msgs.append(_msg("system", f"RAG threat intel failed: {exc}"))

    intel = {
        "source": "threat_intel_rag",
        "matched_vectors": matched[:3],  # top 3
        "total_searched": len(_HISTORICAL_ATTACK_VECTORS),
        "coverage": f"{len(matched)}/{len(_HISTORICAL_ATTACK_VECTORS)} vectors matched",
    }

    msgs.append(_msg("threat_intel", f"RAG matched {len(matched)} historical attack vector(s)"))
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
