# Colony v2 results

Generated from `results.json`; every number below is read from it. Spec: `PREREGISTRATION.md`.
Evaluation items: 100; development items: 100.

## Headline (P1 and P2)

Does the mixed colony answer more questions correctly than its best member given the same number of calls? Paired by item, exact McNemar test, Holm-corrected over the two domains, with a Newcombe 95% interval for the gain.

**P1: colony_local** against solo3[qwen] (best member chosen on development data)

| Domain | Items | Colony | Best member | Gain | 95% interval | Colony-only right | Member-only right | Holm p | Result |
|---|---|---|---|---|---|---|---|---|---|
| finance | 50 | 48.0% | 78.0% | -30.0 pts | -42.1 to -16.1 | 0 | 15 | 0.000 | no gain above 5 points (upper bound -0.161) |
| medical | 50 | 86.0% | 82.0% | +4.0 pts | -3.7 to +12.5 | 2 | 0 | 0.500 | not detected at this sample size |

**P2: colony_haiku** against solo3[haiku] (best member chosen on development data)

| Domain | Items | Colony | Best member | Gain | 95% interval | Colony-only right | Member-only right | Holm p | Result |
|---|---|---|---|---|---|---|---|---|---|
| finance | 50 | 74.0% | 90.0% | -16.0 pts | -27.9 to -5.1 | 0 | 8 | 0.016 | no gain above 5 points (upper bound -0.051) |
| medical | 50 | 82.0% | 84.0% | -2.0 pts | -11.0 to +6.7 | 1 | 2 | 1.000 | not detected at this sample size |

## All arms (evaluation split)

| Arm | Medical | Finance | Both | No answer |
|---|---|---|---|---|
| colony_haiku | 82.0% (69.2-90.2%) | 74.0% (60.4-84.1%) | 78.0% (68.9-85.0%) | 2 |
| colony_haiku_a_no_correlation | 82.0% (69.2-90.2%) | 74.0% (60.4-84.1%) | 78.0% (68.9-85.0%) | 2 |
| colony_haiku_b_no_reputation | 82.0% (69.2-90.2%) | 74.0% (60.4-84.1%) | 78.0% (68.9-85.0%) | 2 |
| colony_haiku_c_no_verification | 82.0% (69.2-90.2%) | 78.0% (64.8-87.2%) | 80.0% (71.1-86.7%) | 0 |
| colony_haiku_cold | 82.0% (69.2-90.2%) | 74.0% (60.4-84.1%) | 78.0% (68.9-85.0%) | 2 |
| colony_haiku_d_plain_plurality | 82.0% (69.2-90.2%) | 76.0% (62.6-85.7%) | 79.0% (70.0-85.8%) | 0 |
| colony_haiku_e_single_model | 84.0% (71.5-91.7%) | 76.0% (62.6-85.7%) | 80.0% (71.1-86.7%) | 7 |
| colony_haiku_withG | 84.0% (71.5-91.7%) | 74.0% (60.4-84.1%) | 79.0% (70.0-85.8%) | 2 |
| colony_local | 86.0% (73.8-93.0%) | 48.0% (34.8-61.5%) | 67.0% (57.3-75.4%) | 5 |
| colony_local_a_no_correlation | 82.0% (69.2-90.2%) | 48.0% (34.8-61.5%) | 65.0% (55.3-73.6%) | 5 |
| colony_local_b_no_reputation | 82.0% (69.2-90.2%) | 46.0% (33.0-59.6%) | 64.0% (54.2-72.7%) | 5 |
| colony_local_c_no_verification | 78.0% (64.8-87.2%) | 76.0% (62.6-85.7%) | 77.0% (67.8-84.2%) | 0 |
| colony_local_cold | 82.0% (69.2-90.2%) | 46.0% (33.0-59.6%) | 64.0% (54.2-72.7%) | 5 |
| colony_local_d_plain_plurality | 76.0% (62.6-85.7%) | 40.0% (27.6-53.8%) | 58.0% (48.2-67.2%) | 0 |
| colony_local_e_single_model | 82.0% (69.2-90.2%) | 70.0% (56.2-80.9%) | 76.0% (66.8-83.3%) | 11 |
| colony_local_noG | 84.0% (71.5-91.7%) | 48.0% (34.8-61.5%) | 66.0% (56.3-74.5%) | 6 |
| solo1[gemma] | 72.0% (58.3-82.5%) | 8.0% (3.2-18.8%) | 40.0% (30.9-49.8%) | 33 |
| solo1[haiku] | 80.0% (67.0-88.8%) | 88.0% (76.2-94.4%) | 84.0% (75.6-89.9%) | 1 |
| solo1[phi] | 48.0% (34.8-61.5%) | 4.0% (1.1-13.5%) | 26.0% (18.4-35.4%) | 9 |
| solo1[qwen] | 84.0% (71.5-91.7%) | 76.0% (62.6-85.7%) | 80.0% (71.1-86.7%) | 0 |
| solo2[qwen] | 84.0% (71.5-91.7%) | 76.0% (62.6-85.7%) | 80.0% (71.1-86.7%) | 0 |
| solo3[gemma] | 76.0% (62.6-85.7%) | 12.0% (5.6-23.8%) | 44.0% (34.7-53.8%) | 23 |
| solo3[haiku] | 84.0% (71.5-91.7%) | 90.0% (78.6-95.7%) | 87.0% (79.0-92.2%) | 0 |
| solo3[phi] | 50.0% (36.6-63.4%) | 4.0% (1.1-13.5%) | 27.0% (19.3-36.4%) | 1 |
| solo3[qwen] | 82.0% (69.2-90.2%) | 78.0% (64.8-87.2%) | 80.0% (71.1-86.7%) | 0 |
| solo4[haiku] | 80.0% (67.0-88.8%) | 90.0% (78.6-95.7%) | 85.0% (76.7-90.7%) | 0 |

Strict scoring: a failed or cut-off reply counts as wrong. Accuracy among answered items is in `results.json` (`acc_answered`).

## Secondary results

### S1 ablations (accuracy, both domains; difference counts against the full colony)

| Variant | Accuracy | Full-only right (medical/finance) | Variant-only right (medical/finance) |
|---|---|---|---|
| colony_haiku_a_no_correlation | 78.0% | 0/0 | 0/0 |
| colony_haiku_b_no_reputation | 78.0% | 0/0 | 0/0 |
| colony_haiku_c_no_verification | 80.0% | 0/7 | 0/9 |
| colony_haiku_d_plain_plurality | 79.0% | 0/6 | 0/7 |
| colony_haiku_e_single_model | 80.0% | 1/0 | 2/1 |

| Variant | Accuracy | Full-only right (medical/finance) | Variant-only right (medical/finance) |
|---|---|---|---|
| colony_local_a_no_correlation | 65.0% | 2/0 | 0/0 |
| colony_local_b_no_reputation | 64.0% | 2/1 | 0/0 |
| colony_local_c_no_verification | 77.0% | 5/0 | 1/14 |
| colony_local_d_plain_plurality | 58.0% | 6/10 | 1/6 |
| colony_local_e_single_model | 76.0% | 2/0 | 0/11 |

### S2 independence (evaluation errors, one sample per member)

| Colony | Effective independent members (raw) | Rate-adjusted (headline) | 95% interval | Error rates |
|---|---|---|---|---|
| colony_haiku | 2.02 | 1.60 | [1.13564, 2.32352] | {'haiku': 0.16, 'phi': 0.74, 'qwen': 0.2} |
| colony_haiku_withG | 2.22 | 1.61 | [1.191616, 2.187399] | {'gemma': 0.6, 'haiku': 0.16, 'phi': 0.74, 'qwen': 0.2} |
| colony_local | 1.86 | 1.34 | [1.072202, 1.730983] | {'gemma': 0.6, 'phi': 0.74, 'qwen': 0.2} |

### S3 abstain mode (tau 0.6, min support 1.0)

| Colony | Domain | Coverage | Accuracy when answering | 95% interval |
|---|---|---|---|---|
| colony_haiku | medical | 90.0% | 86.7% | 73.8-93.7% |
| colony_haiku | finance | 58.0% | 93.1% | 78.0-98.1% |
| colony_haiku | all | 74.0% | 89.2% | 80.1-94.4% |
| colony_local | medical | 76.0% | 89.5% | 75.9-95.8% |
| colony_local | finance | 12.0% | 100.0% | 61.0-100.0% |
| colony_local | all | 44.0% | 90.9% | 78.8-96.4% |

Risk-coverage points (both domains), by confidence threshold:

| Colony | tau | Coverage | Accuracy when answering |
|---|---|---|---|
| colony_haiku | 0.4 | 74.0% | 89.2% |
| colony_haiku | 0.5 | 74.0% | 89.2% |
| colony_haiku | 0.6 | 74.0% | 89.2% |
| colony_haiku | 0.7 | 74.0% | 89.2% |
| colony_haiku | 0.8 | 48.0% | 89.6% |
| colony_haiku | 0.9 | 0.0% | n/a |
| colony_haiku | 0.95 | 0.0% | n/a |
| colony_local | 0.4 | 48.0% | 87.5% |
| colony_local | 0.5 | 48.0% | 87.5% |
| colony_local | 0.6 | 44.0% | 90.9% |
| colony_local | 0.7 | 41.0% | 90.2% |
| colony_local | 0.8 | 15.0% | 93.3% |
| colony_local | 0.9 | 0.0% | n/a |
| colony_local | 0.95 | 0.0% | n/a |

### S4 calibration (10 bins; lower is better)

| Colony | Colony ECE | Colony Brier | Self-consistency ECE | Self-consistency Brier |
|---|---|---|---|---|
| colony_haiku | 0.135076 | 0.129497 | 0.126667 | 0.122222 |
| colony_local | 0.202418 | 0.15538 | 0.103333 | 0.132222 |

### S5 cold start (no warm-up) against the warm colony and the best member

| Colony | Domain | Cold vs warm gain | Cold vs best-member gain | Holm p (vs best) |
|---|---|---|---|---|
| colony_haiku | medical | +0.0 pts | -2.0 pts | 1.000 |
| colony_haiku | finance | +0.0 pts | -16.0 pts | 0.016 |
| colony_local | medical | -4.0 pts | +0.0 pts | 1.000 |
| colony_local | finance | -2.0 pts | -32.0 pts | 0.000 |

### S6 the 40 evaluation items W2 never used

| Test | Domain | Items | Gain | 95% interval | Holm p | Result |
|---|---|---|---|---|---|---|
| P1 | finance | 20 | -20.0 pts | -37.4 to +0.1 | 0.250 | no gain above 5 points (upper bound +0.001) |
| P1 | medical | 20 | +10.0 pts | -6.9 to +27.1 | 0.500 | not detected at this sample size |
| P2 | finance | 20 | -15.0 pts | -34.1 to +4.1 | 0.500 | no gain above 5 points (upper bound +0.041) |
| P2 | medical | 20 | -5.0 pts | -19.6 to +9.4 | 1.000 | not detected at this sample size |

### S7 with and without Gemma (against the matched-call best member)

| Colony | Baseline | Domain | Gain | 95% interval | Holm p | Result |
|---|---|---|---|---|---|---|
| colony_haiku_withG | solo4[haiku] | finance | -16.0 pts | -27.9 to -5.1 | 0.016 | no gain above 5 points (upper bound -0.051) |
| colony_haiku_withG | solo4[haiku] | medical | +4.0 pts | -5.3 to +13.8 | 0.625 | not detected at this sample size |
| colony_local_noG | solo2[qwen] | finance | -28.0 pts | -39.9 to -14.5 | 0.000 | no gain above 5 points (upper bound -0.145) |
| colony_local_noG | solo2[qwen] | medical | +0.0 pts | -6.1 to +6.1 | 1.000 | not detected at this sample size |

### S8 verification health

Verification checks that claims are grounded in the cited passage. It is not accuracy.

| Model | Status | Answers | Correct | Accuracy (95% interval) |
|---|---|---|---|---|
| all | failed | 392 | 205 | 52.3% (47.4-57.2%) |
| all | unverified | 589 | 171 | 29.0% (25.5-32.8%) |
| all | verified | 1478 | 1202 | 81.3% (79.3-83.2%) |
| gemma | failed | 149 | 48 | 32.2% (25.2-40.1%) |
| gemma | unverified | 5 | 3 | 60.0% (23.1-88.2%) |
| gemma | verified | 310 | 230 | 74.2% (69.0-78.7%) |
| haiku | failed | 52 | 40 | 76.9% (63.9-86.3%) |
| haiku | unverified | 10 | 9 | 90.0% (59.6-98.2%) |
| haiku | verified | 627 | 521 | 83.1% (80.0-85.8%) |
| phi | failed | 31 | 22 | 71.0% (53.4-83.9%) |
| phi | unverified | 574 | 159 | 27.7% (24.2-31.5%) |
| phi | verified | 3 | 2 | 66.7% (20.8-93.9%) |
| qwen | failed | 160 | 95 | 59.4% (51.6-66.7%) |
| qwen | verified | 538 | 449 | 83.5% (80.1-86.4%) |

### S9 cost (evaluation split)

| Arm | Calls | Prompt tokens | Completion tokens | Summed model latency (s) |
|---|---|---|---|---|
| colony_haiku | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_a_no_correlation | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_b_no_reputation | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_c_no_verification | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_cold | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_d_plain_plurality | 300 | 393200 | 60765 | 1626.4 |
| colony_haiku_e_single_model | 300 | 507237 | 129046 | 1080.6 |
| colony_haiku_withG | 400 | 512309 | 74798 | 2000.4 |
| colony_local | 300 | 343230 | 32631 | 1647.6 |
| colony_local_a_no_correlation | 300 | 343230 | 32631 | 1647.6 |
| colony_local_b_no_reputation | 300 | 343230 | 32631 | 1647.6 |
| colony_local_c_no_verification | 300 | 343230 | 32631 | 1647.6 |
| colony_local_cold | 300 | 343230 | 32631 | 1647.6 |
| colony_local_d_plain_plurality | 300 | 343230 | 32631 | 1647.6 |
| colony_local_e_single_model | 300 | 350559 | 39880 | 3279.3 |
| colony_local_noG | 200 | 224121 | 18598 | 1273.6 |
| solo1[gemma] | 100 | 119109 | 14033 | 374.0 |
| solo1[haiku] | 100 | 169079 | 42167 | 352.8 |
| solo1[phi] | 100 | 107268 | 5323 | 175.7 |
| solo1[qwen] | 100 | 116853 | 13275 | 1097.9 |
| solo2[qwen] | 200 | 233706 | 26489 | 2185.8 |
| solo3[gemma] | 300 | 357327 | 46199 | 1200.3 |
| solo3[haiku] | 300 | 507237 | 129046 | 1080.6 |
| solo3[phi] | 300 | 321804 | 15126 | 514.3 |
| solo3[qwen] | 300 | 350559 | 39880 | 3279.3 |
| solo4[haiku] | 400 | 676316 | 170705 | 1484.9 |

GPU time and dollars: {'hours': 0.98, 'usd': 1.0}

## Explained-null checklist (section 9)

Applies when a colony does not win. Thresholds for 'near 0' and 'about equal' are this report's proposals.

**colony_haiku** (won in some domain: False)

- Seats not independent (rate-adjusted effective members 1.60, flag below 1.5): False
- Weak members with weight near 0 (mean warm-up weights {'haiku': 1.596471221420848, 'phi': 0.3722202374737481, 'qwen': 1.4403314718846016}): none
- Verification did not separate good from bad (verified vs unverified accuracy intervals overlap): False
- Development correlation did not transfer (largest dev-to-eval shift 0.1556302002615213): False

**colony_local** (won in some domain: False)

- Seats not independent (rate-adjusted effective members 1.34, flag below 1.5): True
- Weak members with weight near 0 (mean warm-up weights {'gemma': 0.6931471805599453, 'phi': 0.3722202374737481, 'qwen': 1.4403314718846016}): none
- Verification did not separate good from bad (verified vs unverified accuracy intervals overlap): False
- Development correlation did not transfer (largest dev-to-eval shift 0.07585189267713417): False

## Deviations

None recorded by the analysis. Add any departure from the preregistration here.

