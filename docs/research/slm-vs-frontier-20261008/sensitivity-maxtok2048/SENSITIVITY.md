# D2 sensitivity: max_tokens 512 (preregistered) vs 2048

Same tasks, same seeds on both sides. Only (model, seed) pairs fully completed in the 2048 run are compared: `claude-haiku-5.5` seeds [0, 1, 2]; `claude-sonnet-5.5` seeds [0]; `qwen38-27b-q3k` seeds [0, 1]. Qwen seed 2 was stopped by the operator part-way (452/540 cells written) and is excluded here; the automatic `REPORT.md`/`results.csv` in this directory count its unwritten cells as failures, so use this file for Qwen.

Truncated = cell ended in status `error` (a call hit the token cap). Accuracy = correct / cells.

| Model | Seeds | Domain | Arm | Cells | Acc 512 | Acc 2048 | Δ | Trunc 512 | Trunc 2048 | Invalid 512 | Invalid 2048 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-haiku-5.5 | 0,1,2 | finance | evidence_exchange | 90 | 54.4% | 80.0% | +25.6% | 26 | 0 | 14 | 12 |
| claude-haiku-5.5 | 0,1,2 | finance | evidence_isolated | 90 | 0.0% | 0.0% | +0.0% | 20 | 0 | 16 | 22 |
| claude-haiku-5.5 | 0,1,2 | finance | single | 90 | 91.1% | 93.3% | +2.2% | 2 | 0 | 0 | 0 |
| claude-haiku-5.5 | 0,1,2 | medical | evidence_exchange | 90 | 73.3% | 72.2% | -1.1% | 15 | 0 | 5 | 13 |
| claude-haiku-5.5 | 0,1,2 | medical | evidence_isolated | 90 | 1.1% | 2.2% | +1.1% | 8 | 0 | 19 | 21 |
| claude-haiku-5.5 | 0,1,2 | medical | single | 90 | 86.7% | 87.8% | +1.1% | 3 | 0 | 3 | 2 |
| claude-sonnet-5.5 | 0 | finance | evidence_exchange | 30 | 23.3% | 30.0% | +6.7% | 2 | 0 | 20 | 19 |
| claude-sonnet-5.5 | 0 | finance | evidence_isolated | 30 | 0.0% | 3.3% | +3.3% | 1 | 0 | 24 | 25 |
| claude-sonnet-5.5 | 0 | finance | single | 30 | 40.0% | 33.3% | -6.7% | 0 | 0 | 17 | 19 |
| claude-sonnet-5.5 | 0 | medical | evidence_exchange | 30 | 63.3% | 76.7% | +13.3% | 0 | 0 | 10 | 6 |
| claude-sonnet-5.5 | 0 | medical | evidence_isolated | 30 | 0.0% | 0.0% | +0.0% | 0 | 0 | 14 | 17 |
| claude-sonnet-5.5 | 0 | medical | single | 30 | 96.7% | 96.7% | +0.0% | 0 | 0 | 0 | 0 |
| qwen38-27b-q3k | 0,1 | finance | evidence_exchange | 60 | 20.0% | 18.3% | -1.7% | 13 | 1 | 31 | 45 |
| qwen38-27b-q3k | 0,1 | finance | evidence_isolated | 60 | 0.0% | 0.0% | +0.0% | 13 | 5 | 33 | 40 |
| qwen38-27b-q3k | 0,1 | finance | single | 60 | 75.0% | 75.0% | +0.0% | 4 | 0 | 6 | 10 |
| qwen38-27b-q3k | 0,1 | medical | evidence_exchange | 60 | 81.7% | 80.0% | -1.7% | 0 | 0 | 7 | 8 |
| qwen38-27b-q3k | 0,1 | medical | evidence_isolated | 60 | 25.0% | 23.3% | -1.7% | 4 | 1 | 14 | 18 |
| qwen38-27b-q3k | 0,1 | medical | single | 60 | 85.0% | 85.0% | +0.0% | 0 | 0 | 1 | 2 |
