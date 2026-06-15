"""Shared types for benchmark runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkItem:
    """One scored question from a public dataset slice."""

    id: str
    dataset: str
    question: str
    context: tuple[str, ...]
    ground_truth: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """Normalized response from rail or baseline adapter."""

    answer: str | None
    confidence: float
    correct: bool | None
    process_integrity_receipt: dict[str, Any] | None = None
    receipt_valid: bool = False
    escalated: bool = False
    abstained: bool = False
    dissent_count: int = 0
    council_consensus: bool = True
    verdict: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredItem:
    """Ground-truth item paired with rail + baseline responses."""

    item: BenchmarkItem
    rail: ModelResponse
    baseline: ModelResponse


@dataclass
class MetricBundle:
    """Headline metrics for a benchmark run."""

    verified_answer_rate: float
    dissent_auroc: float | None
    selective_accuracy_rail: float | None
    selective_accuracy_baseline: float | None
    selective_accuracy_delta: float | None
    ece_rail: float | None
    ece_baseline: float | None
    unanimous_wrong_count: int
    unanimous_wrong_rate: float | None
    total_items: int
    rail_answered: int
    rail_escalated: int
    baseline_answered: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "verified_answer_rate": self.verified_answer_rate,
            "dissent_auroc": self.dissent_auroc,
            "selective_accuracy_rail": self.selective_accuracy_rail,
            "selective_accuracy_baseline": self.selective_accuracy_baseline,
            "selective_accuracy_delta": self.selective_accuracy_delta,
            "ece_rail": self.ece_rail,
            "ece_baseline": self.ece_baseline,
            "unanimous_wrong_count": self.unanimous_wrong_count,
            "unanimous_wrong_rate": self.unanimous_wrong_rate,
            "total_items": self.total_items,
            "rail_answered": self.rail_answered,
            "rail_escalated": self.rail_escalated,
            "baseline_answered": self.baseline_answered,
        }
