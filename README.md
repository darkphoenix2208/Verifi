# 🛡️ FraudGuardian

> **An End-to-End AI-Powered Banking Security & Fraud Prevention Ecosystem**  
> **Author:** darkphoenix2208

FraudGuardian is a comprehensive security suite designed for financial institutions to detect, investigate, and prevent fraudulent activities across multiple attack vectors. It utilizes state-of-the-art Machine Learning, Computer Vision, and Generative AI to secure the entire banking pipeline—from customer onboarding to transaction monitoring and internal employee risk assessment.

## 🌟 Key Features

### 1. 💳 Transaction Fraud Detection
- **Real-time Evaluation:** Analyzes transaction parameters (amount, location, frequency) using a sophisticated Machine Learning pipeline, streamed via WebSockets.
- **Feature Engineering:** Calculates advanced metrics like merchant distance and time-based spending frequencies to accurately score fraud probability.

### 2. 🕵️‍♂️ Behavioral Anomaly Detection
- **Soft-Data Monitoring:** Tracks user interactions such as session length, click rates, device changes, and failed logins.
- **Gaussian Mixture Models (GMM):** Compares live behavior against historical baselines to detect account hijackings and unusual behavioral patterns before a transaction even occurs.

### 3. 🤖 AI Investigator Agent
- **GenAI Integration:** Powered by Google Gemini (`gemini-2.0-flash`).
- **Automated Summarization:** When an anomaly or fraud is flagged, the agent instantly ingests the customer's historical profile and generates an actionable investigation report for human analysts, directly accessible from the Core Banking dashboard.

### 4. 🏢 Insider Threat Management (Employee Risk)
- **Internal Monitoring:** A dedicated dashboard for tracking employee behavior (e.g., manual overrides, abnormal working hours).
- **Predictive Risk Scoring:** Uses a trained Random Forest model to calculate risk scores and identify the top contributing factors for suspicious internal activities using live API endpoints.

### 5. 👁️ KYC Biometric Verification
- **Liveness Detection:** Employs computer vision (MediaPipe) to track facial landmarks and calculate Eye Aspect Ratio (EAR) to ensure the user is physically present (e.g., actively blinking).
- **Identity Matching:** Uses DeepFace to mathematically compare the live webcam selfie against an uploaded identification document (like an Aadhaar card) to prevent identity theft.

## 🛠️ Tech Stack

- **Frontend:** React, TypeScript, Vite, TailwindCSS, Recharts
- **Backend API:** FastAPI, Uvicorn, WebSockets
- **Machine Learning:** Scikit-Learn, Pandas, NumPy
- **Generative AI:** Google Gemini, LangChain
- **Computer Vision:** OpenCV, MediaPipe, DeepFace

## 📂 Project Structure

```text
FraudGuardian/
│
├── api.py                      # Unified FastAPI Backend Server
├── Frontend/                   # React + Vite Frontend Application
│   ├── src/                    # UI Components (Core Banking, Employee Risk, KYC)
│   └── package.json            # Node.js dependencies
├── Transactions/               # ML Pipeline & Feature Engineering for transactions
├── Agent/                      # GenAI investigation integration & customer profiles
├── Customer Behavior/          # GMM models & anomaly tracking logs
├── KYC/                        # Legacy KYC scripts
└── README.md                   # Project documentation
```

## 🚀 Getting Started

### Prerequisites

- **Python 3.8+**
- **Node.js 18+**
- **Google Gemini API Key**

### 1. Backend Setup (FastAPI)

1. Open a terminal in the root directory.
2. Install the required Python dependencies:
   ```bash
   pip install fastapi uvicorn pydantic pandas numpy scikit-learn matplotlib seaborn opencv-python mediapipe deepface langchain langchain-google-genai scipy python-multipart
   ```
3. Set your Google Gemini API key:
   ```bash
   # On Windows (Command Prompt):
   set GOOGLE_API_KEY="your_api_key_here"
   # On Windows (PowerShell):
   $env:GOOGLE_API_KEY="your_api_key_here"
   # On macOS/Linux:
   export GOOGLE_API_KEY="your_api_key_here"
   ```
4. Start the backend server:
   ```bash
   python api.py
   ```
   *(The API will run on `http://localhost:8000`)*

### 2. Frontend Setup (React + Vite)

1. Open a **new** terminal in the `Frontend` directory:
   ```bash
   cd Frontend
   ```
2. Install the Node.js dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```
   *(The frontend will be accessible in your browser, typically at `http://localhost:5173`)*

---

*Built to secure the future of finance.*