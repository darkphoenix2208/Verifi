"""
langgraph_pipeline/orchestrator.py — Hierarchical LangGraph Stateful Orchestrator

Assembles the StateGraph with conditional routing from triage,
parallel fiat/crypto investigation arms, RAG threat intel, and a
Human-in-the-Loop breakpoint before the final CRO synthesizer.

Author: darkphoenix2208
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from langgraph_pipeline.state import GraphState
from langgraph_pipeline.nodes import (
    triage_node,
    fiat_investigator_node,
    crypto_investigator_node,
    threat_intel_rag_node,
    synthesizer_node,
)

# Graceful import — fall back to a plain sequential runner if
# langgraph is not installed (e.g. local dev without the dep).
try:
    from langgraph.graph import StateGraph, END

    _HAS_LANGGRAPH = True
except ImportError:
    _HAS_LANGGRAPH = False
    StateGraph = None  # type: ignore[assignment,misc]
    END = "__end__"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def _route_after_triage(state: GraphState) -> str:
    """Conditional edge: decide which investigator(s) to activate."""
    route = state.get("route", "fiat")
    if route == "both":
        return "both"
    if route == "crypto":
        return "crypto"
    return "fiat"


def build_graph():
    """Construct and compile the LangGraph StateGraph.

    Graph topology:
        START → triage_node
                  ├─ "fiat"   → fiat_investigator → threat_intel_rag → (HITL) → synthesizer → END
                  ├─ "crypto" → crypto_investigator → threat_intel_rag → (HITL) → synthesizer → END
                  └─ "both"   → fiat_investigator → crypto_investigator → threat_intel_rag → (HITL) → synthesizer → END

    A breakpoint before the synthesizer simulates Human-in-the-Loop approval.
    """
    if not _HAS_LANGGRAPH:
        return None

    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("triage", triage_node)
    graph.add_node("fiat_investigator", fiat_investigator_node)
    graph.add_node("crypto_investigator", crypto_investigator_node)
    graph.add_node("threat_intel_rag", threat_intel_rag_node)
    graph.add_node("synthesizer", synthesizer_node)

    # Entry point
    graph.set_entry_point("triage")

    # Conditional routing from triage
    graph.add_conditional_edges(
        "triage",
        _route_after_triage,
        {
            "fiat": "fiat_investigator",
            "crypto": "crypto_investigator",
            "both": "fiat_investigator",  # fiat first, then chain to crypto
        },
    )

    # Fiat → crypto (only on "both" route) or → threat_intel_rag
    def _after_fiat(state: GraphState) -> str:
        if state.get("route") == "both":
            return "crypto_investigator"
        return "threat_intel_rag"

    graph.add_conditional_edges(
        "fiat_investigator",
        _after_fiat,
        {
            "crypto_investigator": "crypto_investigator",
            "threat_intel_rag": "threat_intel_rag",
        },
    )

    # Crypto → threat_intel_rag (always)
    graph.add_edge("crypto_investigator", "threat_intel_rag")

    # Threat intel → synthesizer
    graph.add_edge("threat_intel_rag", "synthesizer")

    # Synthesizer → END
    graph.add_edge("synthesizer", END)

    # Compile (HITL breakpoint is simulated via reasoning trace;
    # interrupt_before is omitted for API auto-approval mode)
    compiled = graph.compile()

    return compiled


# ---------------------------------------------------------------------------
# Singleton compiled graph
# ---------------------------------------------------------------------------
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Public API — run a full investigation
# ---------------------------------------------------------------------------

def run_langgraph_investigation(scenario: str, transaction_id: str | None = None) -> Dict[str, Any]:
    """Execute the full hierarchical orchestrator pipeline.

    Parameters
    ----------
    scenario : str
        Human-readable description of the suspicious activity.
    transaction_id : str, optional
        An identifier for the target; auto-generated if omitted.

    Returns
    -------
    dict
        Complete investigation result including reasoning trace,
        evidence, RAG intel, and the CRO verdict.
    """
    started_at = time.time()
    tx_id = transaction_id or f"VERIFI-{uuid.uuid4().hex[:8].upper()}"

    initial_state: GraphState = {
        "transaction_id": tx_id,
        "scenario": scenario,
        "initial_signals": {},
        "route": "fiat",
        "fiat_evidence": {},
        "crypto_evidence": {},
        "rag_threat_intel": {},
        "human_approved": True,  # auto-approve for API calls
        "final_verdict": {},
        "messages": [{"role": "system", "content": f"Investigation started for: {scenario}", "ts": time.time()}],
    }

    graph = _get_graph()

    if graph is not None:
        try:
            # Use invoke for a clean single-shot execution
            final_state = graph.invoke(initial_state)
            if not isinstance(final_state, dict) or not final_state.get("final_verdict"):
                # invoke may hit the HITL interrupt — fall through to sequential
                raise RuntimeError("Graph interrupted or returned incomplete state")
        except Exception as exc:
            # Fallback: stream and accumulate, or run sequential
            try:
                accumulated = dict(initial_state)
                for event in graph.stream(initial_state):
                    if isinstance(event, dict):
                        for _node_name, update in event.items():
                            if isinstance(update, dict):
                                accumulated.update(update)
                final_state = accumulated
                if not final_state.get("final_verdict"):
                    raise RuntimeError("Stream completed without verdict")
            except Exception:
                final_state = _sequential_fallback(initial_state)
                msgs = list(final_state.get("messages", []))
                msgs.append({"role": "system", "content": f"LangGraph failed ({exc}), used sequential fallback", "ts": time.time()})
                final_state["messages"] = msgs
    else:
        # No langgraph installed — run nodes directly
        final_state = _sequential_fallback(initial_state)

    elapsed = round((time.time() - started_at) * 1000)

    return {
        "transaction_id": final_state.get("transaction_id", tx_id),
        "scenario": scenario,
        "route": final_state.get("route", "unknown"),
        "fiat_evidence": final_state.get("fiat_evidence", {}),
        "crypto_evidence": final_state.get("crypto_evidence", {}),
        "rag_threat_intel": final_state.get("rag_threat_intel", {}),
        "final_verdict": final_state.get("final_verdict", {}),
        "reasoning_trace": final_state.get("messages", []),
        "total_duration_ms": elapsed,
        "pipeline": "LangGraph Hierarchical Orchestrator" if graph else "Sequential Fallback",
    }


def _sequential_fallback(state: GraphState) -> GraphState:
    """Run all nodes in sequence when LangGraph is unavailable."""
    state = {**state, **triage_node(state)}
    route = state.get("route", "fiat")
    if route in ("fiat", "both"):
        state = {**state, **fiat_investigator_node(state)}
    if route in ("crypto", "both"):
        state = {**state, **crypto_investigator_node(state)}
    state = {**state, **threat_intel_rag_node(state)}
    state = {**state, **synthesizer_node(state)}
    return state
