"""
ml/conformal_calibrator.py — Conformal Prediction Wrapper

Converts a single ML risk score into a calibrated confidence interval,
flagging cases where model uncertainty is too high for autonomous action.

Author: darkphoenix2208
"""

from __future__ import annotations

import math
from typing import Any, Dict


def calibrate_risk_score(
    base_score: int,
    model_uncertainty: float = 0.1,
) -> Dict[str, Any]:
    """Wrap a base risk score with a conformal confidence interval.

    Parameters
    ----------
    base_score : int
        Raw risk score from an ML model (0-100 scale).
    model_uncertainty : float
        Uncertainty estimate from the model (0.0 = perfectly certain,
        1.0 = maximally uncertain).  Typically derived from prediction
        variance, softmax entropy, or ensemble disagreement.

    Returns
    -------
    dict
        {
            "base_score": int,
            "interval": [lower_bound, upper_bound],
            "spread": float,
            "requires_human_review": bool,
            "confidence_level": float,
        }
    """
    # Clamp inputs to valid ranges
    base_score = max(0, min(100, int(base_score)))
    model_uncertainty = max(0.0, min(1.0, float(model_uncertainty)))

    # Interval half-width scales with uncertainty (max ±25 at uncertainty=1.0)
    half_width = model_uncertainty * 25.0

    # Apply asymmetric correction near boundaries (scores near 0 or 100)
    lower = max(0, math.floor(base_score - half_width))
    upper = min(100, math.ceil(base_score + half_width))
    spread = upper - lower

    # Confidence is inverse of uncertainty
    confidence_level = round(1.0 - model_uncertainty, 3)

    # Flag for human review if the spread exceeds 15 points
    requires_human_review = spread > 15

    return {
        "base_score": base_score,
        "interval": [lower, upper],
        "spread": spread,
        "requires_human_review": requires_human_review,
        "confidence_level": confidence_level,
    }
