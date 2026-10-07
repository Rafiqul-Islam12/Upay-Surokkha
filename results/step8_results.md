# Step 8: impact model (ScamShield ROI, Agent Copilot KPIs, Cost Advisor A/B pilot)

**Every number below comes from assumptions, not from real upay data.** Inputs marked ASSUMPTION are invented placeholders;
recall and false-alarm rate are our own synthetic-data results (Step 2 / Step 3). Edit `config/impact_assumptions.json`
(or the blue cells in `results/step8_impact_model.xlsx`) and rerun `python src/impact_model.py`.

## ScamShield: monthly impact (BDT million unless stated)

| Metric | Bad | Medium | Good |
|---|---|---|---|
| Prevented loss | 0.27 M | 5.63 M | 43.81 M |
| False-alarm cost | 2.94 M | 0.41 M | 0.21 M |
| Analyst time cost | 26.63 M | 4.59 M | 2.62 M |
| Customer-friction cost | 2.17 M | 0.16 M | 0.04 M |
| Run cost | 0.80 M | 0.50 M | 0.35 M |
| **Net monthly benefit** | -32.28 M | -0.03 M | 40.58 M |
| False alarms per month (count) | 676,932.3 | 223,932.8 | 194,883.0 |
| Precision at real prevalence | 0.03% | 0.60% | 2.58% |
| Analysts needed (FTE) | 591.9 | 131.3 | 87.4 |
| Payback (months) | n/a | n/a | 0.2 |
| ROI over horizon | -2036.53% | -103.36% | 5986.54% |
| Break-even false-alarm rate | n/a | 2.23% | 30.06% |
| Break-even scam rate | 1.2229% | 0.0302% | 0.0043% |

`n/a` = no payback (monthly net benefit is zero or negative) or no break-even exists. ROI below -100% means the system loses more over the horizon than the whole investment.

## Reading it honestly (generated from the numbers above)

- **Bad**: net -32.28 M per month (costs more than it earns), never pays back; no break-even exists; needs about 592 analysts if every flag is reviewed.
- **Medium**: net -0.03 M per month (costs more than it earns), never pays back; break-even false-alarm rate 2.23% vs assumed 2.24%; needs about 131 analysts if every flag is reviewed.
- **Good**: net 40.58 M per month (earns more than it costs), pays back in 0.2 months; break-even false-alarm rate 30.06% vs assumed 1.95%; needs about 87 analysts if every flag is reviewed.
- Recall and false-alarm rate in these scenarios are our own synthetic-data results: good = Step 2 test split, medium = adapted-scam row, bad = external validation (Step 3). They do not predict real performance.
- At a realistic (very low) scam rate almost every flag is a false alarm (see the precision row), so the false-alarm rate and the analyst cost per case dominate the result. Reviewing every flag by hand is the biggest cost line; triage and a lower false-alarm rate are the levers (see `step8_sensitivity_tornado.csv` and the Sensitivity sheet).
- Step 2 used a flat 20 BDT per false alarm. Here it is decomposed; the all-in value per scenario is the row 'All-in cost of one false alarm' in `step8_scenario_results.csv`.

## Agent Copilot

KPIs, formulas, data needed and guardrails: `step8_agent_copilot_kpis.csv` and the `AgentCopilot_KPIs` sheet. Example baseline / pilot values are placeholders (the forecast-error row uses our synthetic Step 1 numbers). The dataset has no cash balances, so stock-out hours and idle cash cannot be measured on synthetic data.

## Cost Advisor A/B pilot

Design: `step8_cost_advisor_ab_design.csv`. With the placeholder inputs (sigma 19.0 BDT, minimum detectable saving 2.0 BDT per customer-month) the pilot needs about 1,063 customers per arm (2,363 to enrol). No migration rate is assumed; it is measured.

## Which public sources to cite for each input

See `step8_assumptions.csv` (column `public_sources_to_cite`) and `step8_sources.csv`.
Only S1 was seen live; every other link must be opened and the exact figure and edition recorded before citing.
