"""Benchmark run orchestration."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mobluehq_bench.adapters import resolve_baseline_adapter, resolve_rail_adapter
from mobluehq_bench.datasets import dataset_licenses, load_all_datasets, load_manifest
from mobluehq_bench.metrics import compute_metrics
from mobluehq_bench.report import sign_results_receipt, write_results_page
from mobluehq_bench.types import ScoredItem


def run_benchmark(
    *,
    rail_spec: str,
    baseline_spec: str,
    output_dir: Path,
    seed: int = 42,
    max_samples: int | None = None,
) -> dict[str, Any]:
    """Score rail vs baseline on public fixture slices."""
    items = load_all_datasets(max_samples=max_samples)
    rail = resolve_rail_adapter(rail_spec, seed=seed)
    baseline = resolve_baseline_adapter(baseline_spec, seed=seed)

    scored: list[ScoredItem] = []
    for item in items:
        scored.append(
            ScoredItem(
                item=item,
                rail=rail.answer(item),
                baseline=baseline.answer(item),
            )
        )

    metrics = compute_metrics(scored)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)

    per_item = []
    for s in scored:
        per_item.append(
            {
                "id": s.item.id,
                "dataset": s.item.dataset,
                "ground_truth": s.item.ground_truth,
                "rail": {
                    "answer": s.rail.answer,
                    "correct": s.rail.correct,
                    "confidence": s.rail.confidence,
                    "receipt_valid": s.rail.receipt_valid,
                    "escalated": s.rail.escalated,
                    "abstained": s.rail.abstained,
                    "dissent_count": s.rail.dissent_count,
                    "council_consensus": s.rail.council_consensus,
                },
                "baseline": {
                    "answer": s.baseline.answer,
                    "correct": s.baseline.correct,
                    "confidence": s.baseline.confidence,
                },
            }
        )

    manifest = load_manifest()
    payload = {
        "bench_version": "0.1.0",
        "run_id": run_id,
        "seed": seed,
        "rail_adapter": rail_spec,
        "baseline_adapter": baseline_spec,
        "datasets": dataset_licenses(),
        "manifest_version": manifest["version"],
        "metrics": metrics.to_dict(),
        "items": per_item,
    }

    results_path = output_dir / "results.json"
    with results_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")

    receipt = sign_results_receipt(payload)
    receipt_path = output_dir / "results.receipt.json"
    with receipt_path.open("w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write("\n")

    write_results_page(output_dir, payload, receipt)
    return payload
