# MOBLUEHQ Process-Integrity Benchmark

Reproducible benchmark for **knowing when a system is wrong** — not raw capability leaderboards.

Blue does not compete on “beats GPT on trivia.” It competes on **defensible process**: verified delivery, dissent as an error signal, selective accuracy after abstention/escalation, and calibration. This repository publishes that benchmark as a citable, re-runnable artifact for design partners and diligence.

## Metrics

| Metric | What it measures |
| --- | --- |
| **Verified Answer Rate (VAR)** | Share of items where the rail delivers an answer backed by a valid process-integrity receipt |
| **Dissent AUROC** | Whether council dissent predicts incorrect answers on the answered subset |
| **Selective accuracy** | Accuracy after abstain/escalate (rail) vs always-answer baseline |
| **ECE** | Expected calibration error — confidence vs correctness |
| **Unanimous-wrong residual** | Consensus (zero dissent) but still wrong — reported honestly |

## Datasets (pinned fixture slices)

Public, citable sources with licenses documented in [`data/manifest.json`](data/manifest.json):

- **TruthfulQA** — misconceptions vs facts ([Apache-2.0](https://github.com/sylinrl/TruthfulQA))
- **HaluEval QA slice** — grounded QA hallucination risk ([MIT](https://github.com/RUCAIBox/HaluEval))
- **LoCoMo slice** — long conversational memory ([CC-BY-4.0](https://github.com/snap-research/locomo))

Fixtures are small, seeded slices checked into `data/fixtures/` for CI reproducibility. Swap in full upstream exports by updating the manifest paths.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Mock rail vs mock baseline (no live endpoints)
bench run --rail mock-rail --baseline mock-baseline --seed 42 --output results/runs/demo

# Live blueCheck rail (after R-RAIL-STANDALONE)
bench run --rail https://your-rail.example.com --baseline mock-baseline --seed 42

# OpenAI-compatible single-model baseline
export OPENAI_API_KEY=...
bench run --rail mock-rail --baseline openai://api.openai.com/v1/gpt-4o-mini --seed 42
```

## Output

Each run writes:

- `results.json` — per-item scores + aggregate metrics
- `results.receipt.json` — signed results receipt (`mobluehq-bench-results-v1`)
- `RESULTS.md` — shareable results page
- `headline.json` — headline numbers for decks / business plan

## Method (honest reporting)

1. Load pinned fixture slices (seeded, manifest-versioned).
2. For each item, call **rail** and **baseline** adapters.
3. Score correctness with normalized string match against public ground truth.
4. Verify process-integrity receipts (Ed25519, schema `process-integrity-v1`).
5. Compute VAR, dissent AUROC, selective accuracy, ECE, unanimous-wrong residual.
6. Sign and emit a results receipt.

We report **where Blue does not help**: unanimous-wrong residuals remain when the council agrees and still errs. Abstention reduces exposure; it does not eliminate consensus failure modes.

## Development

```bash
ruff check src tests
pytest -q
```

## License

Apache-2.0 — see [LICENSE](LICENSE).

Benchmark fixtures are derived from public datasets under their respective licenses (see manifest). Mock adapters use deterministic seeds only; they do not reproduce upstream dataset statistics.
