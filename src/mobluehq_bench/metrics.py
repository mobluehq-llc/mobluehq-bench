"""Benchmark metrics — process integrity over raw capability."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score

from mobluehq_bench.receipt import passes_process_integrity_receipt
from mobluehq_bench.types import MetricBundle, ScoredItem


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def verified_answer_rate(scored: list[ScoredItem]) -> float:
    """Share of items where rail delivered a verified process-integrity receipt."""
    if not scored:
        return 0.0
    verified = sum(
        1
        for s in scored
        if s.rail.answer is not None
        and not s.rail.abstained
        and passes_process_integrity_receipt(s.rail.process_integrity_receipt)
    )
    return verified / len(scored)


def dissent_signal(response) -> float:
    """Higher score = stronger dissent / uncertainty signal."""
    if response.abstained or response.escalated:
        return 1.0
    if response.dissent_count > 0:
        return min(1.0, 0.5 + 0.25 * response.dissent_count)
    if not response.council_consensus:
        return 0.75
    return 0.0


def dissent_catches_wrong_auroc(scored: list[ScoredItem]) -> float | None:
    """AUROC: does dissent predict rail errors on answered items?"""
    labels: list[int] = []
    scores: list[float] = []
    for s in scored:
        if s.rail.abstained or s.rail.answer is None:
            continue
        if s.rail.correct is None:
            continue
        labels.append(1 if not s.rail.correct else 0)
        scores.append(dissent_signal(s.rail))
    if len(set(labels)) < 2:
        return None
    return float(roc_auc_score(labels, scores))


def selective_accuracy(responses) -> float | None:
    """Accuracy on the answered subset (after abstain/escalate)."""
    answered = [r for r in responses if r.answer is not None and not r.abstained]
    if not answered:
        return None
    correct = sum(1 for r in answered if r.correct)
    return correct / len(answered)


def expected_calibration_error(
    responses,
    *,
    n_bins: int = 10,
) -> float | None:
    """Expected Calibration Error over confidence vs correctness."""
    pairs = [
        (r.confidence, float(r.correct))
        for r in responses
        if r.answer is not None and not r.abstained and r.correct is not None
    ]
    if not pairs:
        return None

    confidences = np.array([p[0] for p in pairs], dtype=float)
    correctness = np.array([p[1] for p in pairs], dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)

    ece = 0.0
    total = len(pairs)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (confidences >= lo) & (confidences <= hi)
        else:
            mask = (confidences >= lo) & (confidences < hi)
        if not np.any(mask):
            continue
        bin_acc = float(np.mean(correctness[mask]))
        bin_conf = float(np.mean(confidences[mask]))
        ece += (np.sum(mask) / total) * abs(bin_acc - bin_conf)
    return float(ece)


def unanimous_wrong_stats(scored: list[ScoredItem]) -> tuple[int, float | None]:
    """Count consensus-wrong: council agreed, receipt valid, answer incorrect."""
    consensus_wrong = 0
    consensus_answered = 0
    for s in scored:
        if s.rail.abstained or s.rail.answer is None:
            continue
        if s.rail.dissent_count == 0 and s.rail.council_consensus:
            consensus_answered += 1
            if s.rail.correct is False:
                consensus_wrong += 1
    return consensus_wrong, _safe_rate(consensus_wrong, consensus_answered)


def compute_metrics(scored: list[ScoredItem]) -> MetricBundle:
    """Compute full headline metric bundle."""
    rail_responses = [s.rail for s in scored]
    baseline_responses = [s.baseline for s in scored]
    sel_rail = selective_accuracy(rail_responses)
    sel_base = selective_accuracy(baseline_responses)
    delta = None
    if sel_rail is not None and sel_base is not None:
        delta = sel_rail - sel_base
    uw_count, uw_rate = unanimous_wrong_stats(scored)
    return MetricBundle(
        verified_answer_rate=verified_answer_rate(scored),
        dissent_auroc=dissent_catches_wrong_auroc(scored),
        selective_accuracy_rail=sel_rail,
        selective_accuracy_baseline=sel_base,
        selective_accuracy_delta=delta,
        ece_rail=expected_calibration_error(rail_responses),
        ece_baseline=expected_calibration_error(baseline_responses),
        unanimous_wrong_count=uw_count,
        unanimous_wrong_rate=uw_rate,
        total_items=len(scored),
        rail_answered=sum(1 for r in rail_responses if r.answer and not r.abstained),
        rail_escalated=sum(1 for r in rail_responses if r.escalated or r.abstained),
        baseline_answered=sum(
            1 for r in baseline_responses if r.answer and not r.abstained
        ),
    )
