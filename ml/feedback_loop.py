"""
ml/feedback_loop.py — RLHF Human Feedback Logger

Logs human analyst verdicts to a local JSON file so that future
retraining runs can incorporate real-world label corrections
via partial_fit or full re-training of the Ensemble models.

Author: darkphoenix2208
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_LOG_DIR = Path(__file__).resolve().parent.parent / "data"
_LOG_FILE = _LOG_DIR / "rlhf_logs.json"


def log_human_feedback(
    transaction_id: str,
    human_label: bool,
    original_score: Optional[float] = None,
) -> Dict[str, Any]:
    """Persist a human analyst's fraud verdict for future model retraining.

    Parameters
    ----------
    transaction_id : str
        The investigation / transaction identifier.
    human_label : bool
        True = human confirms fraud, False = human says legitimate.
    original_score : float, optional
        The ML model's original risk score for comparison.

    Returns
    -------
    dict
        Confirmation with the logged entry and total log count.
    """
    if not transaction_id or not isinstance(transaction_id, str):
        return {"logged": False, "error": "transaction_id is required"}

    entry = {
        "transaction_id": transaction_id.strip(),
        "human_label": bool(human_label),
        "original_score": float(original_score) if original_score is not None else None,
        "timestamp": time.time(),
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Ensure data directory exists
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # Load existing logs
    logs: list = []
    if _LOG_FILE.exists():
        try:
            with open(_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
                if not isinstance(logs, list):
                    logs = []
        except (json.JSONDecodeError, OSError):
            logs = []

    logs.append(entry)

    # Write back
    try:
        with open(_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2)
    except OSError as exc:
        return {"logged": False, "error": f"Write failed: {exc}"}

    return {
        "logged": True,
        "entry": entry,
        "total_entries": len(logs),
    }
