# v4 pilot — findings

Hand-written. Every number comes from `results.json` / `REPORT.md` (same folder) unless another file is named.
Preregistration: `PREREGISTRATION.md`, commit 68ac613. These are pilot estimates: 15 runs per arm per world.

## Answer

**Go/no-go: unclear** (the pre-registered rule; independently re-derived from the raw cells).

- Paired on the 15 (world, seed, condition) keys all three arms share, DS-all recovered a mean G of **0.454**;
  F-Jev **0.194**; F-Laya **−0.028**.
- F-Jev minus DS-all: **−0.260**, 95% interval **[−0.593, −0.025]**. F-Laya minus DS-all: **−0.483**,
  **[−0.704, −0.244]**. Both framework arms recovered less of the gap than a strong model on every agent.
- Both framework arms were faster per decision: median **2.05 s** (F-Jev) and **1.50 s** (F-Laya) against
  **2.98 s** (DS-all). So the speed half of "Go" held, the outcome half did not.
- Not "no-go": F-Jev's 0.194 is above the 0.10 line.

## What drove it

**1. Foraging told us nothing about the models.** Every model arm delivered no food on the base task (S: 16.8 on
average). On the variants DS-all averaged 0.333 deliveries and every other model arm 0. Each model arm therefore gets
the same negative G in foraging (−0.393 to −0.404). This was pre-registered as expected after development runs. The
word state — direction to remembered food and nest, the agent's own 5×5 view in words, its last move — is not enough
for a stateless model to navigate around walls and other agents; the script keeps a map memory. Foraging, as built
here, is a floor, not a test.

**2. Colouring carries all the signal** (per-world tables in `REPORT.md`):

| Arm | Mean G (V1+V2) | Base score as share of S | Median s/decision |
|---|---|---|---|
| DS-all | 1.026 | 1.206 | 2.89 |
| F-Jev (queen + escalation) | 0.613 | 0.424 | 1.63 |
| F-Laya (queen + escalation) | 0.243 | 0.252 | 1.31 |
| F-Jev-noEsc | 0.926 | 0.709 | 1.31 |
| F-Jev-noQueen | **1.223** | **1.050** | 1.48 |
| Q-all Qwen3.5-9B | 0.906 | 0.801 | 2.80 |
| Q-all Qwen3.8-27B | 0.743 | 0.760 | 13.38 |
| Q-all Qwen3.5-0.8B | −0.389 | 0.000 | 1.86 |

A G above 1 means the arm beat the adapted script S′ on those variants.

**3. The queen and escalation each made Jev worse (exploratory — the ablations were not the primary comparison).**
In colouring, plain Jev workers with no queen (F-Jev-noQueen) had the highest mean G of any arm, 1.223, above DS-all's
1.026, at about half DS-all's seconds per decision (1.48 vs 2.89). Adding the queen dropped Jev to 0.926 without
escalation and 0.613 with it; on the base task the queened arms also fell well below S (share 0.424 for F-Jev). The
likely reason (a hypothesis, not tested here): the queen restricts the allowed actions for a whole group from
aggregate counts, which in colouring can remove the colour a given agent actually needs. With 15 runs and one world, this is a lead for the next study, not a result.

**4. Reports did not work.** Workers posted many reports but almost none were true: report precision 0.024 for
F-Jev (127 reports) and 0.000 for F-Laya (8,617 reports). A report is "true" only when the queen had forbidden every
good action; the queen rarely did, so reports were mostly noise from failed checks.

**5. Escalation ran far more than Phase 0 suggested.** At the pre-registered band (escalate a yes/no when
0.2 < P(yes) < 0.8) F-Jev escalated in 0.989 of its model decisions overall, 1.000 in foraging and 0.660 in colouring.
In Phase 0, Jev escalated 34.7% of judgement questions (`phase0/phase0-summary.json`). Live states made Jev far less
sure than the harvested ones.

**6. Laya was not usable.** Phase 0: judgement accuracy 0.413 against a 0.700 majority rate; move accuracy 0.253
against 0.381 chance (`phase0/phase0-summary.md`). In the pilot F-Laya was the weakest framework arm in both worlds.

**7. Bigger was not better on every agent.** In colouring Qwen3.5-9B (0.906) beat Qwen3.8-27B (0.743), and the 27B
model took 13.38 s per decision on one L40S under load. Qwen3.5-0.8B chose "noop" in every colouring decision and
never took a colour.

## Cost

Ledger and pod records (`results.json` → `spend_usd`, all-time including development): Nous **$1.456** of the $4.50
stop; Jev **$0.718** of $1.50; RunPod **$1.725** of $2.75. No hard stop was reached.

## Departures from the plan

- **Q-all Qwen3.5-27B** was cut before evaluation (pre-registered RunPod cut 1).
- **Q-all Qwen3.5-4B** was not run. The frozen pod script's pre-flight guard refused to start a pod
  ($1.725 spent + one hour at $1.09 > $2.75), the same effect as pre-registered cut 2. 284 of 314 planned cells ran.
- One colouring key (seed 1, V2) has undefined G for every arm: S and S′ both scored 1.0 there.
- The pooled "base share of S" in `REPORT.md` mixes deliveries with colouring fractions; read the per-world values.

## What this means for a full study

Not a go. Before any full study: (1) rebuild foraging so a stateless model can succeed at all (or give every arm
the same memory); (2) redesign the queen's signal so it cannot forbid the action an individual worker needs, or test
"no queen" as the main framework; (3) recalibrate escalation on live states rather than harvested ones; (4) drop Laya.
The operator decides.
