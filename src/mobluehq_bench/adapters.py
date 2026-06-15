"""Model/rail adapters for the benchmark harness."""

from __future__ import annotations

import base64
import hashlib
import re
import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx
import nacl.signing

from mobluehq_bench.receipt import (
    PROCESS_INTEGRITY_SCHEMA_VERSION,
    canonical_json,
    verify_process_integrity_receipt,
)
from mobluehq_bench.types import BenchmarkItem, ModelResponse

_MOCK_SIGNING_KEY = nacl.signing.SigningKey(
    hashlib.sha256(b"mobluehq-bench-mock-v1").digest()
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _answers_match(predicted: str | None, ground_truth: str) -> bool | None:
    if predicted is None:
        return None
    pred = _normalize(predicted)
    truth = _normalize(ground_truth)
    if pred == truth:
        return True
    if truth in pred or pred in truth:
        return True
    return False


def _mock_sign_receipt(body: dict[str, Any]) -> dict[str, Any]:
    message = canonical_json(body)
    signature = _MOCK_SIGNING_KEY.sign(message).signature
    signer_pub = (
        base64.urlsafe_b64encode(bytes(_MOCK_SIGNING_KEY.verify_key)).decode("ascii").rstrip("=")
    )
    return {
        **body,
        "signature": base64.urlsafe_b64encode(signature).decode("ascii").rstrip("="),
        "signer_pub": signer_pub,
    }


class Adapter(ABC):
    @abstractmethod
    def answer(self, item: BenchmarkItem) -> ModelResponse:
        raise NotImplementedError


class MockBaselineAdapter(Adapter):
    """Deterministic single-model baseline — always answers, no abstention."""

    def __init__(self, *, seed: int = 42, error_rate: float = 0.35) -> None:
        self.seed = seed
        self.error_rate = error_rate

    def _hash(self, item_id: str) -> int:
        digest = hashlib.sha256(f"{self.seed}:{item_id}".encode()).hexdigest()
        return int(digest[:8], 16)

    def answer(self, item: BenchmarkItem) -> ModelResponse:
        h = self._hash(item.id)
        wrong = (h % 100) < int(self.error_rate * 100)
        answer = "incorrect answer" if wrong else item.ground_truth
        confidence = 0.55 + (h % 40) / 100.0
        correct = _answers_match(answer, item.ground_truth)
        return ModelResponse(
            answer=answer,
            confidence=min(confidence, 0.99),
            correct=correct,
            receipt_valid=False,
            escalated=False,
            abstained=False,
            dissent_count=0,
            council_consensus=True,
            verdict="baseline",
        )


class MockRailAdapter(Adapter):
    """Deterministic rail mock — abstains on high-risk, signs process-integrity receipts."""

    def __init__(self, *, seed: int = 42, error_rate: float = 0.22) -> None:
        self.seed = seed
        self.error_rate = error_rate

    def _hash(self, item_id: str) -> int:
        digest = hashlib.sha256(f"rail:{self.seed}:{item_id}".encode()).hexdigest()
        return int(digest[:8], 16)

    def answer(self, item: BenchmarkItem) -> ModelResponse:
        h = self._hash(item.id)
        risk_bucket = h % 100
        dissent_count = 0
        council_consensus = True
        escalated = False
        abstained = False

        # Simulate dissent catching some errors before delivery
        if risk_bucket < 18:
            escalated = True
            abstained = True
            receipt = self._build_receipt(
                item,
                verdict="escalated",
                dissent_count=2,
                council_consensus=False,
                escalated=True,
            )
            return ModelResponse(
                answer=None,
                confidence=0.35,
                correct=None,
                process_integrity_receipt=receipt,
                receipt_valid=verify_process_integrity_receipt(receipt),
                escalated=escalated,
                abstained=abstained,
                dissent_count=2,
                council_consensus=False,
                verdict="escalated",
            )

        wrong = risk_bucket < int(self.error_rate * 100) + 18
        if wrong and risk_bucket % 3 == 0:
            dissent_count = 1
            council_consensus = False
            escalated = True
            abstained = True
            receipt = self._build_receipt(
                item,
                verdict="flagged",
                dissent_count=dissent_count,
                council_consensus=False,
                escalated=True,
            )
            return ModelResponse(
                answer=None,
                confidence=0.42,
                correct=None,
                process_integrity_receipt=receipt,
                receipt_valid=verify_process_integrity_receipt(receipt),
                escalated=True,
                abstained=True,
                dissent_count=dissent_count,
                council_consensus=False,
                verdict="flagged",
            )

        answer = "incorrect answer" if wrong else item.ground_truth
        confidence = 0.72 + (h % 25) / 100.0
        if wrong and risk_bucket % 5 != 0:
            dissent_count = 1
            council_consensus = False

        receipt = self._build_receipt(
            item,
            verdict="accepted" if not wrong else "flagged",
            dissent_count=dissent_count,
            council_consensus=council_consensus,
            escalated=False,
        )
        return ModelResponse(
            answer=answer,
            confidence=min(confidence, 0.98),
            correct=_answers_match(answer, item.ground_truth),
            process_integrity_receipt=receipt,
            receipt_valid=verify_process_integrity_receipt(receipt),
            escalated=False,
            abstained=False,
            dissent_count=dissent_count,
            council_consensus=council_consensus,
            verdict=receipt["verdict"],
        )

    def _build_receipt(
        self,
        item: BenchmarkItem,
        *,
        verdict: str,
        dissent_count: int,
        council_consensus: bool,
        escalated: bool,
    ) -> dict[str, Any]:
        job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mock:{item.id}"))
        body = {
            "receipt_schema_version": PROCESS_INTEGRITY_SCHEMA_VERSION,
            "job_id": job_id,
            "tenant_id": "bench-mock",
            "source_capture": {
                "claim": item.question,
                "context": list(item.context),
                "captured_at": datetime.now(UTC).isoformat(),
            },
            "dissent_check": {
                "dissent": ["council-1"] if dissent_count else [],
                "confirmations": ["council-0"],
                "dissent_count": dissent_count,
                "council_consensus": council_consensus,
            },
            "evidence_trace": {
                "what_was_checked": ["grounding_gate", "council"],
                "grounding_passed": True,
                "evidence_hash": hashlib.sha256(item.question.encode()).hexdigest()[:16],
            },
            "replay_bundle": {
                "claim": item.question,
                "context": list(item.context),
                "policy": {"version": "bench-v1"},
                "fixture_id": item.id,
                "doer_index": 0,
                "council_members": ["council-0", "council-1"],
            },
            "policy_compliance": {
                "policy_version": "bench-v1",
                "grounding_gate_passed": True,
                "compliance_tests": ["grounding"],
                "verdict": verdict,
            },
            "escalation_decision": {
                "escalated": escalated,
                "reason": "dissent_threshold" if escalated else None,
                "dissent_threshold": 1,
                "dissent_count": dissent_count,
            },
            "legacy_receipt_hash": hashlib.sha256(job_id.encode()).hexdigest(),
            "verdict": verdict,
        }
        return _mock_sign_receipt(body)


class HttpRailAdapter(Adapter):
    """Call a live blueCheck rail /v1/verify endpoint."""

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        tenant_id: str = "mobluehq-bench",
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.tenant_id = tenant_id
        self.timeout = timeout

    def answer(self, item: BenchmarkItem) -> ModelResponse:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "tenant_id": self.tenant_id,
            "claim": item.question,
            "context": list(item.context),
            "policy": {"version": "bench-v1"},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/v1/verify", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        pi = data.get("process_integrity_receipt")
        escalation = (pi or {}).get("escalation_decision", {})
        dissent = (pi or {}).get("dissent_check", {})
        escalated = bool(escalation.get("escalated"))
        answer = data.get("answer")
        abstained = escalated or answer is None
        receipt_valid = bool(pi and verify_process_integrity_receipt(pi))
        return ModelResponse(
            answer=answer,
            confidence=float(data.get("confidence", 0.5)),
            correct=_answers_match(answer, item.ground_truth) if answer else None,
            process_integrity_receipt=pi,
            receipt_valid=receipt_valid,
            escalated=escalated,
            abstained=abstained,
            dissent_count=int(dissent.get("dissent_count", 0)),
            council_consensus=bool(dissent.get("council_consensus", True)),
            verdict=data.get("verdict"),
            raw=data,
        )


class OpenAICompatibleBaseline(Adapter):
    """Single-model baseline via OpenAI-compatible chat completions API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def answer(self, item: BenchmarkItem) -> ModelResponse:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        context_block = "\n".join(item.context)
        user_content = item.question
        if context_block:
            user_content = f"Context:\n{context_block}\n\nQuestion: {item.question}"
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Answer concisely with the best short factual answer.",
                },
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.0,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
        choice = data["choices"][0]["message"]["content"].strip()
        logprobs = data["choices"][0].get("logprobs")
        confidence = 0.75
        if logprobs and logprobs.get("content"):
            # crude proxy when logprobs available
            confidence = 0.85
        return ModelResponse(
            answer=choice,
            confidence=confidence,
            correct=_answers_match(choice, item.ground_truth),
            verdict="baseline",
            raw=data,
        )


def resolve_adapter(spec: str, *, seed: int = 42) -> Adapter:
    """Parse adapter spec: mock-rail | mock-baseline | http://... | openai://host/model."""
    lowered = spec.strip().lower()
    if lowered.startswith("mock-rail"):
        return MockRailAdapter(seed=seed)
    if lowered.startswith("mock-baseline"):
        return MockBaselineAdapter(seed=seed)

    if spec.startswith("http://") or spec.startswith("https://"):
        return HttpRailAdapter(spec)

    if spec.startswith("openai://"):
        rest = spec[len("openai://") :]
        if "/" not in rest:
            raise ValueError(f"expected openai://<base>/<model>, got {spec!r}")
        base, model = rest.rsplit("/", 1)
        if not base.startswith("http"):
            base = f"https://{base}"
        api_key = __import__("os").environ.get("OPENAI_API_KEY")
        return OpenAICompatibleBaseline(base, model, api_key=api_key)

    raise ValueError(
        f"unknown adapter {spec!r}; use mock-rail, mock-baseline, http(s)://..., or openai://host/model"
    )


def resolve_rail_adapter(spec: str, *, seed: int = 42) -> Adapter:
    if spec.strip().lower() in {"mock", "mock-rail"}:
        return MockRailAdapter(seed=seed)
    return resolve_adapter(spec, seed=seed)


def resolve_baseline_adapter(spec: str, *, seed: int = 42) -> Adapter:
    lowered = spec.strip().lower()
    if lowered in {"mock", "mock-baseline"}:
        return MockBaselineAdapter(seed=seed)
    return resolve_adapter(spec, seed=seed)
