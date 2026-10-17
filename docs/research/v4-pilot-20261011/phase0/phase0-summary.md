# Phase 0 calibration summary

Aggregate results only. Every number below is read from `phase0-summary.json`, produced by `scripts/v4_phase0_analysis.py` from the local calibration rows (150 judgement and 150 move items per backend, development seeds).

Accuracy is scored at 0.5 for judgements. Brier and ECE use the probability of the right answer (moves: summed over the accepted options). Chance for a judgement is the majority-label rate; for a move it is the mean of accepted options over all options. Chance and all statistics use scored items only; errored items are counted in n and errors.

## Calibration: both worlds

| backend | kind | n | scored | errors | accuracy | chance | Brier | ECE | latency median s | p90 s |
|---|---|---|---|---|---|---|---|---|---|---|
| laya | all | 300 | 300 | 0 | 0.333 | 0.540 | 0.217 | 0.188 | 0.17 | 0.19 |
| laya | judgement | 150 | 150 | 0 | 0.413 | 0.700 | 0.322 | 0.296 | 0.17 | 0.19 |
| laya | move | 150 | 150 | 0 | 0.253 | 0.381 | 0.111 | 0.112 | 0.17 | 0.19 |
| jev | all | 300 | 300 | 0 | 0.757 | 0.540 | 0.092 | 0.136 | 0.90 | 1.08 |
| jev | judgement | 150 | 150 | 0 | 0.813 | 0.700 | 0.110 | 0.112 | 0.91 | 1.09 |
| jev | move | 150 | 150 | 0 | 0.700 | 0.381 | 0.073 | 0.200 | 0.88 | 1.06 |
| deepseek | all | 300 | 284 | 16 | 0.694 | 0.532 | 0.120 | 0.087 | 2.73 | 6.40 |
| deepseek | judgement | 150 | 145 | 5 | 0.848 | 0.703 | 0.145 | 0.147 | 2.68 | 5.21 |
| deepseek | move | 150 | 139 | 11 | 0.532 | 0.352 | 0.093 | 0.066 | 2.78 | 7.47 |
| qwen3.5-9b | all | 300 | 282 | 18 | 0.631 | 0.541 | 0.076 | 0.060 | 3.26 | 4.98 |
| qwen3.5-9b | judgement | 150 | 150 | 0 | 0.820 | 0.700 | 0.127 | 0.102 | 1.77 | 3.60 |
| qwen3.5-9b | move | 150 | 132 | 18 | 0.417 | 0.361 | 0.018 | 0.033 | 3.90 | 5.80 |

## Calibration: foraging sb

| backend | kind | n | scored | errors | accuracy | chance | Brier | ECE | latency median s | p90 s |
|---|---|---|---|---|---|---|---|---|---|---|
| laya | all | 150 | 150 | 0 | 0.420 | 0.349 | 0.184 | 0.111 | 0.18 | 0.19 |
| laya | judgement | 75 | 75 | 0 | 0.640 | 0.507 | 0.240 | 0.140 | 0.18 | 0.19 |
| laya | move | 75 | 75 | 0 | 0.200 | 0.190 | 0.129 | 0.086 | 0.18 | 0.20 |
| jev | all | 150 | 150 | 0 | 0.580 | 0.349 | 0.132 | 0.143 | 0.90 | 1.08 |
| jev | judgement | 75 | 75 | 0 | 0.693 | 0.507 | 0.177 | 0.158 | 0.91 | 1.10 |
| jev | move | 75 | 75 | 0 | 0.467 | 0.190 | 0.086 | 0.179 | 0.88 | 1.06 |
| deepseek | all | 150 | 147 | 3 | 0.599 | 0.353 | 0.126 | 0.141 | 2.80 | 7.84 |
| deepseek | judgement | 75 | 74 | 1 | 0.757 | 0.514 | 0.230 | 0.216 | 2.89 | 7.46 |
| deepseek | move | 75 | 73 | 2 | 0.438 | 0.190 | 0.022 | 0.097 | 2.80 | 7.88 |
| qwen3.5-9b | all | 150 | 146 | 4 | 0.575 | 0.352 | 0.077 | 0.047 | 2.26 | 3.91 |
| qwen3.5-9b | judgement | 75 | 75 | 0 | 0.813 | 0.507 | 0.149 | 0.091 | 1.69 | 2.08 |
| qwen3.5-9b | move | 75 | 71 | 4 | 0.324 | 0.189 | 0.000 | 0.002 | 3.64 | 4.19 |

## Calibration: graph coloring

| backend | kind | n | scored | errors | accuracy | chance | Brier | ECE | latency median s | p90 s |
|---|---|---|---|---|---|---|---|---|---|---|
| laya | all | 150 | 150 | 0 | 0.247 | 0.732 | 0.249 | 0.373 | 0.16 | 0.17 |
| laya | judgement | 75 | 75 | 0 | 0.187 | 0.893 | 0.405 | 0.545 | 0.16 | 0.17 |
| laya | move | 75 | 75 | 0 | 0.307 | 0.571 | 0.093 | 0.200 | 0.16 | 0.17 |
| jev | all | 150 | 150 | 0 | 0.933 | 0.732 | 0.052 | 0.148 | 0.90 | 1.07 |
| jev | judgement | 75 | 75 | 0 | 0.933 | 0.893 | 0.043 | 0.101 | 0.90 | 1.08 |
| jev | move | 75 | 75 | 0 | 0.933 | 0.571 | 0.060 | 0.221 | 0.89 | 1.05 |
| deepseek | all | 150 | 137 | 13 | 0.796 | 0.723 | 0.113 | 0.077 | 2.60 | 4.42 |
| deepseek | judgement | 75 | 71 | 4 | 0.944 | 0.901 | 0.058 | 0.075 | 2.15 | 3.30 |
| deepseek | move | 75 | 66 | 9 | 0.636 | 0.532 | 0.172 | 0.147 | 2.76 | 5.65 |
| qwen3.5-9b | all | 150 | 136 | 14 | 0.691 | 0.745 | 0.075 | 0.075 | 3.85 | 6.30 |
| qwen3.5-9b | judgement | 75 | 75 | 0 | 0.827 | 0.893 | 0.105 | 0.113 | 1.88 | 5.50 |
| qwen3.5-9b | move | 75 | 61 | 14 | 0.525 | 0.562 | 0.039 | 0.069 | 4.83 | 6.54 |

## Escalation grid

The decision model answers when confident; Qwen3.5-9B answers when escalated; if Qwen errors on an escalated item the decision model's answer is kept. Noul escalates when lo < P(yes) < hi. Choice escalates when the decision model's confidence is below c_min; the rows carry no backend confidence, so the maximum probability over all options is the proxy. `none` means never escalate. `dm acc esc` and `slm acc esc` are the decision model's and Qwen's accuracy on the escalated subset (Qwen's over the items it scored; `dm acc same` is the decision model on those same items). Latency adds Qwen's wall-clock to escalated items.

### laya: noul (judgements)

| setting | n | escalated | rate | slm errors | accuracy | Brier | dm acc esc | slm acc esc | dm acc same | latency median s | latency mean s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1/0.9 | 150 | 150 | 1.000 | 0 | 0.820 | 0.127 | 0.413 | 0.820 | 0.413 | 1.94 | 2.58 |
| 0.2/0.8 | 150 | 150 | 1.000 | 0 | 0.820 | 0.127 | 0.413 | 0.820 | 0.413 | 1.94 | 2.58 |
| 0.3/0.7 | 150 | 121 | 0.807 | 0 | 0.653 | 0.218 | 0.504 | 0.802 | 0.504 | 1.82 | 2.01 |
| 0.35/0.65 | 150 | 99 | 0.660 | 0 | 0.553 | 0.270 | 0.566 | 0.778 | 0.566 | 1.72 | 1.61 |
| none | 150 | 0 | 0.000 | 0 | 0.413 | 0.322 | - | - | - | 0.17 | 0.17 |

### laya: choice (moves)

| setting | n | escalated | rate | slm errors | accuracy | Brier | dm acc esc | slm acc esc | dm acc same | latency median s | latency mean s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.3 | 150 | 83 | 0.553 | 10 | 0.287 | 0.045 | 0.386 | 0.438 | 0.370 | 3.49 | 2.57 |
| 0.4 | 150 | 113 | 0.753 | 12 | 0.347 | 0.038 | 0.310 | 0.436 | 0.297 | 3.87 | 3.46 |
| 0.5 | 150 | 130 | 0.867 | 14 | 0.387 | 0.032 | 0.285 | 0.448 | 0.276 | 3.95 | 3.96 |
| 0.6 | 150 | 145 | 0.967 | 17 | 0.400 | 0.027 | 0.262 | 0.430 | 0.258 | 4.07 | 4.49 |
| 0.7 | 150 | 150 | 1.000 | 18 | 0.400 | 0.025 | 0.253 | 0.417 | 0.250 | 4.11 | 4.62 |
| none | 150 | 0 | 0.000 | 0 | 0.253 | 0.111 | - | - | - | 0.17 | 0.17 |

### jev: noul (judgements)

| setting | n | escalated | rate | slm errors | accuracy | Brier | dm acc esc | slm acc esc | dm acc same | latency median s | latency mean s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1/0.9 | 150 | 57 | 0.380 | 0 | 0.860 | 0.117 | 0.544 | 0.667 | 0.544 | 1.06 | 1.76 |
| 0.2/0.8 | 150 | 52 | 0.347 | 0 | 0.867 | 0.110 | 0.500 | 0.654 | 0.500 | 1.05 | 1.70 |
| 0.3/0.7 | 150 | 51 | 0.340 | 0 | 0.867 | 0.106 | 0.510 | 0.667 | 0.510 | 1.05 | 1.68 |
| 0.35/0.65 | 150 | 40 | 0.267 | 0 | 0.853 | 0.106 | 0.550 | 0.700 | 0.550 | 1.03 | 1.54 |
| none | 150 | 0 | 0.000 | 0 | 0.813 | 0.110 | - | - | - | 0.91 | 0.97 |

### jev: choice (moves)

| setting | n | escalated | rate | slm errors | accuracy | Brier | dm acc esc | slm acc esc | dm acc same | latency median s | latency mean s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.3 | 150 | 1 | 0.007 | 0 | 0.693 | 0.072 | 1.000 | 0.000 | 1.000 | 0.88 | 0.99 |
| 0.4 | 150 | 17 | 0.113 | 0 | 0.667 | 0.058 | 0.412 | 0.118 | 0.412 | 0.90 | 1.41 |
| 0.5 | 150 | 33 | 0.220 | 3 | 0.667 | 0.047 | 0.364 | 0.200 | 0.367 | 0.90 | 1.81 |
| 0.6 | 150 | 61 | 0.407 | 6 | 0.620 | 0.034 | 0.459 | 0.236 | 0.455 | 1.02 | 2.62 |
| 0.7 | 150 | 111 | 0.740 | 14 | 0.513 | 0.023 | 0.667 | 0.361 | 0.649 | 4.61 | 4.31 |
| none | 150 | 0 | 0.000 | 0 | 0.700 | 0.073 | - | - | - | 0.88 | 0.95 |

## Proposed thresholds

Rule: highest combined accuracy with escalation rate at most 0.5; ties go to the lower escalation rate, then the lower Brier. Goal defaults are 0.2/0.8 for noul and c_min 0.5 for choice.

| model | question | proposed | accuracy | escalation rate | Brier | items gained vs none | items gained vs goal default |
|---|---|---|---|---|---|---|---|
| laya | noul band | none | 0.413 (62/150) | 0.000 | 0.322 | 0 | -61 |
| laya | choice c_min | none | 0.253 (38/150) | 0.000 | 0.111 | 0 | -20 |
| jev | noul band | 0.3/0.7 | 0.867 (130/150) | 0.340 | 0.106 | 8 | 0 |
| jev | choice c_min | none | 0.700 (105/150) | 0.000 | 0.073 | 0 | 5 |

Notes generated from the table values:

- laya: P(yes) on judgements spans 0.294 to 0.796 (median 0.529). Without the rate cap the best noul setting is 0.1/0.9 (accuracy 0.820, escalation rate 1.000); the best choice setting is 0.6 (accuracy 0.400, escalation rate 0.967).
- jev: P(yes) on judgements spans 0.020 to 0.930 (median 0.075). Without the rate cap the best noul setting is 0.3/0.7 (accuracy 0.867, escalation rate 0.340); the best choice setting is none (accuracy 0.700, escalation rate 0.000).

Per world at the proposed setting:

| model | question | world | n | escalation rate | accuracy | accuracy without escalation |
|---|---|---|---|---|---|---|
| laya | noul band | foraging_sb | 75 | 0.000 | 0.640 | 0.640 |
| laya | noul band | graph_coloring | 75 | 0.000 | 0.187 | 0.187 |
| laya | choice c_min | foraging_sb | 75 | 0.000 | 0.200 | 0.200 |
| laya | choice c_min | graph_coloring | 75 | 0.000 | 0.307 | 0.307 |
| jev | noul band | foraging_sb | 75 | 0.573 | 0.813 | 0.693 |
| jev | noul band | graph_coloring | 75 | 0.107 | 0.920 | 0.933 |
| jev | choice c_min | foraging_sb | 75 | 0.000 | 0.467 | 0.467 |
| jev | choice c_min | graph_coloring | 75 | 0.000 | 0.933 | 0.933 |

Each cell has about 75 items, so a difference of a few items is within noise.
