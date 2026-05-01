"""
langgraph_pipeline/state.py — Graph State Schema

Defines the TypedDict that flows through every node in the
Hierarchical LangGraph Stateful Orchestrator.

Author: darkphoenix2208
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


class GraphState(TypedDict, total=False):
    """Shared state that is read/written by every node in the graph.

    Fields
    ------
    transaction_id : str
        Unique identifier for the investigation target.
    scenario : str
        Human-readable description of the suspicious activity.
    initial_signals : dict
        Aggregated signals from upstream ML models (risk scores, flags).
    route : str
        Triage decision — one of "fiat", "crypto", or "both".
    fiat_evidence : dict
        Evidence gathered by the fiat investigator node.
    crypto_evidence : dict
        Evidence gathered by the crypto investigator node.
    rag_threat_intel : dict
        Threat intelligence from the vector-search RAG node.
    human_approved : bool
        Whether a human-in-the-loop has approved synthesis.
    final_verdict : dict
        The synthesised JSON risk report produced by the CRO node.
    messages : list
        Append-only reasoning trace for full auditability.
    """

    transaction_id: str
    scenario: str
    initial_signals: Dict[str, Any]
    route: Literal["fiat", "crypto", "both"]
    fiat_evidence: Dict[str, Any]
    crypto_evidence: Dict[str, Any]
    rag_threat_intel: Dict[str, Any]
    human_approved: bool
    final_verdict: Dict[str, Any]
    messages: List[Dict[str, Any]]
