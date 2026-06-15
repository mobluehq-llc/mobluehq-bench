"""Metric computation tests against a fixed fixture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mobluehq_bench.metrics import (
    compute_metrics,
    dissent_catches_wrong_auroc,
    expected_calibration_error,
    selective_accuracy,
    verified_answer_rate,
)
from mobluehq_bench.receipt import passes_process_integrity_receipt, verify_process_integrity_receipt
from mobluehq_bench.report import sign_results_receipt, verify_results_receipt
from mobluehq_bench.types import BenchmarkItem, ModelResponse, ScoredItem

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "metric_cases.json"


def _load_fixture() -> list[ScoredItem]:
    with FIXTURE_PATH.open(encoding="utf-8") as f:
        raw = json.load(f)
    scored: list[ScoredItem] = []
    for row in raw:
        item = BenchmarkItem(
            id=row["id"],
            dataset=row["dataset"],
            question=row["question"],
            context=tuple(row.get("context", [])),
            ground_truth=row["ground_truth"],
        )

        def _resp(side: dict) -> ModelResponse:
            return ModelResponse(
                answer=side.get("answer"),
                confidence=float(side["confidence"]),
                correct=side.get("correct"),
                process_integrity_receipt=side.get("process_integrity_receipt"),
                receipt_valid=bool(side.get("receipt_valid", False)),
                escalated=bool(side.get("escalated", False)),
                abstained=bool(side.get("abstained", False)),
                dissent_count=int(side.get("dissent_count", 0)),
                council_consensus=bool(side.get("council_consensus", True)),
            )

        scored.append(ScoredItem(item=item, rail=_resp(row["rail"]), baseline=_resp(row["baseline"])))
    return scored


def test_verified_answer_rate_fixture():
    from mobluehq_bench.adapters import MockBaselineAdapter, MockRailAdapter

    adapter = MockRailAdapter(seed=99)
    baseline = MockBaselineAdapter(seed=99)
    items = [
        BenchmarkItem(id=f"v-{i}", dataset="truthfulqa", question=f"Q{i}", context=(), ground_truth="ok")
        for i in range(10)
    ]
    scored = [
        ScoredItem(item=item, rail=adapter.answer(item), baseline=baseline.answer(item))
        for item in items
    ]
    var = verified_answer_rate(scored)
    assert 0.0 < var < 1.0


def test_verified_answer_rate_counts_valid_receipts():
    scored = _load_fixture()
    verified = sum(
        1
        for s in scored
        if s.rail.answer is not None
        and not s.rail.abstained
        and s.rail.receipt_valid
    )
    assert verified == 3


def test_dissent_auroc_fixture():
    scored = _load_fixture()
    auroc = dissent_catches_wrong_auroc(scored)
    assert auroc is not None
    # Dissent score ranks the dissenting wrong case above consensus-wrong + correct.
    assert auroc >= 0.5


def test_selective_accuracy_fixture():
    scored = _load_fixture()
    rail_acc = selective_accuracy([s.rail for s in scored])
    base_acc = selective_accuracy([s.baseline for s in scored])
    # Rail abstains on case-3; answered subset is 4 items, 2 correct.
    assert rail_acc == pytest.approx(0.5)
    assert base_acc == pytest.approx(0.6)


def test_ece_computation():
    responses = [
        ModelResponse(answer="a", confidence=0.9, correct=True),
        ModelResponse(answer="b", confidence=0.9, correct=False),
        ModelResponse(answer="c", confidence=0.1, correct=False),
    ]
    ece = expected_calibration_error(responses, n_bins=2)
    assert ece is not None
    assert ece > 0.0


def test_compute_metrics_bundle():
    scored = _load_fixture()
    metrics = compute_metrics(scored)
    assert metrics.total_items == 5
    assert metrics.unanimous_wrong_count == 1
    assert metrics.selective_accuracy_delta == pytest.approx(0.5 - 0.6)


def test_mock_receipt_roundtrip():
    from mobluehq_bench.adapters import MockRailAdapter

    adapter = MockRailAdapter(seed=42)
    item = BenchmarkItem(
        id="test-1",
        dataset="truthfulqa",
        question="What is 2+2?",
        context=(),
        ground_truth="4",
    )
    resp = adapter.answer(item)
    assert resp.process_integrity_receipt is not None
    assert verify_process_integrity_receipt(resp.process_integrity_receipt)
    assert passes_process_integrity_receipt(resp.process_integrity_receipt) == resp.receipt_valid


def test_results_receipt_sign_verify():
    payload = {
        "bench_version": "0.1.0",
        "run_id": "test-run",
        "seed": 42,
        "rail_adapter": "mock-rail",
        "baseline_adapter": "mock-baseline",
        "manifest_version": "0.1.0",
        "metrics": {"verified_answer_rate": 0.5},
        "items": [{"id": "x"}],
    }
    receipt = sign_results_receipt(payload)
    assert verify_results_receipt(receipt)
