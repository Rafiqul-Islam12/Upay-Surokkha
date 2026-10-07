# Step 2 results: rules baseline vs ML (synthetic data, held-out chronological test split)

Test set: 63,252 transactions, 1,812 scam-like (2.86%), 2026-09-15 to 2026-09-29. Same split for every row.

## Rules used (no ML)
- **R1_big_to_new**: New recipient AND amount >= 3x customer's usual
- **R2_night_to_new**: New recipient AND time between 00:00-05:59
- **R3_rapid_repeat**: >= 3 transactions in 10 minutes
- **R4_pass_through**: Money was received <= 15 min ago and is being sent out now

Rules use only the same 7 features as the ML model. Parameters are round numbers fixed without looking at the test split.

## Table 1: main comparison
| setup | precision | recall | f1 | pr_auc | false_alarm_rate_% | flags_that_are_false_% | alerts_per_10k_tx | TP | FP | FN |
|---|---|---|---|---|---|---|---|---|---|---|
| 1a. Rules only (basic: R1-R3) | 0.352 | 0.668 | 0.461 | 0.296 | 3.63 | 64.8 | 544.2 | 1211.0 | 2231.0 | 601.0 |
| 1b. Rules only (extended: R1-R4) | 0.377 | 0.801 | 0.513 | 0.381 | 3.9 | 62.3 | 608.7 | 1452.0 | 2398.0 | 360.0 |
| 2. ML only (LightGBM, threshold 0.30) | 0.566 | 0.859 | 0.682 | 0.687 | 1.95 | 43.4 | 435.2 | 1557.0 | 1196.0 | 255.0 |
| 3a. ML + tiers: any warning (score >= 0.15) | 0.389 | 0.911 | 0.546 | 0.687 | 4.21 | 61.1 | 669.9 | 1650.0 | 2587.0 | 162.0 |
| 3b. ML + tiers: HIGH only (score >= 0.3) | 0.566 | 0.859 | 0.682 | 0.687 | 1.95 | 43.4 | 435.2 | 1557.0 | 1196.0 | 255.0 |
| 3c. ML + tiers: MEDIUM only (0.15 to <0.3) | 0.063 | 0.051 | 0.056 | 0.687 | 2.26 | 93.7 | 234.6 | 93.0 | 1391.0 | 1719.0 |
| 4. Integrated: ML + agent-liquidity signal | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| 5. (extra) Hybrid: ML OR rules R1-R4 | 0.395 | 0.901 | 0.549 | n/a | 4.07 | 60.5 | 652.9 | 1632.0 | 2498.0 | 180.0 |

False-alarm rate = false alarms / all legitimate transactions (the project's existing definition). For single-stage setups this is also the % of legitimate transactions that get a warning. 'Flags that are false' = 1 - precision. PR-AUC for rules uses the number of rules fired as the score.

## Table 2: matched operating points (read off the test curve; NOT deployable thresholds)
| comparison | rules_value | ML_value |
|---|---|---|
| ML recall at the SAME false-alarm rate as Rules R1-R4 | FAR 3.90%, recall 0.801 | recall 0.903 |
| ML false-alarm rate at the SAME recall as Rules R1-R4 | recall 0.801, FAR 3.90% | FAR 1.21% |

## Table 3: recall by scam pattern (test)
| pattern | n_scam_tx | Rules R1-R3 | Rules R1-R4 | ML @0.30 | ML @0.15 (warn) | Hybrid ML OR R1-R4 |
|---|---|---|---|---|---|---|
| new_recipient_big | 347 | 1.0 | 1.0 | 0.79 | 0.983 | 1.0 |
| night_tx | 285 | 0.996 | 0.996 | 0.996 | 0.996 | 0.996 |
| rapid_burst | 861 | 0.582 | 0.583 | 0.79 | 0.82 | 0.792 |
| refund_scam | 319 | 0.248 | 1.0 | 1.0 | 1.0 | 1.0 |

## Table 4: cost-sensitive comparison (false alarm = BDT 20, ASSUMPTION; missed scam = its actual amount, no recovery)
| policy | missed_scam_loss | false_alarm_cost | total_cost | saving_vs_no_system | scam_value_caught_% | FN | FP |
|---|---|---|---|---|---|---|---|
| No system (all scams missed) | 5035020 | 0 | 5035020 | 0 | 0.0 | 1812 | 0 |
| ML strict (>= 0.15) | 254878 | 51740 | 306618 | 4728402 | 94.9 | 162 | 2587 |
| ML balanced (>= 0.3) | 622942 | 23920 | 646862 | 4388158 | 87.6 | 255 | 1196 |
| ML lenient (>= 0.33) | 2233718 | 12260 | 2245978 | 2789042 | 55.6 | 459 | 613 |
| Rules R1-R3 | 1000247 | 44620 | 1044867 | 3990153 | 80.1 | 601 | 2231 |
| Rules R1-R4 | 530641 | 47960 | 578601 | 4456418 | 89.5 | 360 | 2398 |
| Hybrid ML(0.30) OR R1-R4 | 267612 | 49960 | 317572 | 4717448 | 94.7 | 180 | 2498 |

## Table 5: does the cheapest policy change if the false-alarm cost changes?
| false_alarm_cost_bdt | cheapest_policy | No system (all scams missed) | ML strict (>= 0.15) | ML balanced (>= 0.3) | ML lenient (>= 0.33) | Rules R1-R3 | Rules R1-R4 | Hybrid ML(0.30) OR R1-R4 |
|---|---|---|---|---|---|---|---|---|
| 5 | ML strict (>= 0.15) | 5035020 | 267813 | 628922 | 2236783 | 1011402 | 542631 | 280102 |
| 20 | ML strict (>= 0.15) | 5035020 | 306618 | 646862 | 2245978 | 1044867 | 578601 | 317572 |
| 100 | ML strict (>= 0.15) | 5035020 | 513578 | 742542 | 2295018 | 1223347 | 770441 | 517412 |
| 500 | ML balanced (>= 0.3) | 5035020 | 1548378 | 1220942 | 2540218 | 2115747 | 1729641 | 1516612 |
| 1000 | ML balanced (>= 0.3) | 5035020 | 2841878 | 1818942 | 2846718 | 3231247 | 2928641 | 2765612 |

## Note A: integrated ML + agent-liquidity signal
In this dataset 0 of 12,225 scam transactions are cash-outs and 0 go to an agent (scam transaction types: {'send': 12225}). The agent-liquidity forecast is about agent cash-out demand, so it carries no information about these scams. No integrated gain can be measured, so row 4 is left blank instead of inventing a number.
