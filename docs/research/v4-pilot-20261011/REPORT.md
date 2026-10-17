# Antelligence v4 pilot report

Generated from `results.json` by `v4_report.py`. No number in this file is typed by hand.

- Pilot: v4 pilot, can a queen and small workers handle surprises?
- Preregistration commit: 68ac613
- Cells in results: 284

> **Pilot estimates.** pilot estimates; 15 runs per arm per world detect only large effects. Do not read these as confirmed effects.

## Go / no-go verdict

**Verdict: UNCLEAR**

Rule (fixed in the preregistration):
- Go: a framework arm's paired mean G is at least DS-all's paired mean G minus 0.10, and its median seconds per decision is lower than DS-all's.
- No-go: both framework arms have paired mean G below 0.10. No-go takes precedence.
- Otherwise: unclear.

- Paired keys (world, seed, condition): 15
- DS-all paired mean G: 0.454
- DS-all median s/decision: 2.98
- go_also_holds: no
- Arms meeting Go: none

| Arm | Paired mean G | Median s/decision | G within margin | Faster than DS-all | Go | Below no-go line |
|---|---|---|---|---|---|---|
| F-Jev | 0.194 | 2.05 | no | yes | no | no |
| F-Laya | -0.028 | 1.50 | no | yes | no | yes |

## Primary comparison

Mean G difference on shared (world, seed, condition) keys; percentile bootstrap over seed clusters (confidence level 0.95, 10000 resamples). Pilot estimates.

| Comparison | Pairs | Seeds | Mean diff | 95% CI |
|---|---|---|---|---|
| F-Jev vs DS-all | 15 | 5 | -0.260 | [-0.593, -0.025] |
| F-Laya vs DS-all | 15 | 5 | -0.483 | [-0.704, -0.244] |

## Per-arm results (all worlds)

**Score and gap recovered**

| Arm | Cells | Errors | Mean G | Mean G V1 | Mean G V2 | Base share of S | Score base | Score V1 | Score V2 | G undefined |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 30 | 0 | — | — | — | 1.000 | 8.741 | 2.748 | 1.794 | 0 |
| S-prime | 20 | 0 | — | — | — | — | — | 8.543 | 7.803 | 0 |
| DS-all | 24 | 0 | 0.454 | 0.320 | 0.607 | 0.074 | 0.515 | 0.589 | 0.592 | 1 |
| F-Jev | 30 | 0 | 0.084 | 0.109 | 0.055 | 0.017 | 0.145 | 0.337 | 0.302 | 1 |
| F-Laya | 30 | 0 | -0.092 | -0.077 | -0.108 | 0.010 | 0.086 | 0.191 | 0.214 | 1 |
| F-Jev-noEsc | 30 | 0 | 0.231 | 0.190 | 0.277 | 0.028 | 0.242 | 0.400 | 0.352 | 1 |
| F-Jev-noQueen | 30 | 0 | 0.372 | 0.202 | 0.561 | 0.041 | 0.358 | 0.403 | 0.435 | 1 |
| Q-all-qwen3.5-0.8b | 30 | 0 | -0.391 | -0.318 | -0.473 | 0.000 | 0.000 | 0.000 | 0.000 | 1 |
| Q-all-qwen3.5-9b | 30 | 0 | 0.222 | 0.136 | 0.318 | 0.031 | 0.273 | 0.355 | 0.307 | 1 |
| Q-all-qwen3.8-27b | 30 | 0 | 0.145 | 0.164 | 0.123 | 0.030 | 0.260 | 0.379 | 0.304 | 1 |

**Time, calls and cost**

| Arm | Median s/decision | p90 s/decision | Ticks (mean) | Wall s (mean) | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|---|---|---|---|
| S | — | — | 52.00 | 0.65 | 0 | 0 | 0 | $0.0000 |
| S-prime | — | — | 52.00 | 0.73 | 0 | 0 | 0 | $0.0000 |
| DS-all | 2.98 | 5.46 | 40.00 | 258.44 | 9480 | 2774760 | 62847 | $0.8765 |
| F-Jev | 2.05 | 3.46 | 52.00 | 220.76 | 14825 | 8006786 | 1088033 | $0.3232 |
| F-Laya | 1.50 | 3.31 | 52.00 | 94.24 | 5377 | 2458884 | 76335 | $0.0791 |
| F-Jev-noEsc | 1.14 | 2.90 | 52.00 | 121.10 | 9156 | 6763323 | 1046928 | $0.3571 |
| F-Jev-noQueen | 1.96 | 3.14 | 52.00 | 113.79 | 10257 | 5165567 | 709706 | $0.1542 |
| Q-all-qwen3.5-0.8b | 1.71 | 4.30 | 52.00 | 203.13 | 15480 | 4860055 | 93670 | $0.0000 |
| Q-all-qwen3.5-9b | 2.75 | 4.52 | 52.00 | 234.87 | 15480 | 4697246 | 93645 | $0.0000 |
| Q-all-qwen3.8-27b | 18.72 | 19.53 | 52.00 | 1006.30 | 15480 | 4652094 | 94600 | $0.0000 |

**Worker behaviour**

| Arm | Compliance | Report precision | Reports | Escalation rate | Policy failures |
|---|---|---|---|---|---|
| S | 1.000 | — | 0 | — | 0 |
| S-prime | 1.000 | — | 0 | — | 0 |
| DS-all | 1.000 | — | 0 | — | 0 |
| F-Jev | 1.000 | 0.024 | 127 | 0.989 | 0 |
| F-Laya | 1.000 | 0.000 | 8617 | 0.992 | 0 |
| F-Jev-noEsc | 1.000 | 0.000 | 283 | 0.000 | 0 |
| F-Jev-noQueen | 1.000 | 0.000 | 5 | 0.988 | 0 |
| Q-all-qwen3.5-0.8b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.5-9b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.8-27b | 1.000 | — | 0 | — | 0 |

## Per-world results: foraging_sb

**Score and gap recovered**

| Arm | Cells | Errors | Mean G | Mean G V1 | Mean G V2 | Base share of S | Score base | Score V1 | Score V2 | G undefined |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 15 | 0 | — | — | — | 1.000 | 16.800 | 5.400 | 3.200 | 0 |
| S-prime | 10 | 0 | — | — | — | — | — | 16.200 | 14.800 | 0 |
| DS-all | 9 | 0 | -0.404 | -0.511 | -0.296 | 0.000 | 0.000 | 0.333 | 0.333 | 0 |
| F-Jev | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| F-Laya | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| F-Jev-noEsc | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| F-Jev-noQueen | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| Q-all-qwen3.5-0.8b | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| Q-all-qwen3.5-9b | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |
| Q-all-qwen3.8-27b | 15 | 0 | -0.393 | -0.508 | -0.278 | 0.000 | 0.000 | 0.000 | 0.000 | 0 |

**Time, calls and cost**

| Arm | Median s/decision | p90 s/decision | Ticks (mean) | Wall s (mean) | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|---|---|---|---|
| S | — | — | 100.00 | 1.25 | 0 | 0 | 0 | $0.0000 |
| S-prime | — | — | 100.00 | 1.42 | 0 | 0 | 0 | $0.0000 |
| DS-all | 2.99 | 5.43 | 100.00 | 648.32 | 9000 | 2658857 | 59046 | $0.8386 |
| F-Jev | 2.07 | 3.49 | 100.00 | 422.78 | 13984 | 7615701 | 1025671 | $0.2984 |
| F-Laya | 1.51 | 3.29 | 100.00 | 166.30 | 4502 | 2194699 | 63341 | $0.0635 |
| F-Jev-noEsc | 1.14 | 2.86 | 100.00 | 220.83 | 8628 | 6449387 | 988682 | $0.3302 |
| F-Jev-noQueen | 1.99 | 3.16 | 100.00 | 214.07 | 9496 | 4817207 | 655791 | $0.1426 |
| Q-all-qwen3.5-0.8b | 1.70 | 4.30 | 100.00 | 393.36 | 15000 | 4746760 | 90790 | $0.0000 |
| Q-all-qwen3.5-9b | 2.74 | 4.51 | 100.00 | 454.70 | 15000 | 4577685 | 90093 | $0.0000 |
| Q-all-qwen3.8-27b | 18.73 | 19.53 | 100.00 | 1956.53 | 15000 | 4532661 | 90282 | $0.0000 |

**Worker behaviour**

| Arm | Compliance | Report precision | Reports | Escalation rate | Policy failures |
|---|---|---|---|---|---|
| S | 1.000 | — | 0 | — | 0 |
| S-prime | 1.000 | — | 0 | — | 0 |
| DS-all | 1.000 | — | 0 | — | 0 |
| F-Jev | 1.000 | 0.000 | 124 | 1.000 | 0 |
| F-Laya | 1.000 | 0.000 | 8617 | 1.000 | 0 |
| F-Jev-noEsc | 1.000 | 0.000 | 283 | 0.000 | 0 |
| F-Jev-noQueen | 1.000 | 0.000 | 5 | 1.000 | 0 |
| Q-all-qwen3.5-0.8b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.5-9b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.8-27b | 1.000 | — | 0 | — | 0 |

## Per-world results: graph_coloring

**Score and gap recovered**

| Arm | Cells | Errors | Mean G | Mean G V1 | Mean G V2 | Base share of S | Score base | Score V1 | Score V2 | G undefined |
|---|---|---|---|---|---|---|---|---|---|---|
| S | 15 | 0 | — | — | — | 1.000 | 0.683 | 0.097 | 0.388 | 0 |
| S-prime | 10 | 0 | — | — | — | — | — | 0.887 | 0.805 | 0 |
| DS-all | 15 | 0 | 1.026 | 0.819 | 1.285 | 1.206 | 0.823 | 0.742 | 0.748 | 1 |
| F-Jev | 15 | 0 | 0.613 | 0.726 | 0.472 | 0.424 | 0.290 | 0.674 | 0.604 | 1 |
| F-Laya | 15 | 0 | 0.243 | 0.354 | 0.104 | 0.252 | 0.172 | 0.382 | 0.428 | 1 |
| F-Jev-noEsc | 15 | 0 | 0.926 | 0.889 | 0.972 | 0.709 | 0.484 | 0.800 | 0.704 | 1 |
| F-Jev-noQueen | 15 | 0 | 1.223 | 0.913 | 1.611 | 1.050 | 0.717 | 0.806 | 0.871 | 1 |
| Q-all-qwen3.5-0.8b | 15 | 0 | -0.389 | -0.129 | -0.715 | 0.000 | 0.000 | 0.000 | 0.000 | 1 |
| Q-all-qwen3.5-9b | 15 | 0 | 0.906 | 0.781 | 1.062 | 0.801 | 0.547 | 0.710 | 0.614 | 1 |
| Q-all-qwen3.8-27b | 15 | 0 | 0.743 | 0.837 | 0.625 | 0.760 | 0.519 | 0.757 | 0.608 | 1 |

**Time, calls and cost**

| Arm | Median s/decision | p90 s/decision | Ticks (mean) | Wall s (mean) | Calls | Input tokens | Output tokens | Cost |
|---|---|---|---|---|---|---|---|---|
| S | — | — | 4.00 | 0.05 | 0 | 0 | 0 | $0.0000 |
| S-prime | — | — | 4.00 | 0.05 | 0 | 0 | 0 | $0.0000 |
| DS-all | 2.89 | 5.81 | 4.00 | 24.51 | 480 | 115903 | 3801 | $0.0379 |
| F-Jev | 1.63 | 2.61 | 4.00 | 18.74 | 841 | 391085 | 62362 | $0.0248 |
| F-Laya | 1.31 | 3.38 | 4.00 | 22.17 | 875 | 264185 | 12994 | $0.0156 |
| F-Jev-noEsc | 1.31 | 3.78 | 4.00 | 21.37 | 528 | 313936 | 58246 | $0.0269 |
| F-Jev-noQueen | 1.48 | 2.48 | 4.00 | 13.52 | 761 | 348360 | 53915 | $0.0116 |
| Q-all-qwen3.5-0.8b | 1.86 | 4.15 | 4.00 | 12.91 | 480 | 113295 | 2880 | $0.0000 |
| Q-all-qwen3.5-9b | 2.80 | 4.64 | 4.00 | 15.03 | 480 | 119561 | 3552 | $0.0000 |
| Q-all-qwen3.8-27b | 13.38 | 15.26 | 4.00 | 56.07 | 480 | 119433 | 4318 | $0.0000 |

**Worker behaviour**

| Arm | Compliance | Report precision | Reports | Escalation rate | Policy failures |
|---|---|---|---|---|---|
| S | 1.000 | — | 0 | — | 0 |
| S-prime | 1.000 | — | 0 | — | 0 |
| DS-all | 1.000 | — | 0 | — | 0 |
| F-Jev | 1.000 | 1.000 | 3 | 0.660 | 0 |
| F-Laya | 1.000 | — | 0 | 0.741 | 0 |
| F-Jev-noEsc | 1.000 | — | 0 | 0.000 | 0 |
| F-Jev-noQueen | 1.000 | — | 0 | 0.623 | 0 |
| Q-all-qwen3.5-0.8b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.5-9b | 1.000 | — | 0 | — | 0 |
| Q-all-qwen3.8-27b | 1.000 | — | 0 | — | 0 |

## Incomplete-arm rule

An arm missing more than 20% of its planned cells is reported as incomplete. The verdict is `unclear` if DS-all, F-Jev or F-Laya is incomplete.

| Arm | Planned cells | Cells | Errors | Status |
|---|---|---|---|---|
| S | 30 | 30 | 0 | complete |
| S-prime | 20 | 20 | 0 | complete |
| DS-all | 24 | 24 | 0 | complete |
| F-Jev | 30 | 30 | 0 | complete |
| F-Laya | 30 | 30 | 0 | complete |
| F-Jev-noEsc | 30 | 30 | 0 | complete |
| F-Jev-noQueen | 30 | 30 | 0 | complete |
| Q-all-qwen3.5-0.8b | 30 | 30 | 0 | complete |
| Q-all-qwen3.5-4b | 30 | 0 | 0 | INCOMPLETE |
| Q-all-qwen3.5-9b | 30 | 30 | 0 | complete |
| Q-all-qwen3.8-27b | 30 | 30 | 0 | complete |
