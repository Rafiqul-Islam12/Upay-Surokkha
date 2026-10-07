# Step 3 results: external validation and distribution shift (synthetic data)

Model: `models/scam_model.pkl`, **unchanged**. Decision threshold: **0.30**, **unchanged**.
Nothing below was used to train the model or to choose the threshold. 5 independent draws per
scenario (seeds 100-104); rates are pooled over draws.
All numbers are produced by `python src/shift_test.py`.

## Key findings
1. **Harness check passes.** On the control (same world as training, new customers and seeds) recall is 85.8% and precision 53.2%, close to the Step 2 test split (85.9% / 56.6%). So the drop below comes from the shifts, not from the new pipeline.
2. **External validation drop (fixed threshold 0.30).** Recall 85.9% -> 18.0% (-68.0 pts), precision 56.6% -> 3.2% (-53.4 pts), false-alarm rate 1.95% -> 6.77%, AUC 0.981 -> 0.558.
3. **Part of the precision drop is just prevalence.** Scam share fell from 2.86% to 1.22%. At the original prevalence the same recall/false-alarm rate would give precision 7.3% (column 'precision_if_same_prevalence'). The rest of the drop is real.
4. **Which shift hurts what.** Legit-behaviour shift alone: recall 86.1%, false-alarm rate 6.80% (honest users who forward money, pay several bills in a row or send to new numbers look risky). Novel typologies alone: recall 7.8%. Adapted tactics on known scams: recall 44.7%.
5. **Ranking vs operating point (threshold-free view).** AUC is 0.954 when only legit behaviour shifts (the ranking mostly survives, but the fixed 0.30 cut now raises 6.80% false alarms), 0.792 when known scams adapt, and 0.521 for novel typologies alone (close to a coin flip: the score carries almost no signal for them). Best recall reachable at the Step 2 false-alarm budget on the external set: 0.0% (diagnostic only).
6. **Hand-written rules degrade too.** On the external set rules R1-R4 reach recall 20.2% at false-alarm rate 13.12% (ML: 18.0% at 6.77%). Neither approach covers typologies whose signature is outside the 7 features.

## Table 1: ScamShield at the fixed threshold, reference vs shifted worlds
| scenario | scam_share | recall | recall_95ci | precision | precision_if_same_prevalence | false_alarm_rate | auc | pr_auc |
|---|---|---|---|---|---|---|---|---|
| Step 2 test split (reference) | 2.86% | 85.9% | 84.2%-87.5% | 56.6% | 56.6% | 1.95% | 0.981 | 0.687 |
| Control (same world, new seed) | 2.89% | 85.8% | 85.1%-86.5% | 53.2% | 53.0% | 2.24% | 0.980 | 0.667 |
| Legit behaviour shift | 2.90% | 86.1% | 85.6%-86.6% | 27.5% | 27.2% | 6.80% | 0.954 | 0.286 |
| 5 novel scam typologies | 2.98% | 7.8% | 7.3%-8.3% | 9.5% | 9.1% | 2.28% | 0.521 | 0.061 |
| Evasion (known scams, adapted) | 2.92% | 44.7% | 43.7%-45.6% | 37.5% | 37.0% | 2.24% | 0.792 | 0.388 |
| Volume / mix shift | 1.46% | 86.3% | 85.7%-86.9% | 15.3% | 26.4% | 7.09% | 0.943 | 0.123 |
| Scam surge (3x volume) | 8.04% | 86.1% | 85.7%-86.5% | 75.7% | 51.3% | 2.42% | 0.979 | 0.824 |
| EXTERNAL VALIDATION (all shifts) | 1.22% | 18.0% | 17.1%-18.9% | 3.2% | 7.3% | 6.77% | 0.558 | 0.021 |

- `recall_95ci`: Wilson interval on pooled counts (does not include variation of the generator itself; see seed range in `step3_scenarios_by_seed.csv`).
- `precision_if_same_prevalence`: precision recomputed with the scenario's recall and false-alarm rate but the Step 2 scam share (2.86%). It separates "fewer scams in the traffic" from "worse model".
- Reference row = Step 2 held-out test split, recomputed live (matches `models/metrics.json`).

## Table 2: diagnostics and the Step 2 rules baseline
| scenario | best_recall_at_ref_far_(diagnostic) | incident_recall | rules_recall | rules_precision | rules_far |
|---|---|---|---|---|---|
| Step 2 test split (reference) | 85.9% | n/a | 80.1% | 37.7% | 3.90% |
| Control (same world, new seed) | 84.2% | 94.3% | 79.3% | 34.2% | 4.53% |
| Legit behaviour shift | 0.0% | 94.0% | 80.3% | 15.4% | 13.16% |
| 5 novel scam typologies | 7.7% | 11.0% | 11.5% | 7.2% | 4.57% |
| Evasion (known scams, adapted) | 44.7% | 32.0% | 20.6% | 12.0% | 4.52% |
| Volume / mix shift | 0.0% | 94.0% | 80.6% | 9.2% | 11.75% |
| Scam surge (3x volume) | 80.4% | 94.4% | 79.7% | 59.3% | 4.79% |
| EXTERNAL VALIDATION (all shifts) | 0.0% | 27.1% | 20.2% | 1.9% | 13.12% |

- `best_recall_at_ref_far_(diagnostic)`: the best recall ANY threshold could reach while keeping the false-alarm rate at or below the Step 2 rate (1.95%) on that scenario. 0.0% means no threshold can flag anything without exceeding that false-alarm budget. **Oracle-style diagnostic, not a deployable setting** (it needs labels from the shifted world).
- `incident_recall`: share of scam *incidents* (multi-transaction scams) with at least one flagged transaction.
- Rules = R1-R4 from Step 2 (round-number parameters, not tuned on any of this data).

## Table 3: external validation, recall by scam typology
| pattern | group | n | ml_recall | rules_recall | description |
|---|---|---|---|---|---|
| account_takeover_drain | novel | 1589 | 0.0% | 12.4% | 2-4 evening transfers (1.5-3.5x) to one mule, spaced 4-9 min |
| emergency_impersonation | novel | 711 | 0.4% | 24.8% | 'family emergency': 1.5-4x to a new number, daytime/evening |
| investment_drip | novel | 1929 | 0.4% | 0.4% | 3-5 normal-sized transfers to one new account over 1-3 days |
| mule_pass_through | novel | 1275 | 39.6% | 28.2% | receives a large sum, forwards it in chunks 18-40 min later |
| prize_fee_scam | novel | 668 | 0.0% | 0.1% | SMALL 'processing fee' (0.25-0.9x) to a new account, daytime |
| new_recipient_big | known | 156 | 84.0% | 100.0% | big amount (3-8x usual) to a new recipient |
| night_tx | known | 147 | 100.0% | 100.0% | ordinary amount to a new recipient at 1-4 AM |
| rapid_burst | known | 422 | 78.7% | 57.3% | 3-4 transfers to new recipients within minutes |
| refund_scam | known | 139 | 100.0% | 100.0% | 'refund' sent minutes after receiving money |

Typologies marked `novel` were written for this step and were never part of training. They are illustrative
guesses at plausible mobile-money fraud, **not** observed upay fraud. Some (`prize_fee_scam`,
`investment_drip` follow-ups) are by construction hard to separate from honest behaviour using only the 7 features:
the failure there is as much a feature-coverage limit as a model limit.

## Scenario definitions
- **Control (same world, new seed)** (`control_train_like`): Control: training-like world and the 4 known typologies, fresh seed/customers. Should match the Step 2 test numbers; if not, the harness is wrong.
- **Legit behaviour shift** (`environment_only`): Legit behaviour changes (amounts, hours, volume, contacts, legit bursts and pass-through); scam tactics unchanged (4 known typologies).
- **5 novel scam typologies** (`novel_typologies_only`): Training-like legit world, but ONLY the 5 new scam typologies.
- **Evasion (known scams, adapted)** (`tactic_evasion`): Training-like legit world; the 4 known typologies with adapted tactics (smaller amounts, evening not night, slower bursts, delayed refunds).
- **Volume / mix shift** (`volume_mix_shift`): Legit volume up (heavier users, more merchant/bill traffic, more honest bursts); scam count unchanged so prevalence halves.
- **Scam surge (3x volume)** (`scam_surge`): Campaign surge: same world as control but 3x the scam volume (prevalence up).
- **EXTERNAL VALIDATION (all shifts)** (`external_validation`): MAIN external set: shifted legit world + 20% known / 80% novel typologies, lower prevalence (1.2%).

## How to read this honestly
- All data is synthetic and produced by two generators written by the same team. A different generator
  measures robustness to *the shifts we thought of*, not to real-world drift.
- The legit-world shift and the novel typologies were designed to stress the model. They are not a random sample of the future.
- Figures: `results/step3_shift_summary.png`, `results/step3_typology_recall.png`.
