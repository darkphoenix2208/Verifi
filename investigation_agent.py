"""
investigation_agent.py — Multi-Tool Agentic AI Investigation Engine

ReAct-style agent that autonomously queries all ML modules in the Verifi
platform, chains together evidence, and generates a structured threat
investigation report.

Requires GOOGLE_API_KEY for live Gemini inference; falls back to a
synthetic rule-based investigation if the key is absent.

Author: darkphoenix2208
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Tool functions — each wraps an existing ML engine
# ---------------------------------------------------------------------------

def tool_query_transaction_risk(amount: float = 500.0, category: str = "shopping_net") -> Dict[str, Any]:
    """Query the ensemble fraud detection model for a transaction risk assessment."""
    try:
        from api import bridge
        tx_data = {
            "trans_date_trans_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "amt": amount,
            "category": category,
            "merchant": "fraud_investigation_probe",
            "city": "New York",
            "state": "NY",
            "lat": 40.7128, "long": -74.0060,
            "merch_lat": 40.7580, "merch_long": -73.9855,
            "city_pop": 8336817,
            "job": "analyst",
            "dob": "1990-01-15",
            "gender": "M",
            "cc_num": "0000000000000000",
            "trans_num": "probe_investigation",
            "zip": "10001",
        }
        result = bridge.tx_scorer.score_single(tx_data)
        return {
            "tool": "Transaction Fraud Model (VotingClassifier Ensemble)",
            "risk_score": result.get("risk_score", 0),
            "decision": result.get("decision", "UNKNOWN"),
            "reason": result.get("reason", ""),
            "top_features": result.get("top_features", []),
            "model_type": "VotingClassifier (RF + GBM + LR)",
        }
    except Exception as exc:
        return {"tool": "Transaction Fraud Model", "error": str(exc)}


def tool_query_behavior_anomaly(
    clicks: float = 200, time_between: float = 2, session_len: float = 50,
    failed_logins: float = 5
) -> Dict[str, Any]:
    """Query the GMM behavior anomaly detector for a session risk score."""
    try:
        from behavior_engine import behavior_detector
        result = behavior_detector.score_session({
            "clicks_last_hour": clicks,
            "avg_time_between_clicks": time_between,
            "session_length": session_len,
            "num_failed_logins": failed_logins,
            "device_change_rate": 4,
            "location_variance": 5,
            "browser_jump_freq": 3,
            "actions_per_session": 180,
        })
        return {
            "tool": "Behavior Anomaly Detector (GMM)",
            "anomaly_score": result.get("anomaly_score", 0),
            "is_anomaly": result.get("is_anomaly", False),
            "risk_level": result.get("risk_level", "UNKNOWN"),
            "threshold": result.get("threshold", 0),
            "model_type": "GaussianMixture (2-component)",
        }
    except Exception as exc:
        return {"tool": "Behavior Anomaly Detector", "error": str(exc)}


def tool_query_employee_risk() -> Dict[str, Any]:
    """Query the employee insider threat model for current risk assessments."""
    try:
        from api import bridge
        items = bridge.emp_scorer.get_risk_items()
        high_risk = [i for i in items if i.get("risk_level") == "HIGH"]
        return {
            "tool": "Employee Insider Threat Model (RandomForest)",
            "total_employees_scored": len(items),
            "high_risk_count": len(high_risk),
            "high_risk_employees": high_risk[:3],
            "model_type": "RandomForestRegressor",
        }
    except Exception as exc:
        return {"tool": "Employee Insider Threat Model", "error": str(exc)}


def tool_assess_crypto_threat(value_eth: float = 250.0, gas: int = 21000, gas_price_gwei: float = 50.0) -> Dict[str, Any]:
    """Query the crypto IsolationForest anomaly scorer for DeFi threat assessment."""
    try:
        from crypto_engine import _crypto_scorer
        is_anomaly = _crypto_scorer.is_anomaly(value_eth, gas, gas_price_gwei)
        anomaly_score = _crypto_scorer.score(value_eth, gas, gas_price_gwei)
        return {
            "tool": "Crypto Anomaly Scorer (IsolationForest)",
            "value_eth": value_eth,
            "is_anomaly": is_anomaly,
            "anomaly_score": round(anomaly_score, 4),
            "model_type": "IsolationForest (150 estimators)",
        }
    except Exception as exc:
        return {"tool": "Crypto Anomaly Scorer", "error": str(exc)}


# ---------------------------------------------------------------------------
# Agent — orchestrates tools and generates investigation report
# ---------------------------------------------------------------------------

TOOL_REGISTRY = [
    ("Transaction Risk Analysis", tool_query_transaction_risk),
    ("Behavior Anomaly Detection", tool_query_behavior_anomaly),
    ("Employee Insider Threat Scan", tool_query_employee_risk),
    ("Crypto/DeFi Threat Assessment", tool_assess_crypto_threat),
]


def run_investigation(scenario: str) -> Dict[str, Any]:
    """
    Run a full multi-tool investigation.

    1. Executes all 4 ML tools to gather evidence
    2. Attempts Gemini-based reasoning over the evidence
    3. Falls back to rule-based report if Gemini is unavailable

    Returns a structured investigation report.
    """
    started_at = time.time()
    reasoning_steps: List[Dict[str, Any]] = []
    evidence_collected: List[Dict[str, Any]] = []

    # Step 1: Execute all tools
    for tool_name, tool_fn in TOOL_REGISTRY:
        step_start = time.time()
        try:
            result = tool_fn()
            evidence_collected.append(result)
            reasoning_steps.append({
                "step": len(reasoning_steps) + 1,
                "action": f"Querying {tool_name}",
                "tool": tool_name,
                "status": "error" if "error" in result else "success",
                "duration_ms": round((time.time() - step_start) * 1000),
                "observation": _summarize_evidence(result),
            })
        except Exception as exc:
            reasoning_steps.append({
                "step": len(reasoning_steps) + 1,
                "action": f"Querying {tool_name}",
                "tool": tool_name,
                "status": "error",
                "duration_ms": round((time.time() - step_start) * 1000),
                "observation": f"Tool failed: {exc}",
            })

    # Step 2: Generate report (Gemini or fallback)
    report, risk_assessment = _generate_report(scenario, evidence_collected, reasoning_steps)

    reasoning_steps.append({
        "step": len(reasoning_steps) + 1,
        "action": "Generating Investigation Report",
        "tool": "Gemini 2.0 Flash" if os.environ.get("GOOGLE_API_KEY") else "Rule-Based Engine",
        "status": "success",
        "duration_ms": round((time.time() - started_at) * 1000),
        "observation": "Final report compiled from all evidence sources.",
    })

    return {
        "scenario": scenario,
        "reasoning_steps": reasoning_steps,
        "evidence_collected": evidence_collected,
        "final_report": report,
        "risk_assessment": risk_assessment,
        "recommended_actions": _get_recommendations(evidence_collected),
        "total_duration_ms": round((time.time() - started_at) * 1000),
        "agent_model": "Gemini 2.0 Flash (ReAct)" if os.environ.get("GOOGLE_API_KEY") else "Rule-Based Fallback",
    }


def _summarize_evidence(result: Dict[str, Any]) -> str:
    """One-line summary of a tool result for the reasoning chain."""
    if "error" in result:
        return f"Error: {result['error']}"
    tool = result.get("tool", "Unknown")
    if "risk_score" in result:
        return f"{tool}: risk_score={result['risk_score']}, decision={result.get('decision', 'N/A')}"
    if "anomaly_score" in result:
        return f"{tool}: anomaly_score={result['anomaly_score']}, is_anomaly={result.get('is_anomaly')}"
    if "high_risk_count" in result:
        return f"{tool}: {result['high_risk_count']} high-risk employees out of {result['total_employees_scored']}"
    return f"{tool}: completed"


def _generate_report(
    scenario: str,
    evidence: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
) -> tuple:
    """Generate the final report. Tries Gemini first, falls back to rule-based."""
    api_key = os.environ.get("GOOGLE_API_KEY", "")

    if api_key:
        try:
            from langchain.chat_models import init_chat_model
            from langchain_core.messages import HumanMessage

            model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
            evidence_text = json.dumps(evidence, indent=2, default=str)
            steps_text = json.dumps(steps, indent=2, default=str)

            prompt = (
                "You are an expert fraud investigation AI agent for the Verifi Security Platform.\n\n"
                f"## Investigation Scenario\n{scenario}\n\n"
                f"## Evidence Collected from ML Pipelines\n```json\n{evidence_text}\n```\n\n"
                f"## Agent Reasoning Steps\n```json\n{steps_text}\n```\n\n"
                "Based on the above evidence, generate:\n"
                "1. A comprehensive investigation report (3-4 paragraphs)\n"
                "2. A one-word risk assessment: CRITICAL, HIGH, MEDIUM, or LOW\n\n"
                "Format your response as:\n"
                "RISK_LEVEL: [level]\n\n"
                "REPORT:\n[your detailed report]"
            )

            response = model.invoke([HumanMessage(content=prompt)])
            content = response.content

            # Parse risk level
            risk_level = "MEDIUM"
            if "RISK_LEVEL:" in content:
                risk_line = content.split("RISK_LEVEL:")[1].split("\n")[0].strip()
                for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                    if level in risk_line.upper():
                        risk_level = level
                        break

            # Parse report
            report = content
            if "REPORT:" in content:
                report = content.split("REPORT:")[1].strip()

            return report, risk_level
        except Exception as exc:
            print(f"[InvestigationAgent] Gemini failed: {exc}. Using rule-based fallback.")

    # Rule-based fallback
    return _rule_based_report(scenario, evidence)


def _rule_based_report(scenario: str, evidence: List[Dict[str, Any]]) -> tuple:
    """Generate a structured report from evidence without LLM."""
    risk_signals = 0
    findings = []

    for e in evidence:
        if e.get("risk_score", 0) > 0.6:
            risk_signals += 2
            findings.append(f"Transaction fraud model flagged elevated risk (score: {e['risk_score']})")
        if e.get("is_anomaly"):
            risk_signals += 2
            findings.append(f"{e.get('tool', 'Anomaly detector')} flagged anomalous behavior")
        if e.get("high_risk_count", 0) > 0:
            risk_signals += 1
            findings.append(f"{e['high_risk_count']} employee(s) flagged as high insider threat risk")

    if risk_signals >= 4:
        risk_level = "CRITICAL"
    elif risk_signals >= 2:
        risk_level = "HIGH"
    elif risk_signals >= 1:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    if not findings:
        findings = ["No significant risk signals detected across all ML modules."]

    report = (
        f"## Automated Investigation Report\n\n"
        f"**Scenario:** {scenario}\n\n"
        f"### Key Findings\n"
        + "\n".join(f"- {f}" for f in findings) +
        f"\n\n### Risk Assessment: {risk_level}\n\n"
        f"This investigation queried {len(evidence)} ML models across the Verifi platform. "
        f"A total of {risk_signals} risk signal(s) were detected. "
        f"{'Immediate action is recommended.' if risk_level in ('CRITICAL', 'HIGH') else 'Continued monitoring is advised.'}"
    )

    return report, risk_level


def _get_recommendations(evidence: List[Dict[str, Any]]) -> List[str]:
    """Generate recommended actions based on evidence."""
    actions = []
    for e in evidence:
        if e.get("decision") == "FLAG":
            actions.append("Block/review flagged transactions immediately")
        if e.get("is_anomaly") and "Behavior" in e.get("tool", ""):
            actions.append("Enforce step-up authentication for anomalous sessions")
        if e.get("high_risk_count", 0) > 0:
            actions.append("Audit high-risk employee access permissions")
        if e.get("is_anomaly") and "Crypto" in e.get("tool", ""):
            actions.append("Freeze associated DeFi wallet interactions")

    if not actions:
        actions = ["Continue standard monitoring", "No immediate action required"]

    actions.append("File Suspicious Activity Report (SAR) if risk is HIGH or CRITICAL")
    return list(dict.fromkeys(actions))  # deduplicate preserving order
