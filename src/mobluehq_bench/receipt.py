"""Process-integrity receipt verification (bench-local, schema-compatible)."""

from __future__ import annotations

import base64
import json
from typing import Any

import nacl.exceptions
import nacl.signing

PROCESS_INTEGRITY_SCHEMA_VERSION = "process-integrity-v1"

COMPONENT_NAMES = (
    "source_capture",
    "dissent_check",
    "evidence_trace",
    "replay_bundle",
    "policy_compliance",
    "escalation_decision",
)


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def receipt_body(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "receipt_schema_version": receipt["receipt_schema_version"],
        "job_id": receipt["job_id"],
        "tenant_id": receipt["tenant_id"],
        **{name: receipt[name] for name in COMPONENT_NAMES},
        "legacy_receipt_hash": receipt.get("legacy_receipt_hash", ""),
        "verdict": receipt.get("verdict", ""),
    }


def verify_process_integrity_receipt(
    receipt: dict[str, Any],
    *,
    expected_public_key: bytes | None = None,
) -> bool:
    """Verify Ed25519 signature on a process-integrity receipt."""
    if receipt.get("receipt_schema_version") != PROCESS_INTEGRITY_SCHEMA_VERSION:
        return False
    for name in COMPONENT_NAMES:
        if name not in receipt:
            return False

    pub_b64 = str(receipt["signer_pub"])
    padding = "=" * (-len(pub_b64) % 4)
    public_key = base64.urlsafe_b64decode(pub_b64 + padding)
    if expected_public_key is not None and public_key != expected_public_key:
        return False

    sig_b64 = str(receipt["signature"])
    sig_padding = "=" * (-len(sig_b64) % 4)
    signature = base64.urlsafe_b64decode(sig_b64 + sig_padding)
    verify_key = nacl.signing.VerifyKey(public_key)
    try:
        verify_key.verify(canonical_json(receipt_body(receipt)), signature)
        return True
    except nacl.exceptions.BadSignatureError:
        return False


def passes_process_integrity_receipt(receipt: dict[str, Any] | None) -> bool:
    """True when receipt exists, schema is complete, and signature verifies."""
    if not receipt:
        return False
    return verify_process_integrity_receipt(receipt)
