# Process-Integrity Benchmark — Headline Numbers

**NON-REAL — harness demo only. Numbers are from a scripted/mock council (returns a fixed answer) and must NOT appear in the business plan or any design-partner material. Real numbers require council_mode: live against the production council.**  
**Run:** seed `42`, mock-rail vs mock-baseline (80-item fixture slice)  
**Re-run:** `bench run --rail mock-rail --baseline mock-baseline --seed 42 --output results/runs/latest`

> Mock adapters demonstrate harness behavior. Replace `--rail` with your blueCheck rail URL after R-RAIL-STANDALONE for production numbers. Baseline can be any single-model endpoint (`openai://…`).

## Headline metrics (2026-06-15 reference run)

| Metric | Value | Plain-language read |
| --- | --- | --- |
| **Verified Answer Rate** | **77.5%** | Share of items delivered with a valid process-integrity receipt |
| **Dissent AUROC** | **0.90** | Dissent signal strongly predicts errors on answered items |
| **Selective accuracy (rail)** | **91.9%** | Accuracy when the rail chooses to answer |
| **Selective accuracy (baseline)** | **75.0%** | Single-model always-answers accuracy |
| **Selective accuracy Δ** | **+16.9 pp** | Edge from abstention + verification, not raw coverage |
| **ECE (rail)** | **0.096** | Better confidence calibration than baseline (0.135) |
| **Unanimous-wrong residual** | **1 (1.7%)** | Honest floor — consensus can still be wrong |

## What this proves (and does not)

**Proves:** Blue-style process integrity improves *selective* accuracy and calibration by knowing when to withhold an answer. Dissent is a usable error signal (AUROC 0.90 on this slice).

**Does not prove:** Beating a single model on every question. Baseline answers 100% of items; rail answers 77.5% with receipts and abstains on 18/80 — trading coverage for defensibility.

## Category framing

> We do not publish raw-capability leaderboards. We publish **process-integrity** — verified delivery, dissent-as-signal, selective accuracy, calibration — the thing Blue is uniquely built for.

Full per-item results: [`runs/demo-full/RESULTS.md`](runs/demo-full/RESULTS.md)
