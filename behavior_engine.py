"""
behavior_engine.py — Customer Session Anomaly Detection Engine

Uses a Gaussian Mixture Model (GMM) fitted on historical user-session
features to score new sessions as normal or anomalous.

Author: darkphoenix2208
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


# ---------------------------------------------------------------------------
# Feature schema for session scoring
# ---------------------------------------------------------------------------
SESSION_FEATURES: List[str] = [
    "clicks_last_hour",
    "avg_time_between_clicks",
    "session_length",
    "num_failed_logins",
    "device_change_rate",
    "location_variance",
    "browser_jump_freq",
    "actions_per_session",
]


class BehaviorAnomalyDetector:
    """GMM-based anomaly detector for user session behaviour.

    Trains on historical feature distributions and flags new sessions
    whose log-likelihood falls below the 5th-percentile threshold.
    """

    def __init__(self, n_components: int = 2, percentile_threshold: float = 5.0) -> None:
        self._n_components = n_components
        self._percentile = percentile_threshold
        self._scaler = StandardScaler()
        self._gmm = GaussianMixture(
            n_components=n_components,
            covariance_type="full",
            random_state=42,
        )
        self._threshold: float = 0.0
        self._fitted = False
        self._train_on_synthetic()

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def _train_on_synthetic(self) -> None:
        """Bootstrap the model with realistic synthetic session data."""
        rng = np.random.RandomState(42)
        n = 500

        # Cluster A — casual users
        cluster_a = np.column_stack([
            rng.poisson(lam=20, size=n),           # clicks_last_hour
            rng.exponential(scale=40, size=n),      # avg_time_between_clicks
            rng.uniform(300, 2000, size=n),          # session_length
            rng.poisson(lam=0.2, size=n),            # num_failed_logins
            rng.poisson(lam=1, size=n),              # device_change_rate
            rng.poisson(lam=1, size=n),              # location_variance
            rng.poisson(lam=1, size=n),              # browser_jump_freq
            rng.poisson(lam=25, size=n),             # actions_per_session
        ])

        # Cluster B — power users
        cluster_b = np.column_stack([
            rng.poisson(lam=50, size=n),
            rng.exponential(scale=10, size=n),
            rng.uniform(1000, 3000, size=n),
            rng.poisson(lam=1, size=n),
            rng.poisson(lam=2, size=n),
            rng.poisson(lam=2, size=n),
            rng.poisson(lam=2, size=n),
            rng.poisson(lam=60, size=n),
        ])

        X = np.vstack([cluster_a, cluster_b]).astype(float)
        self._fit(X)

    def _fit(self, X: np.ndarray) -> None:
        X_scaled = self._scaler.fit_transform(X)
        self._gmm.fit(X_scaled)
        log_likelihoods = self._gmm.score_samples(X_scaled)
        self._threshold = float(np.percentile(log_likelihoods, self._percentile))
        self._fitted = True

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------
    def score_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single session dict.

        Parameters
        ----------
        session : dict
            Must contain keys from SESSION_FEATURES.

        Returns
        -------
        dict
            {
                "anomaly_score": float,      # raw log-likelihood
                "is_anomaly": bool,
                "threshold": float,
                "features_used": list[str],
                "risk_level": str,           # NORMAL | SUSPICIOUS | ANOMALOUS
            }
        """
        if not self._fitted:
            return {
                "anomaly_score": 0.0,
                "is_anomaly": False,
                "threshold": 0.0,
                "features_used": SESSION_FEATURES,
                "risk_level": "UNKNOWN",
                "error": "Model not fitted",
            }

        # Extract features in the correct order
        feature_vec = []
        for feat in SESSION_FEATURES:
            feature_vec.append(float(session.get(feat, 0.0)))

        X = np.array([feature_vec])
        X_scaled = self._scaler.transform(X)
        log_likelihood = float(self._gmm.score_samples(X_scaled)[0])
        is_anomaly = log_likelihood < self._threshold

        # Three-tier classification
        if log_likelihood < self._threshold * 1.5:
            risk_level = "ANOMALOUS"
        elif log_likelihood < self._threshold:
            risk_level = "SUSPICIOUS"
        else:
            risk_level = "NORMAL"

        return {
            "anomaly_score": round(log_likelihood, 4),
            "is_anomaly": is_anomaly,
            "threshold": round(self._threshold, 4),
            "features_used": SESSION_FEATURES,
            "risk_level": risk_level,
        }


# Module-level singleton — trained on import
behavior_detector = BehaviorAnomalyDetector()
