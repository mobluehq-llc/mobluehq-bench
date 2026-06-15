"""Public dataset loaders — pinned fixture slices for reproducibility."""

from __future__ import annotations

import json
from pathlib import Path

from mobluehq_bench.types import BenchmarkItem


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data" / "manifest.json").exists():
            return parent
    raise FileNotFoundError("Could not locate data/manifest.json")


PACKAGE_ROOT = _repo_root()
DATA_ROOT = PACKAGE_ROOT / "data"
MANIFEST_PATH = DATA_ROOT / "manifest.json"


def load_manifest() -> dict:
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_jsonl(path: Path) -> list[BenchmarkItem]:
    items: list[BenchmarkItem] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items.append(
                BenchmarkItem(
                    id=str(row["id"]),
                    dataset=str(row["dataset"]),
                    question=str(row["question"]),
                    context=tuple(row.get("context", [])),
                    ground_truth=str(row["ground_truth"]),
                    metadata=dict(row.get("metadata", {})),
                )
            )
    return items


def load_all_datasets(*, max_samples: int | None = None) -> list[BenchmarkItem]:
    """Load all fixture slices in manifest order."""
    manifest = load_manifest()
    items: list[BenchmarkItem] = []
    for ds in manifest["datasets"]:
        path = PACKAGE_ROOT / ds["fixture"]
        items.extend(_parse_jsonl(path))
    if max_samples is not None:
        return items[:max_samples]
    return items


def dataset_licenses() -> list[dict[str, str]]:
    manifest = load_manifest()
    return [
        {
            "id": ds["id"],
            "name": ds["name"],
            "license": ds["license"],
            "source_url": ds["source_url"],
            "citation": ds["citation"],
        }
        for ds in manifest["datasets"]
    ]
