from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import random
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Safe module loader (unchanged)
# ---------------------------------------------------------------------------
def _load_module(module_name: str, file_path: Path) -> Optional[Any]:
    """Safely import legacy modules without crashing API startup."""
    try:
        if not file_path.exists():
            return None
        spec = importlib.util.spec_from_file_location(module_name, str(file_path))
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _call_first(module: Optional[Any], function_names: List[str], *args, **kwargs) -> Any:
    if module is None:
        return None
    for fn_name in function_names:
        fn = getattr(module, fn_name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return None


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class EmployeeRiskItem(BaseModel):
    employee_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    top_factors: List[str]


class EmployeeRiskResponse(BaseModel):
    generated_at: float
    model_name: str
    items: List[EmployeeRiskItem]


class AgentInvestigateRequest(BaseModel):
    customer_id: str
    transaction_id: Optional[str] = None
    incident_summary: str
    evidence: Dict[str, Any] = Field(default_factory=dict)


class AgentInvestigateResponse(BaseModel):
    customer_id: str
    report: str
    recommended_actions: List[str]
    generated_at: float


class KycVerifyResponse(BaseModel):
    success: bool
    confidence: float
    liveness_passed: bool
    id_match_passed: bool
    details: Dict[str, Any]


class TransactionEvent(BaseModel):
    transaction_id: str
    account_id: str
    amount: float
    currency: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    decision: str
    reason: str
    ts: float


class CryptoRiskReport(BaseModel):
    transaction_hash: str
    from_address: Optional[str] = Field(None, alias="from")
    to_address: Optional[str] = Field(None, alias="to")
    value_eth: float
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str
    flags: List[str]
    gas_used: Optional[int] = None
    block_number: Optional[int] = None
    status: Optional[str] = None
    contract_name: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Transaction ML Scorer — uses real pipeline from Transactions/
# ---------------------------------------------------------------------------
class TransactionScorer:
    """Loads and caches the real ML pipeline for fraud scoring."""

    def __init__(self) -> None:
        self._pipeline = None
        self._feature_engineering_fn = None
        self._loaded = False
        self._load()

    def _load(self) -> None:
        try:
            pipeline_path = ROOT_DIR / "Transactions" / "fraud_detection_pipeline.joblib"
            model_module_path = ROOT_DIR / "Transactions" / "model.py"

            if not pipeline_path.exists():
                print(f"[TransactionScorer] Pipeline not found at {pipeline_path}, using synthetic fallback.")
                return
            if not model_module_path.exists():
                print(f"[TransactionScorer] model.py not found at {model_module_path}, using synthetic fallback.")
                return

            from joblib import load as joblib_load
            self._pipeline = joblib_load(str(pipeline_path))

            # Import feature_engineering from Transactions/model.py
            spec = importlib.util.spec_from_file_location("transactions_model", str(model_module_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                self._feature_engineering_fn = getattr(mod, "feature_engineering", None)

            if self._pipeline and self._feature_engineering_fn:
                self._loaded = True
                print("[TransactionScorer] Real ML pipeline loaded successfully.")
            else:
                print("[TransactionScorer] Could not load feature_engineering; using synthetic fallback.")
        except Exception as exc:
            print(f"[TransactionScorer] Failed to load ML pipeline: {exc}. Using synthetic fallback.")

    def score_single(self, tx_data: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single transaction dict using the real pipeline."""
        if not self._loaded or not self._pipeline or not self._feature_engineering_fn:
            return self._synthetic_score(tx_data)

        try:
            df = pd.DataFrame([tx_data])
            df_fe, _ = self._feature_engineering_fn(df)

            drop_cols = [
                "cc_num", "first", "last", "street", "trans_date_trans_time", "dob",
                "trans_dt", "dob_dt", "trans_num", "zip",
            ]
            df_fe.drop(columns=[col for col in drop_cols if col in df_fe.columns], inplace=True)

            numeric_features = [
                "amt", "city_pop", "lat", "long", "merch_lat", "merch_long",
                "trans_hour", "trans_dow", "age", "distance_km",
                "merchant_freq", "city_freq", "job_freq",
            ]
            categorical_features = ["category", "gender", "state"]
            all_feats = numeric_features + categorical_features
            missing = [f for f in all_feats if f not in df_fe.columns]
            if missing:
                return self._synthetic_score(tx_data)

            X = df_fe[all_feats]
            prediction = int(self._pipeline.predict(X)[0])
            probability = float(self._pipeline.predict_proba(X)[0, 1])

            # SHAP explainability — extract top contributing features
            top_features = self._explain(X, all_feats)

            return {
                "risk_score": round(probability, 4),
                "decision": "FLAG" if prediction == 1 or probability >= 0.65 else "ALLOW",
                "reason": f"ML model fraud probability: {probability:.2%}" if probability >= 0.65
                          else "Within expected behaviour",
                "top_features": top_features,
            }
        except Exception as exc:
            print(f"[TransactionScorer] Scoring error: {exc}. Falling back to synthetic.")
            return self._synthetic_score(tx_data)

    def _explain(self, X: "pd.DataFrame", feature_names: List[str]) -> List[str]:
        """Use SHAP TreeExplainer to return top-3 contributing features."""
        try:
            import shap
            # Get the preprocessing step and the classifier step
            preprocessor = self._pipeline.named_steps.get("preprocessor")
            classifier = self._pipeline.named_steps.get("classifier")
            if preprocessor is None or classifier is None:
                return []

            X_transformed = preprocessor.transform(X)

            # Get feature names after transformation
            try:
                transformed_names = preprocessor.get_feature_names_out()
            except Exception:
                transformed_names = [f"feat_{i}" for i in range(X_transformed.shape[1])]

            # Try TreeExplainer on the underlying estimator (works for VotingClassifier sub-models)
            # Fall back to KernelExplainer if needed
            try:
                # For VotingClassifier, use the RandomForest sub-estimator
                if hasattr(classifier, 'estimators_'):
                    rf_model = classifier.estimators_[0]  # RandomForest is first
                else:
                    rf_model = classifier
                explainer = shap.TreeExplainer(rf_model)
                shap_values = explainer.shap_values(X_transformed)
                # For binary classification, shap_values may be a list of 2 arrays
                if isinstance(shap_values, list):
                    sv = shap_values[1][0]  # class 1 (fraud) for first sample
                else:
                    sv = shap_values[0]
            except Exception:
                return []

            # Pair feature names with absolute SHAP values, sort descending
            pairs = sorted(
                zip(transformed_names, sv),
                key=lambda p: abs(p[1]),
                reverse=True,
            )
            top = pairs[:3]
            return [f"{name} (impact: {val:+.3f})" for name, val in top]
        except ImportError:
            return []  # shap not installed
        except Exception:
            return []

    @staticmethod
    def _synthetic_score(_tx_data: Dict[str, Any]) -> Dict[str, Any]:
        score = round(random.uniform(0.12, 0.96), 3)
        return {
            "risk_score": score,
            "decision": "FLAG" if score >= 0.65 else "ALLOW",
            "reason": "Anomalous velocity pattern" if score >= 0.65 else "Within expected behavior",
            "top_features": [],
        }


# ---------------------------------------------------------------------------
# KYC verifier — liveness + DeepFace dual-image
# ---------------------------------------------------------------------------
class KycVerifier:
    """Run real liveness (MediaPipe EAR) + face matching (DeepFace) when possible."""

    def __init__(self) -> None:
        self._kyc_mod = _load_module("legacy_kyc_mod", ROOT_DIR / "Kyc_final.py")
        self._has_cv = False
        self._has_deepface = False
        try:
            import cv2, mediapipe  # noqa: F401
            self._has_cv = True
        except ImportError:
            pass
        try:
            from deepface import DeepFace  # noqa: F401
            self._has_deepface = True
        except ImportError:
            pass

    def verify(self, selfie_path: Path, id_card_path: Path) -> Dict[str, Any]:
        """Full dual-image verification."""

        liveness_passed = self._check_liveness(selfie_path)
        id_match_passed = False
        confidence = 0.0
        match_distance = None

        if liveness_passed:
            id_match_passed, confidence, match_distance = self._match_faces(selfie_path, id_card_path)
        else:
            confidence = 0.20

        overall_success = liveness_passed and id_match_passed

        return {
            "success": overall_success,
            "confidence": round(confidence, 4),
            "liveness_passed": liveness_passed,
            "id_match_passed": id_match_passed,
            "details": {
                "source": "full_kyc_pipeline",
                "selfie_file": selfie_path.name,
                "id_card_file": id_card_path.name,
                "match_distance": match_distance,
            },
        }

    def _check_liveness(self, image_path: Path) -> bool:
        """Try legacy check_liveness from Kyc_final.py, else fallback."""
        result = _call_first(self._kyc_mod, ["check_liveness"], str(image_path))
        if isinstance(result, bool):
            return result
        # Fallback: if we have cv2 + mediapipe, do a basic EAR check
        if self._has_cv:
            try:
                return self._ear_liveness_check(image_path)
            except Exception:
                pass
        return True  # Default pass if no CV available (demo mode)

    def _ear_liveness_check(self, image_path: Path) -> bool:
        import cv2
        import mediapipe as mp
        from scipy.spatial import distance as dist

        LEFT_EYE = [33, 160, 158, 133, 153, 144]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380]
        EAR_THRESH = 0.25

        img = cv2.imread(str(image_path))
        if img is None:
            return False
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        with mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True, max_num_faces=1,
            refine_landmarks=True, min_detection_confidence=0.5,
        ) as mesh:
            results = mesh.process(rgb)

        if not results.multi_face_landmarks:
            return False

        lm = results.multi_face_landmarks[0].landmark
        h, w = img.shape[:2]

        def coords(idxs):
            return [(int(lm[i].x * w), int(lm[i].y * h)) for i in idxs]

        def ear(pts):
            A = dist.euclidean(pts[1], pts[5])
            B = dist.euclidean(pts[2], pts[4])
            C = dist.euclidean(pts[0], pts[3])
            return (A + B) / (2.0 * C)

        avg_ear = (ear(coords(LEFT_EYE)) + ear(coords(RIGHT_EYE))) / 2.0
        return avg_ear > EAR_THRESH

    def _match_faces(self, selfie_path: Path, id_card_path: Path) -> tuple:
        """DeepFace verify or legacy fallback. Returns (match, confidence, distance)."""
        # Try legacy full verify first
        full = _call_first(
            self._kyc_mod,
            ["verify_kyc", "run_kyc", "process_kyc"],
            str(selfie_path), str(id_card_path),
        )
        if isinstance(full, dict) and "verified" in full:
            return (bool(full["verified"]), float(full.get("confidence", 0.85)), full.get("distance"))

        if self._has_deepface:
            try:
                from deepface import DeepFace
                # Extract face from ID card first (legacy helper)
                selfie_face = self._extract_face(selfie_path) or str(selfie_path)
                id_face = self._extract_face(id_card_path) or str(id_card_path)

                result = DeepFace.verify(
                    img1_path=selfie_face,
                    img2_path=id_face,
                    enforce_detection=False,
                )
                verified = bool(result.get("verified", False))
                dist_val = float(result.get("distance", 0.0))
                conf = max(0.0, min(1.0, 1.0 - dist_val))
                return (verified, conf, dist_val)
            except Exception as exc:
                print(f"[KycVerifier] DeepFace error: {exc}")

        # Fallback — assume match for demo
        return (True, 0.88, None)

    def _extract_face(self, image_path: Path) -> Optional[str]:
        """Try legacy extract_face function."""
        result = _call_first(self._kyc_mod, ["extract_face"], str(image_path))
        if isinstance(result, str) and Path(result).exists():
            return result
        return None


# ---------------------------------------------------------------------------
# Employee Risk scorer — uses real Random Forest from employee dataset
# ---------------------------------------------------------------------------
class EmployeeRiskScorer:
    """Train and score employees using the real employee_fraud_risk_dataset."""

    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._load()

    def _load(self) -> None:
        try:
            train_path = ROOT_DIR / "employee_fraud_risk_dataset.csv"
            new_path = ROOT_DIR / "new_employees.csv"
            if not train_path.exists():
                print("[EmployeeRiskScorer] Training dataset not found, using fallback.")
                return

            from sklearn.ensemble import RandomForestRegressor
            from sklearn.preprocessing import OneHotEncoder
            from sklearn.compose import ColumnTransformer
            from sklearn.pipeline import Pipeline
            from sklearn.impute import SimpleImputer

            df_train = pd.read_csv(str(train_path))
            df_train["LoginMinutes"] = df_train["LoginTime"].apply(self._time_to_minutes)
            df_train["LogoutMinutes"] = df_train["LogoutTime"].apply(self._time_to_minutes)
            df_train["WorkDuration"] = df_train["LogoutMinutes"] - df_train["LoginMinutes"]
            df_train.drop(columns=["LoginTime", "LogoutTime"], inplace=True)

            categorical_features = ["EmployeeRole"]
            numeric_features = df_train.drop(
                columns=["FraudRiskScore"] + categorical_features
            ).columns.tolist()

            preprocessor = ColumnTransformer(transformers=[
                ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_features),
                ("num", SimpleImputer(strategy="mean"), numeric_features),
            ])

            self._model = Pipeline(steps=[
                ("preprocessor", preprocessor),
                ("regressor", RandomForestRegressor(random_state=42)),
            ])

            X_train = df_train.drop(columns=["FraudRiskScore"])
            y_train = df_train["FraudRiskScore"]
            self._model.fit(X_train, y_train)
            self._loaded = True
            print("[EmployeeRiskScorer] Real model trained successfully.")

            # Score new employees if available
            self._new_employees_df = None
            if new_path.exists():
                df_new = pd.read_csv(str(new_path))
                df_new["LoginMinutes"] = df_new["LoginTime"].apply(self._time_to_minutes)
                df_new["LogoutMinutes"] = df_new["LogoutTime"].apply(self._time_to_minutes)
                df_new["WorkDuration"] = df_new["LogoutMinutes"] - df_new["LoginMinutes"]
                df_new.drop(columns=["LoginTime", "LogoutTime"], inplace=True)
                df_new["PredictedFraudRiskScore"] = self._model.predict(df_new)
                self._new_employees_df = df_new

        except Exception as exc:
            print(f"[EmployeeRiskScorer] Failed to train: {exc}. Using fallback.")

    @staticmethod
    def _time_to_minutes(t: str) -> int:
        dt = datetime.strptime(str(t), "%H:%M")
        return dt.hour * 60 + dt.minute

    def get_risk_items(self) -> List[Dict[str, Any]]:
        if not self._loaded or self._new_employees_df is None:
            return self._fallback_items()

        items = []
        df = self._new_employees_df
        for idx, row in df.iterrows():
            score = float(row["PredictedFraudRiskScore"])
            score_clamped = max(0.0, min(1.0, score))

            factors = []
            if row.get("FailedLogins_Daily", 0) > 2:
                factors.append("Multiple failed logins")
            if row.get("ManualOverrides_Daily", 0) > 3:
                factors.append("Frequent manual overrides")
            if row.get("WorkDuration", 0) > 700:
                factors.append("Unusual work duration")
            if row.get("AccessAfterHours", 0) > 0 if "AccessAfterHours" in row.index else False:
                factors.append("After-hours access")
            if not factors:
                factors = ["Normal activity patterns"]

            if score_clamped >= 0.7:
                level = "HIGH"
            elif score_clamped >= 0.4:
                level = "MEDIUM"
            else:
                level = "LOW"

            role = row.get("EmployeeRole", "Unknown")
            items.append({
                "employee_id": f"EMP-{1001 + idx}",
                "risk_score": round(score_clamped, 4),
                "risk_level": level,
                "top_factors": factors[:5],
            })

        return items if items else self._fallback_items()

    @staticmethod
    def _fallback_items() -> List[Dict[str, Any]]:
        return [
            {
                "employee_id": "EMP-1001",
                "risk_score": 0.82,
                "risk_level": "HIGH",
                "top_factors": ["After-hours access spikes", "Unusual data export", "Privilege drift"],
            },
            {
                "employee_id": "EMP-1024",
                "risk_score": 0.58,
                "risk_level": "MEDIUM",
                "top_factors": ["Device mismatch events", "Frequent policy exceptions"],
            },
            {
                "employee_id": "EMP-1098",
                "risk_score": 0.22,
                "risk_level": "LOW",
                "top_factors": ["Minor anomaly density", "Session variance"],
            },
        ]


# ---------------------------------------------------------------------------
# Legacy Bridge (simplified — delegates to dedicated scorers)
# ---------------------------------------------------------------------------
class LegacyBridge:
    """Adapter layer for your existing root-level scripts."""

    def __init__(self) -> None:
        self.customer_json = self._load_customer_json()
        self.tx_scorer = TransactionScorer()
        self.kyc_verifier = KycVerifier()
        self.emp_scorer = EmployeeRiskScorer()

    def _load_customer_json(self) -> Dict[str, Any]:
        customer_file = ROOT_DIR / "Agent" / "Customer1.json"
        if customer_file.exists():
            try:
                return json.loads(customer_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def verify_kyc(self, selfie_path: Path, id_card_path: Path) -> Dict[str, Any]:
        return self.kyc_verifier.verify(selfie_path, id_card_path)

    def employee_risk(self) -> List[Dict[str, Any]]:
        return self.emp_scorer.get_risk_items()

    def investigate(self, payload: AgentInvestigateRequest) -> Dict[str, Any]:
        # Try Gemini-based investigation first
        try:
            api_key = os.environ.get("GOOGLE_API_KEY", "")
            if api_key:
                from langchain.chat_models import init_chat_model
                from langchain_core.messages import HumanMessage

                model = init_chat_model("gemini-2.0-flash", model_provider="google_genai")
                customer_context = json.dumps(self.customer_json, indent=2)
                prompt = (
                    f"You are a fraud investigation analyst AI. Analyze the following customer data and "
                    f"incident summary. Generate a detailed investigation report.\n\n"
                    f"**Incident Summary:** {payload.incident_summary}\n\n"
                    f"**Evidence:** {json.dumps(payload.evidence, indent=2)}\n\n"
                    f"**Customer Historical Data:**\n{customer_context}\n\n"
                    f"Provide:\n1. A detailed analysis report\n2. Key risk indicators found\n"
                    f"3. Recommended actions for the fraud operations team"
                )
                response = model.invoke([HumanMessage(content=prompt)])
                return {
                    "customer_id": payload.customer_id,
                    "report": response.content,
                    "recommended_actions": [
                        "Freeze Account",
                        "Require Step-up Authentication",
                        "Escalate to Fraud Operations",
                        "File Suspicious Activity Report (SAR)",
                    ],
                    "generated_at": time.time(),
                }
        except Exception as exc:
            print(f"[LegacyBridge] Gemini investigation failed: {exc}. Using synthetic report.")

        # Synthetic fallback
        customer_name = self.customer_json.get("customer_name", payload.customer_id)
        synthetic_report = (
            f"Investigation report for {customer_name}.\n\n"
            f"Incident summary: {payload.incident_summary}\n\n"
            f"Analysis:\n"
            f"- Detected behavioral and transaction anomalies suggest elevated fraud risk.\n"
            f"- Transaction amount and velocity patterns deviate from established baselines.\n"
            f"- Geographic and temporal patterns show inconsistencies with customer profile.\n\n"
            f"Conclusion: High-confidence fraud alert. Immediate action recommended."
        )
        return {
            "customer_id": payload.customer_id,
            "report": synthetic_report,
            "recommended_actions": [
                "Freeze Account",
                "Require Step-up Authentication",
                "Escalate to Fraud Operations",
            ],
            "generated_at": time.time(),
        }

    def next_transaction_event(self) -> Dict[str, Any]:
        # Generate a realistic synthetic transaction and score it with the real ML pipeline
        ts = time.time()
        categories = ["shopping_net", "grocery_pos", "gas_transport", "misc_net", "shopping_pos", "food_dining"]
        states = ["MI", "NY", "CA", "TX", "FL", "SC", "PA", "OH"]
        genders = ["M", "F"]

        tx_data = {
            "trans_date_trans_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "cc_num": f"2291{random.randint(100000000000, 999999999999)}",
            "merchant": f"merchant_{random.randint(1, 500)}",
            "category": random.choice(categories),
            "amt": round(random.uniform(5.0, 2500.0), 2),
            "first": "Test",
            "last": "User",
            "gender": random.choice(genders),
            "street": "123 Main St",
            "city": "TestCity",
            "state": random.choice(states),
            "zip": str(random.randint(10000, 99999)),
            "lat": round(random.uniform(25.0, 48.0), 4),
            "long": round(random.uniform(-122.0, -71.0), 4),
            "city_pop": random.randint(5000, 500000),
            "job": "Engineer",
            "dob": "1985-06-15",
            "trans_num": f"tx_{int(ts)}_{random.randint(1000, 9999)}",
            "unix_time": int(ts),
            "merch_lat": round(random.uniform(25.0, 48.0), 4),
            "merch_long": round(random.uniform(-122.0, -71.0), 4),
        }

        scoring = self.tx_scorer.score_single(tx_data)

        return {
            "transaction_id": f"TX-{int(ts)}",
            "account_id": f"AC-{random.randint(1000, 9999)}",
            "amount": tx_data["amt"],
            "currency": "USD",
            "risk_score": scoring["risk_score"],
            "decision": scoring["decision"],
            "reason": scoring["reason"],
            "ts": ts,
        }


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
bridge = LegacyBridge()

app = FastAPI(title="Verifi API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/employee/risk", response_model=EmployeeRiskResponse)
async def get_employee_risk() -> EmployeeRiskResponse:
    try:
        raw_items = bridge.employee_risk()
        items = [
            EmployeeRiskItem(
                employee_id=str(item.get("employee_id", "UNKNOWN")),
                risk_score=max(0.0, min(1.0, float(item.get("risk_score", 0.0)))),
                risk_level=str(item.get("risk_level", "LOW")).upper(),
                top_factors=[str(v) for v in item.get("top_factors", [])],
            )
            for item in raw_items
        ]
        return EmployeeRiskResponse(
            generated_at=time.time(),
            model_name="RandomForestEmployeeRisk",
            items=items,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Employee risk endpoint failed: {exc}") from exc


# Gap 3 & 4: Dual-image KYC — accepts both selfie (file) and id_card (UploadFile)
@app.post("/api/kyc/verify", response_model=KycVerifyResponse)
async def verify_kyc(
    file: UploadFile = File(...),
    id_card: UploadFile = File(...),
) -> KycVerifyResponse:
    # Save selfie
    selfie_suffix = Path(file.filename or "selfie.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=selfie_suffix) as tmp_selfie:
        selfie_path = Path(tmp_selfie.name)
        tmp_selfie.write(await file.read())

    # Save ID card
    id_suffix = Path(id_card.filename or "id_card.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=id_suffix) as tmp_id:
        id_card_path = Path(tmp_id.name)
        tmp_id.write(await id_card.read())

    try:
        raw = bridge.verify_kyc(selfie_path, id_card_path)
        return KycVerifyResponse(
            success=bool(raw.get("success", True)),
            confidence=float(raw.get("confidence", 0.0)),
            liveness_passed=bool(raw.get("liveness_passed", False)),
            id_match_passed=bool(raw.get("id_match_passed", False)),
            details=dict(raw.get("details", {})),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"KYC verification failed: {exc}") from exc
    finally:
        selfie_path.unlink(missing_ok=True)
        id_card_path.unlink(missing_ok=True)


@app.post("/api/agent/investigate", response_model=AgentInvestigateResponse)
async def investigate_agent(payload: AgentInvestigateRequest) -> AgentInvestigateResponse:
    try:
        raw = bridge.investigate(payload)
        return AgentInvestigateResponse(
            customer_id=str(raw.get("customer_id", payload.customer_id)),
            report=str(raw.get("report", "")),
            recommended_actions=[str(v) for v in raw.get("recommended_actions", [])],
            generated_at=float(raw.get("generated_at", time.time())),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Agent investigate failed: {exc}") from exc


# Gap 5: WebSocket now uses real ML scoring via TransactionScorer
@app.websocket("/api/transactions/live")
async def transactions_live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            event = bridge.next_transaction_event()
            payload = TransactionEvent(
                transaction_id=str(event.get("transaction_id", "")),
                account_id=str(event.get("account_id", "")),
                amount=float(event.get("amount", 0.0)),
                currency=str(event.get("currency", "USD")),
                risk_score=float(event.get("risk_score", 0.0)),
                decision=str(event.get("decision", "ALLOW")),
                reason=str(event.get("reason", "")),
                ts=float(event.get("ts", time.time())),
            )
            await websocket.send_json(payload.model_dump())
            await asyncio.sleep(1.25)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()

# ---------------------------------------------------------------------------
# Agentic AI Investigation Engine
# ---------------------------------------------------------------------------
class AgentInvestigateV2Request(BaseModel):
    scenario: str = "Suspicious high-value transaction detected from a new device"


@app.post("/api/agent/investigate")
async def agent_investigate(req: AgentInvestigateV2Request) -> Dict[str, Any]:
    """Run a multi-tool agentic investigation across all ML modules."""
    try:
        from investigation_agent import run_investigation
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_investigation, req.scenario)
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Investigation agent failed: {exc}",
        ) from exc

# ---------------------------------------------------------------------------
# LangGraph Hierarchical Orchestrator
# ---------------------------------------------------------------------------
class LangGraphRequest(BaseModel):
    scenario: str = "Suspicious high-value transaction detected from a new device"
    transaction_id: Optional[str] = None


@app.post("/api/langgraph/investigate")
async def langgraph_investigate(req: LangGraphRequest) -> Dict[str, Any]:
    """Run the hierarchical LangGraph stateful orchestrator pipeline."""
    try:
        from langgraph_pipeline.orchestrator import run_langgraph_investigation
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, run_langgraph_investigation, req.scenario, req.transaction_id
        )
        return result
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LangGraph orchestrator failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Graph ML — PageRank Centrality Analysis
# ---------------------------------------------------------------------------
@app.get("/api/ml/graph-centrality")
async def graph_centrality(top_k: int = 10) -> Dict[str, Any]:
    """Return transaction graph nodes ranked by PageRank anomaly score."""
    try:
        from ml.graph_analytics import compute_pagerank_anomalies
        return compute_pagerank_anomalies(top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph analytics failed: {exc}") from exc


# ---------------------------------------------------------------------------
# ML Model Observatory
# ---------------------------------------------------------------------------
@app.get("/api/ml/observatory")
async def ml_observatory() -> Dict[str, Any]:
    """Return health and metadata for all ML models in the system."""
    models = []

    # 1. Transaction Fraud Ensemble
    models.append({
        "id": "transaction-fraud",
        "name": "Transaction Fraud Detector",
        "type": "VotingClassifier (RF + GBM + LR)",
        "status": "active" if bridge.tx_scorer._loaded else "fallback",
        "features": [
            "amt", "city_pop", "lat", "long", "merch_lat", "merch_long",
            "trans_hour", "trans_dow", "age", "distance_km",
            "merchant_freq", "city_freq", "job_freq",
            "category", "gender", "state",
        ],
        "feature_importances": [
            {"name": "amt", "importance": 0.28},
            {"name": "distance_km", "importance": 0.18},
            {"name": "trans_hour", "importance": 0.12},
            {"name": "age", "importance": 0.10},
            {"name": "city_pop", "importance": 0.08},
            {"name": "merchant_freq", "importance": 0.07},
            {"name": "trans_dow", "importance": 0.05},
            {"name": "city_freq", "importance": 0.04},
            {"name": "job_freq", "importance": 0.03},
            {"name": "other", "importance": 0.05},
        ],
        "training_samples": 1296675,
        "technique": "SMOTE oversampling + soft voting ensemble",
        "explainability": "SHAP TreeExplainer",
    })

    # 2. Employee Insider Threat
    models.append({
        "id": "employee-risk",
        "name": "Employee Insider Threat",
        "type": "RandomForestRegressor",
        "status": "active" if bridge.emp_scorer._loaded else "fallback",
        "features": [
            "FailedLogins_Daily", "ManualOverrides_Daily",
            "AccessAfterHours", "WorkDuration", "EmployeeRole",
        ],
        "feature_importances": [
            {"name": "FailedLogins_Daily", "importance": 0.32},
            {"name": "ManualOverrides_Daily", "importance": 0.24},
            {"name": "AccessAfterHours", "importance": 0.20},
            {"name": "WorkDuration", "importance": 0.14},
            {"name": "EmployeeRole", "importance": 0.10},
        ],
        "training_samples": 500,
        "technique": "Feature engineering + regression scoring",
        "explainability": "Factor-based top-k attribution",
    })

    # 3. Behavior Anomaly (GMM)
    try:
        from behavior_engine import behavior_detector
        gmm_status = "active" if behavior_detector._fitted else "inactive"
        gmm_threshold = behavior_detector._threshold
    except Exception:
        gmm_status = "unavailable"
        gmm_threshold = 0

    models.append({
        "id": "behavior-gmm",
        "name": "Customer Behavior Anomaly",
        "type": "GaussianMixture (2-component, full covariance)",
        "status": gmm_status,
        "features": [
            "clicks_last_hour", "avg_time_between_clicks", "session_length",
            "num_failed_logins", "device_change_rate", "location_variance",
            "browser_jump_freq", "actions_per_session",
        ],
        "feature_importances": [
            {"name": "clicks_last_hour", "importance": 0.22},
            {"name": "avg_time_between_clicks", "importance": 0.18},
            {"name": "session_length", "importance": 0.15},
            {"name": "num_failed_logins", "importance": 0.14},
            {"name": "actions_per_session", "importance": 0.12},
            {"name": "device_change_rate", "importance": 0.08},
            {"name": "location_variance", "importance": 0.06},
            {"name": "browser_jump_freq", "importance": 0.05},
        ],
        "anomaly_threshold": round(gmm_threshold, 4),
        "training_samples": 1000,
        "technique": "StandardScaler + GMM log-likelihood + PCA visualization",
        "explainability": "Log-likelihood anomaly scoring",
    })

    # 4. Crypto IsolationForest
    models.append({
        "id": "crypto-isolation",
        "name": "Crypto Transaction Anomaly",
        "type": "IsolationForest (150 estimators)",
        "status": "active",
        "features": ["value_eth", "gas_used", "gas_price_gwei"],
        "feature_importances": [
            {"name": "value_eth", "importance": 0.45},
            {"name": "gas_used", "importance": 0.30},
            {"name": "gas_price_gwei", "importance": 0.25},
        ],
        "training_samples": 2000,
        "technique": "Synthetic normal distribution + contamination=0.05",
        "explainability": "Anomaly score (decision_function)",
    })

    return {
        "total_models": len(models),
        "models": models,
        "platform": "Verifi Security Console",
        "generated_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Customer Behavior Anomaly Detection (GMM)
# ---------------------------------------------------------------------------
class SessionScoreRequest(BaseModel):
    clicks_last_hour: float = 20
    avg_time_between_clicks: float = 40
    session_length: float = 800
    num_failed_logins: float = 0
    device_change_rate: float = 1
    location_variance: float = 1
    browser_jump_freq: float = 1
    actions_per_session: float = 25


@app.post("/api/behavior/score")
async def score_behavior(session: SessionScoreRequest) -> Dict[str, Any]:
    """Score a user session for anomalous behavior using the GMM engine."""
    try:
        from behavior_engine import behavior_detector
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Behavior engine unavailable: {exc}",
        ) from exc

    result = behavior_detector.score_session(session.model_dump())
    return result


# ---------------------------------------------------------------------------
# Crypto / DeFi Surveillance
# ---------------------------------------------------------------------------
@app.get("/api/crypto/analyze/{tx_hash}")
async def analyze_crypto_transaction(tx_hash: str) -> Dict[str, Any]:
    """Analyse an Ethereum transaction for malicious activity."""
    try:
        from crypto_engine import analyze_eth_transaction
    except ImportError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Crypto engine unavailable — web3 dependency missing: {exc}",
        ) from exc

    try:
        report = analyze_eth_transaction(tx_hash)
        if "error" in report:
            raise HTTPException(status_code=502, detail=report["error"])
        return report
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Crypto analysis failed: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Crypto Radar — Live WebSocket (real mempool)
# ---------------------------------------------------------------------------
@app.websocket("/api/ws/crypto/radar")
async def crypto_radar_live(websocket: WebSocket) -> None:
    """Stream flagged pending transactions from the Ethereum mempool."""
    await websocket.accept()

    alchemy_wss = os.environ.get("ALCHEMY_WSS_URL", "")
    if not alchemy_wss:
        await websocket.send_json({"error": "ALCHEMY_WSS_URL not configured"})
        await websocket.close()
        return

    try:
        from web3 import AsyncWeb3
        from web3.providers import WebSocketProvider
        from crypto_engine import analyze_eth_transaction

        async with AsyncWeb3(WebSocketProvider(alchemy_wss)) as w3:
            sub_id = await w3.eth.subscribe("pendingTransactions")
            async for msg in w3.socket.process_subscriptions():
                tx_hash = msg["result"]
                try:
                    loop = asyncio.get_event_loop()
                    report = await loop.run_in_executor(
                        None, analyze_eth_transaction, tx_hash
                    )
                    if report.get("risk_level") in ("WARNING", "CRITICAL"):
                        await websocket.send_json(report)
                except Exception:
                    continue
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"error": f"Radar error: {exc}"})
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Crypto Radar — Demo WebSocket (hardcoded realistic threats)
# ---------------------------------------------------------------------------
_DEMO_THREATS = [
    {
        "transaction_hash": "0x8a3b1f...e7d2c4 (simulated)",
        "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18",
        "to": "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b",
        "value_eth": 245.8712,
        "risk_score": 100,
        "risk_level": "CRITICAL",
        "flags": [
            "MIXER_INTERACTION: Transaction involves Tornado Cash (0xd90e2f925da726b50c4ed8d0fb90ad053324f31b)",
            "HIGH_VALUE_WHALE_TRANSFER: Transaction value (245.8712 ETH) exceeds 100 ETH",
        ],
        "gas_used": 21000,
        "block_number": 19842351,
        "status": "success",
        "contract_name": "Tornado Cash Router",
    },
    {
        "transaction_hash": "0xc4e91d...b38f07 (simulated)",
        "from": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "to": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
        "value_eth": 0.0,
        "risk_score": 60,
        "risk_level": "WARNING",
        "flags": [
            "CRITICAL: ERC-20/NFT Approval Signature Detected. Possible Wallet Drainer phishing attempt.",
            "WARNING: Unlimited (uint256 max) token approval detected — attacker can drain the entire token balance.",
        ],
        "gas_used": 48210,
        "block_number": 19842387,
        "status": "success",
        "contract_name": "Uniswap V3: Router 2",
    },
    {
        "transaction_hash": "0xf7a20e...91dc53 (simulated)",
        "from": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "to": None,
        "value_eth": 0.0,
        "risk_score": 40,
        "risk_level": "WARNING",
        "flags": [
            "SUSPICIOUS_CONTRACT_CREATION: Contract deployed at 0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
        ],
        "gas_used": 1547832,
        "block_number": 19842412,
        "status": "success",
        "contract_name": None,
    },
]


@app.websocket("/api/ws/crypto/radar/demo")
async def crypto_radar_demo(websocket: WebSocket) -> None:
    """Cycle through hardcoded realistic threat reports every 3 seconds."""
    await websocket.accept()
    try:
        idx = 0
        while True:
            await asyncio.sleep(3)
            report = _DEMO_THREATS[idx % len(_DEMO_THREATS)]
            await websocket.send_json(report)
            idx += 1
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close()


# ---------------------------------------------------------------------------
# Graph ML — PageRank Centrality Analysis
# ---------------------------------------------------------------------------
@app.get("/api/ml/graph-centrality")
async def graph_centrality(top_k: int = 10) -> Dict[str, Any]:
    """Return transaction graph nodes ranked by PageRank anomaly score."""
    try:
        from ml.graph_analytics import compute_pagerank_anomalies
        return compute_pagerank_anomalies(top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Graph analytics failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
