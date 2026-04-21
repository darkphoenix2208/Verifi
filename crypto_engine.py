"""
crypto_engine.py — Ethereum Transaction Risk Analysis Engine

Connects to Ethereum Mainnet via an Alchemy HTTP provider and runs
heuristic-based risk analysis on individual transactions.

Environment Variables:
    ALCHEMY_URL: Full Alchemy HTTP endpoint for Ethereum Mainnet.

Author: darkphoenix2208
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from web3 import Web3
from web3.exceptions import TransactionNotFound


# ---------------------------------------------------------------------------
# Known malicious / high-risk addresses (lowercase for comparison)
# ---------------------------------------------------------------------------
TORNADO_CASH_ADDRESS = "0xd90e2f925DA726b50C4Ed8D0Fb90Ad053324F31b".lower()

# ---------------------------------------------------------------------------
# Risk thresholds
# ---------------------------------------------------------------------------
HIGH_VALUE_THRESHOLD_ETH = 100  # Flag transfers above 100 ETH
RISK_SCORE_CAP = 100

# ---------------------------------------------------------------------------
# ERC-20 / ERC-721 approval function selectors (first 4 bytes of keccak)
# ---------------------------------------------------------------------------
APPROVE_SELECTOR = "0x095ea7b3"            # approve(address,uint256)
SET_APPROVAL_FOR_ALL_SELECTOR = "0xa22cb465"  # setApprovalForAll(address,bool)

# Infinite approval sentinel (2**256 - 1 encoded as 64-char hex)
INFINITE_APPROVAL_VALUE = "f" * 64


def _get_web3() -> Web3:
    """Initialise and return a Web3 instance connected to Alchemy."""
    alchemy_url = os.environ.get("ALCHEMY_URL", "")
    if not alchemy_url:
        raise ConnectionError(
            "ALCHEMY_URL environment variable is not set. "
            "Please provide a valid Alchemy HTTP endpoint."
        )
    w3 = Web3(Web3.HTTPProvider(alchemy_url))
    if not w3.is_connected():
        raise ConnectionError(
            "Unable to connect to Ethereum Mainnet via the provided ALCHEMY_URL."
        )
    return w3


def analyze_eth_transaction(tx_hash: str) -> Dict[str, Any]:
    """
    Pull an Ethereum transaction by hash and evaluate it against a set of
    security heuristics.

    Parameters
    ----------
    tx_hash : str
        The 0x-prefixed transaction hash to analyse.

    Returns
    -------
    dict
        Structured risk report containing:
        - transaction_hash
        - from
        - to
        - value_eth
        - risk_score   (0-100, capped)
        - risk_level   (SAFE | WARNING | CRITICAL)
        - flags        (list of triggered heuristic descriptions)
    """

    # ------------------------------------------------------------------
    # 1. Connect to Ethereum
    # ------------------------------------------------------------------
    try:
        w3 = _get_web3()
    except ConnectionError as exc:
        return _error_response(tx_hash, str(exc))

    # ------------------------------------------------------------------
    # 2. Fetch transaction & receipt
    # ------------------------------------------------------------------
    try:
        tx = w3.eth.get_transaction(tx_hash)
    except TransactionNotFound:
        return _error_response(tx_hash, f"Transaction {tx_hash} not found on-chain.")
    except Exception as exc:
        return _error_response(tx_hash, f"Failed to fetch transaction: {exc}")

    try:
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as exc:
        return _error_response(tx_hash, f"Failed to fetch transaction receipt: {exc}")

    # ------------------------------------------------------------------
    # 3. Extract core fields
    # ------------------------------------------------------------------
    from_addr: str = tx.get("from", "")
    to_addr = tx.get("to")  # None for contract creation
    value_wei: int = tx.get("value", 0)
    value_eth: float = float(Web3.from_wei(value_wei, "ether"))

    # ------------------------------------------------------------------
    # 4. Run risk heuristics
    # ------------------------------------------------------------------
    risk_score: int = 0
    flags: List[str] = []

    # Heuristic 1: Mixer Interaction (Tornado Cash)
    from_lower = from_addr.lower() if from_addr else ""
    to_lower = to_addr.lower() if to_addr else ""

    if from_lower == TORNADO_CASH_ADDRESS or to_lower == TORNADO_CASH_ADDRESS:
        risk_score += 80
        flags.append(
            "MIXER_INTERACTION: Transaction involves Tornado Cash "
            f"({TORNADO_CASH_ADDRESS})"
        )

    # Heuristic 2: High-Value Whale Transfer
    if value_eth > HIGH_VALUE_THRESHOLD_ETH:
        risk_score += 30
        flags.append(
            f"HIGH_VALUE_WHALE_TRANSFER: Transaction value "
            f"({value_eth:.4f} ETH) exceeds {HIGH_VALUE_THRESHOLD_ETH} ETH"
        )

    # Heuristic 3: Suspicious Contract Creation
    if to_addr is None:
        risk_score += 40
        contract_address = receipt.get("contractAddress", "unknown")
        flags.append(
            f"SUSPICIOUS_CONTRACT_CREATION: Contract deployed at "
            f"{contract_address}"
        )

    # Heuristic 4: Wallet Drainer — ERC-20 / ERC-721 Approval Phishing
    raw_input = tx.get("input", b"")
    input_data: str = Web3.to_hex(raw_input).lower() if raw_input else ""

    if input_data.startswith(APPROVE_SELECTOR) or input_data.startswith(
        SET_APPROVAL_FOR_ALL_SELECTOR
    ):
        risk_score += 60
        if input_data.startswith(APPROVE_SELECTOR):
            detected_fn = "approve(address,uint256)"
        else:
            detected_fn = "setApprovalForAll(address,bool)"

        flags.append(
            "CRITICAL: ERC-20/NFT Approval Signature Detected. "
            "Possible Wallet Drainer phishing attempt."
        )

        # Sub-signal: check for infinite / extremely high approval value
        # approve calldata: 4-byte selector + 32-byte address + 32-byte value
        if (
            input_data.startswith(APPROVE_SELECTOR)
            and len(input_data) >= 138  # 0x + 4-byte sel + 64 + 64
            and input_data[74:138] == INFINITE_APPROVAL_VALUE
        ):
            flags.append(
                "WARNING: Unlimited (uint256 max) token approval detected — "
                "attacker can drain the entire token balance."
            )

    # Cap the risk score
    risk_score = min(risk_score, RISK_SCORE_CAP)

    # ------------------------------------------------------------------
    # 5. Determine risk level
    # ------------------------------------------------------------------
    if risk_score >= 70:
        risk_level = "CRITICAL"
    elif risk_score >= 30:
        risk_level = "WARNING"
    else:
        risk_level = "SAFE"

    # ------------------------------------------------------------------
    # 6. Build and return the structured report
    # ------------------------------------------------------------------
    return {
        "transaction_hash": tx_hash,
        "from": from_addr,
        "to": to_addr if to_addr else None,
        "value_eth": round(value_eth, 6),
        "risk_score": risk_score,
        "risk_level": risk_level,
        "flags": flags,
        "gas_used": receipt.get("gasUsed"),
        "block_number": tx.get("blockNumber"),
        "status": "success" if receipt.get("status") == 1 else "failed",
    }


def _error_response(tx_hash: str, error_message: str) -> Dict[str, Any]:
    """Return a standardised error report when analysis cannot proceed."""
    return {
        "transaction_hash": tx_hash,
        "from": None,
        "to": None,
        "value_eth": 0.0,
        "risk_score": 0,
        "risk_level": "UNKNOWN",
        "flags": [],
        "error": error_message,
    }
