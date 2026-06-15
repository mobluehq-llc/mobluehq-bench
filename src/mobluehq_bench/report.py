"""Signed benchmark results receipt and shareable results page."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import nacl.signing

from mobluehq_bench.receipt import canonical_json

RESULTS_SCHEMA_VERSION = "mobluehq-bench-results-v1"
_BENCH_SIGNING_KEY = nacl.signing.SigningKey(
    hashlib.sha256(b"mobluehq-bench-results-signing-v1").digest()
)


def _results_body(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "results_schema_version": RESULTS_SCHEMA_VERSION,
        "run_id": payload["run_id"],
        "bench_version": payload["bench_version"],
        "seed": payload["seed"],
        "rail_adapter": payload["rail_adapter"],
        "baseline_adapter": payload["baseline_adapter"],
        "metrics": payload["metrics"],
        "manifest_version": payload["manifest_version"],
        "content_hash": hashlib.sha256(
            json.dumps(payload["items"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }


def sign_results_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    body = _results_body(payload)
    message = canonical_json(body)
    signature = _BENCH_SIGNING_KEY.sign(message).signature
    signer_pub = (
        base64.urlsafe_b64encode(bytes(_BENCH_SIGNING_KEY.verify_key)).decode("ascii").rstrip("=")
    )
    return {
        **body,
        "signed_at": datetime.now(UTC).isoformat(),
        "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        "signer_pub": signer_pub,
    }


def verify_results_receipt(receipt: dict[str, Any]) -> bool:
    if receipt.get("results_schema_version") != RESULTS_SCHEMA_VERSION:
        return False
    pub_b64 = str(receipt["signer_pub"])
    padding = "=" * (-len(pub_b64) % 4)
    public_key = base64.urlsafe_b64decode(pub_b64 + padding)
    sig_b64 = str(receipt["signature"])
    sig_padding = "=" * (-len(sig_b64) % 4)
    signature = base64.urlsafe_b64decode(sig_b64 + sig_padding)
    verify_key = nacl.signing.VerifyKey(public_key)
    body = {
        "results_schema_version": receipt["results_schema_version"],
        "run_id": receipt["run_id"],
        "bench_version": receipt["bench_version"],
        "seed": receipt["seed"],
        "rail_adapter": receipt["rail_adapter"],
        "baseline_adapter": receipt["baseline_adapter"],
        "metrics": receipt["metrics"],
        "manifest_version": receipt["manifest_version"],
        "content_hash": receipt["content_hash"],
    }
    try:
        verify_key.verify(canonical_json(body), signature)
        return True
    except Exception:
        return False


def _pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100.0 * value:.1f}%"


def _float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def write_results_page(output_dir: Path, payload: dict[str, Any], receipt: dict[str, Any]) -> None:
    m = payload["metrics"]
    lines = [
        "# MOBLUEHQ Process-Integrity Benchmark — Results",
        "",
        f"**Run ID:** `{payload['run_id']}`  ",
        f"**Seed:** `{payload['seed']}`  ",
        f"**Rail:** `{payload['rail_adapter']}`  ",
        f"**Baseline:** `{payload['baseline_adapter']}`  ",
        "",
        "## Headline metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Verified Answer Rate | {_pct(m['verified_answer_rate'])} |",
        f"| Dissent catches wrong (AUROC) | {_float(m['dissent_auroc'])} |",
        f"| Selective accuracy (rail) | {_pct(m['selective_accuracy_rail'])} |",
        f"| Selective accuracy (baseline) | {_pct(m['selective_accuracy_baseline'])} |",
        f"| Selective accuracy Δ (rail − baseline) | {_pct(m['selective_accuracy_delta'])} |",
        f"| ECE (rail) | {_float(m['ece_rail'])} |",
        f"| ECE (baseline) | {_float(m['ece_baseline'])} |",
        f"| Unanimous-wrong residual | {m['unanimous_wrong_count']} ({_pct(m['unanimous_wrong_rate'])}) |",
        "",
        "## Coverage",
        "",
        f"- Items scored: **{m['total_items']}**",
        f"- Rail answered: **{m['rail_answered']}** (escalated/abstained: **{m['rail_escalated']}**)",
        f"- Baseline answered: **{m['baseline_answered']}**",
        "",
        "## Honest limits",
        "",
        "This benchmark measures **knowing when it is wrong** — verified delivery, dissent as an error signal,",
        "selective accuracy after abstention, and calibration — not raw leaderboard capability.",
        "",
        f"**Unanimous-wrong residual:** {m['unanimous_wrong_count']} cases where the council agreed",
        "(zero dissent) but the delivered answer was still incorrect. Process integrity does not eliminate",
        "consensus errors; it reduces exposure by abstaining when dissent fires.",
        "",
        "## Datasets",
        "",
    ]
    for ds in payload["datasets"]:
        lines.append(
            f"- **{ds['name']}** — [{ds['source_url']}]({ds['source_url']}) ({ds['license']})"
        )
    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            "```bash",
            "pip install -e .",
            f"bench run --rail {payload['rail_adapter']} --baseline {payload['baseline_adapter']} "
            f"--seed {payload['seed']} --output results/runs/{payload['run_id']}",
            "```",
            "",
            f"Signed receipt: `results.receipt.json` (schema `{RESULTS_SCHEMA_VERSION}`).",
            "",
        ]
    )
    (output_dir / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")

    headline = {
        "run_id": payload["run_id"],
        "verified_answer_rate": m["verified_answer_rate"],
        "dissent_auroc": m["dissent_auroc"],
        "selective_accuracy_rail": m["selective_accuracy_rail"],
        "selective_accuracy_baseline": m["selective_accuracy_baseline"],
        "selective_accuracy_delta": m["selective_accuracy_delta"],
        "ece_rail": m["ece_rail"],
        "unanimous_wrong_count": m["unanimous_wrong_count"],
        "receipt_valid": verify_results_receipt(receipt),
    }
    headline_path = output_dir / "headline.json"
    with headline_path.open("w", encoding="utf-8") as f:
        json.dump(headline, f, indent=2, sort_keys=True)
        f.write("\n")
