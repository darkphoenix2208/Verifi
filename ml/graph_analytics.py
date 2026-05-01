"""
ml/graph_analytics.py — Transaction Graph Machine Learning

Builds a directed transaction graph using NetworkX and computes
PageRank (Eigenvector Centrality) to identify potential laundering
hubs and anomalous high-centrality nodes.

Author: darkphoenix2208
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List

try:
    import networkx as nx
    _HAS_NX = True
except ImportError:
    _HAS_NX = False
    print("[GraphML] networkx not installed. Graph analytics disabled.")


# ---------------------------------------------------------------------------
# Synthetic transaction graph generator
# ---------------------------------------------------------------------------

def _build_sample_graph() -> "nx.DiGraph":
    """Build a realistic synthetic transaction graph for demonstration."""
    G = nx.DiGraph()
    rng = random.Random(42)

    # Normal users
    users = [f"USER_{i:04d}" for i in range(1, 51)]
    # Wallets / accounts
    wallets = [f"WALLET_{i:03d}" for i in range(1, 31)]
    # Exchanges
    exchanges = ["Binance", "Coinbase", "Kraken", "Uniswap_Pool"]
    # Suspicious hubs (will have high centrality)
    hubs = ["MIXER_001", "SHELL_CORP_A", "DARKNET_RECV"]

    all_nodes = users + wallets + exchanges + hubs
    for node in all_nodes:
        G.add_node(node, type="hub" if node in hubs else "normal")

    # Normal transactions
    for _ in range(200):
        src = rng.choice(users)
        dst = rng.choice(wallets + exchanges)
        G.add_edge(src, dst,
                   value=round(rng.uniform(50, 5000), 2),
                   tx_count=rng.randint(1, 10))

    # Hub-connected laundering pattern (high fan-in/fan-out)
    for hub in hubs:
        # Many inputs from different users
        for _ in range(25):
            src = rng.choice(users)
            G.add_edge(src, hub,
                       value=round(rng.uniform(1000, 50000), 2),
                       tx_count=rng.randint(5, 20))
        # Fan-out to wallets
        for _ in range(20):
            dst = rng.choice(wallets + exchanges)
            G.add_edge(hub, dst,
                       value=round(rng.uniform(500, 30000), 2),
                       tx_count=rng.randint(3, 15))

    return G


# ---------------------------------------------------------------------------
# Graph analytics
# ---------------------------------------------------------------------------

_cached_graph: "nx.DiGraph | None" = None


def _get_graph() -> "nx.DiGraph":
    global _cached_graph
    if _cached_graph is None:
        if not _HAS_NX:
            raise RuntimeError("networkx not installed")
        _cached_graph = _build_sample_graph()
    return _cached_graph


def compute_pagerank_anomalies(top_k: int = 10) -> Dict[str, Any]:
    """Compute PageRank on the transaction graph and return top anomalous nodes.

    High PageRank in a financial transaction graph indicates nodes that
    receive value from many sources — potential laundering hubs.
    """
    if not _HAS_NX:
        return _fallback_result()

    try:
        G = _get_graph()
        start = time.time()

        # PageRank (weighted by transaction value)
        weights = {}
        for u, v, data in G.edges(data=True):
            weights[(u, v)] = data.get("value", 1.0)
        nx.set_edge_attributes(G, weights, "weight")

        pr = nx.pagerank(G, weight="weight", alpha=0.85, max_iter=100)

        # Eigenvector centrality (for comparison)
        try:
            eigen = nx.eigenvector_centrality_numpy(G, weight="weight")
        except Exception:
            eigen = {}

        # Betweenness centrality
        try:
            between = nx.betweenness_centrality(G, weight="weight", k=min(50, len(G)))
        except Exception:
            between = {}

        elapsed = round((time.time() - start) * 1000)

        # Rank by PageRank and annotate
        ranked = sorted(pr.items(), key=lambda x: x[1], reverse=True)

        # Compute mean + stddev for anomaly detection
        scores = list(pr.values())
        mean_pr = sum(scores) / len(scores)
        std_pr = (sum((s - mean_pr) ** 2 for s in scores) / len(scores)) ** 0.5
        threshold = mean_pr + 2 * std_pr  # 2-sigma anomaly

        nodes = []
        for node_id, score in ranked[:top_k]:
            node_data = G.nodes[node_id]
            in_degree = G.in_degree(node_id)
            out_degree = G.out_degree(node_id)
            total_value_in = sum(d.get("value", 0) for _, _, d in G.in_edges(node_id, data=True))
            total_value_out = sum(d.get("value", 0) for _, _, d in G.out_edges(node_id, data=True))

            nodes.append({
                "node_id": node_id,
                "pagerank": round(score, 6),
                "eigenvector_centrality": round(eigen.get(node_id, 0), 6),
                "betweenness_centrality": round(between.get(node_id, 0), 6),
                "is_anomaly": score > threshold,
                "node_type": node_data.get("type", "unknown"),
                "in_degree": in_degree,
                "out_degree": out_degree,
                "total_value_in": round(total_value_in, 2),
                "total_value_out": round(total_value_out, 2),
            })

        return {
            "nodes": nodes,
            "total_nodes": len(G.nodes),
            "total_edges": len(G.edges),
            "anomaly_threshold": round(threshold, 6),
            "mean_pagerank": round(mean_pr, 6),
            "std_pagerank": round(std_pr, 6),
            "computation_ms": elapsed,
            "algorithm": "PageRank (alpha=0.85, weighted by tx value)",
        }

    except Exception as exc:
        return {**_fallback_result(), "error": str(exc)}


def _fallback_result() -> Dict[str, Any]:
    return {
        "nodes": [
            {"node_id": "MIXER_001", "pagerank": 0.085, "is_anomaly": True,
             "node_type": "hub", "in_degree": 25, "out_degree": 20},
            {"node_id": "SHELL_CORP_A", "pagerank": 0.072, "is_anomaly": True,
             "node_type": "hub", "in_degree": 22, "out_degree": 18},
        ],
        "total_nodes": 84, "total_edges": 335,
        "algorithm": "fallback_synthetic",
    }
