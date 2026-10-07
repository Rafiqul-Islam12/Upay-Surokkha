# Step 8: impact model, KPIs and A/B pilot (what to say, what to cite)

**Honesty rule for the pitch:** nothing in this step is real upay data. Every input is an *ASSUMPTION* (invented placeholder),
a *CONVENTION* (statistical default) or *MEASURED_ON_SYNTHETIC* (our own Step 2/3 result). Say so on the slide.

## Files

| File | What it is |
|---|---|
| `config/impact_assumptions.json` | All inputs (edit here), with status, basis and source IDs |
| `src/impact_model.py` | Python model, CSV export, workbook builder (`python src/impact_model.py`) |
| `results/step8_impact_model.xlsx` | Spreadsheet with live formulas; blue cells on yellow are editable |
| `results/step8_*.csv`, `results/step8_results.md` | Exported tables and generated summary |
| `tests/test_impact_model.py` | Arithmetic, break-even, link to Step 2/3 results, workbook-vs-Python check |

The workbook has six sheets: `Assumptions`, `ScamShield_Model`, `Sensitivity`, `AgentCopilot_KPIs`, `CostAdvisor_ABPilot`, `Sources`.
After editing the JSON, rerun the script; after editing blue cells in Excel, the formulas update by themselves.
(The shipped workbook was recalculated with LibreOffice so values show in any viewer; a freshly rebuilt one is recalculated when opened in Excel.)

## 1. ScamShield formula

```
prevented loss = monthly transactions x scam rate x average loss x recall x intervention success
net benefit    = prevented loss - false-alarm cost - analyst time cost - customer-friction cost - monthly run cost
payback        = one-time cost / net benefit            (only if net benefit > 0, otherwise "never")
ROI            = (net benefit x horizon - one-time cost) / one-time cost
```

* `transactions x scam rate x loss x recall` is also shown on its own row ("literal formula"). Set intervention success to 100% to make the two equal.
  Intervention success was added because a flag does not stop every loss (customers ignore warnings).
* False-alarm cost = false alarms x (notification + support-contact rate x contact cost).
* Analyst time cost = (true flags + false flags) x share reviewed x minutes x analyst cost per productive minute. True flags are reviewed too.
* Customer-friction cost = false alarms x (abandonment x revenue lost + churn probability x customer margin).
* Also computed: analysts needed (FTE), precision at the assumed prevalence, all-in cost of one false alarm, break-even false-alarm rate and break-even scam rate.

### What the numbers say (with the placeholder inputs)

| | Bad | Medium | Good |
|---|---|---|---|
| Recall / false-alarm rate (own synthetic results) | 18.0% / 6.77% | 44.7% / 2.24% | 85.9% / 1.95% |
| Net benefit per month (BDT) | about -32.3 M | about -0.03 M | about +40.6 M |
| Payback | never | never (about break-even) | under 1 month |

* The spread is huge because the result depends on recall holding up **and** on a low false-alarm rate when real scams are very rare.
* Break-even is the useful pitch number: in the medium scenario ScamShield breaks even at a false-alarm rate of about 2.2%.
* Reviewing every flag by hand needs far more analysts than any bank would hire (about 90 to 590 FTE with these inputs). The honest message is
  that analyst triage and a lower false-alarm rate matter more than recall. Do not present the "good" column as a forecast.
* Step 2 used one flat 20 BDT per false alarm; the decomposed all-in cost here is 14 to 47 BDT depending on scenario.

## 2. Agent Copilot KPIs

Defined in sheet `AgentCopilot_KPIs` and `results/step8_agent_copilot_kpis.csv`: **stock-out hours**, **completed transactions**, **idle cash**,
plus forecast error and warning usefulness. Each has definition, formula, data needed and a guardrail. Read stock-out hours and idle cash together.
Baseline / pilot values in the sheet are EXAMPLES. The synthetic dataset has no balances, so these KPIs need real hourly balance snapshots
and failure-reason codes. Suggested design: randomise agents (stratified by area and size) to Copilot on/off for 8 weeks.

## 3. Cost Advisor A/B pilot (no fixed migration rate)

Sheet `CostAdvisor_ABPilot`: randomised, stratified, intention-to-treat design with a true control group, primary metric = net fees paid
per customer-month, secondary = measured migration of small cash-outs to digital payments, guardrails, decision rule based on the **lower
confidence bound**, sample-size calculator and an analysis template. Migration is an output of the pilot, never an input.

**Existing prototype note:** `src/cashout_saver.py` still uses `SHIFT_SHARE = 0.4` and `FEE_RATE = 0.014` for the in-app estimate. They are labelled
assumptions in the UI; once the pilot gives a measured migration rate, replace the fixed 0.4 with it (or show the pilot's lower-bound saving).
Also note a customer's saving is upay's lost fee revenue unless merchant revenue compensates; the workbook computes both.

## 4. Which public sources to cite for each input

Only **S1** was seen live while preparing this step. For every other source: open it, copy the exact figure, edition and date, and cite that. Never cite a source for a number you did not read in it.

| ID | Input | Bad / Medium / Good | Status | Public sources to cite |
|---|---|---|---|---|
| V1 | Monthly transactions scored by ScamShield (in-scope P2P sends) | 10,000,000 / 10,000,000 / 10,000,000 | ASSUMPTION | S1; S2 |
| R1 | Scam rate (share of scored transactions that are loss-causing scams) | 0.01% / 0.03% / 0.06% | ASSUMPTION | S3; S4; S5; S6 |
| R2 | Average loss per scam transaction | 3,000 / 6,000 / 10,000 | ASSUMPTION | S1; S3; S4 |
| R3 | Recall (share of scam transactions flagged) | 18% / 44.7% / 85.9% | MEASURED_ON_SYNTHETIC | S7 |
| R4 | Intervention success (share of flagged scams where the warning/hold really stops the loss) | 50% / 70% / 85% | ASSUMPTION | S8; S5 |
| F1 | False-alarm rate (share of legitimate transactions flagged) | 6.77% / 2.24% / 1.95% | MEASURED_ON_SYNTHETIC | S7 |
| A1 | Share of flags reviewed by a human analyst | 100% / 100% / 100% | ASSUMPTION | S9 |
| A2 | Review time per flagged case | 6 / 4 / 3 | ASSUMPTION | S9 |
| A3 | Fully loaded monthly cost of one analyst | 45,000 / 35,000 / 30,000 | ASSUMPTION | S10; S11 |
| A4 | Paid hours per analyst per month | 176 / 176 / 176 | ASSUMPTION | S10 |
| A5 | Productive share of paid time (utilization) | 65% / 65% / 65% | ASSUMPTION | S9 |
| F2 | Notification cost per flag (SMS / push) | 0.35 / 0.35 / 0.35 | ASSUMPTION | S12 |
| F3 | Share of false alarms that contact customer support | 10% / 5% / 3% | ASSUMPTION | S9 |
| F4 | Cost of one support contact | 40 / 30 / 25 | ASSUMPTION | S10; S9 |
| C1 | Abandonment rate after a false alarm (customer cancels the transfer) | 15% / 8% / 5% | ASSUMPTION | S9 |
| C2 | Revenue lost per abandoned transaction | 8 / 5 / 3 | ASSUMPTION | S12; S13 |
| C3 | Churn probability per false alarm | 0.2% / 0.05% / 0.02% | ASSUMPTION | S9 |
| C4 | Annual margin of an active customer | 1,000 / 600 / 400 | ASSUMPTION | S2; S13 |
| K1 | One-time cost (build, integration, security review, training) | 20,000,000 / 12,000,000 / 8,000,000 | ASSUMPTION | S10 |
| K2 | Monthly run cost (hosting, monitoring, retraining, support) | 800,000 / 500,000 / 350,000 | ASSUMPTION | S10 |
| H1 | ROI horizon | 12 / 12 / 12 | ASSUMPTION | team decision |
| B1 | Significance level alpha (two-sided) | 5% | CONVENTION | S15 |
| B2 | Statistical power (1 - beta) | 80% | CONVENTION | S15; S16 |
| B3 | Std. deviation of fees paid per eligible customer-month | 19 | MEASURED_ON_SYNTHETIC | S9; S15 |
| B4 | Minimum detectable effect (saving per customer-month) | 2 | ASSUMPTION | S13; S15 |
| B5 | Correlation between pre-period and pilot-period fees (for CUPED) | 50% | ASSUMPTION | S17 |
| B6 | Expected attrition / missing data | 10% | ASSUMPTION | S16 |
| B7 | Eligible customer base available for the pilot | 50,000 | ASSUMPTION | S2; S9 |
| B8 | Pilot duration | 8 | ASSUMPTION | S16 |
| B9 | Cash-out fee rate (customer pays at agent) | 0.014 | ASSUMPTION | S13 |
| B10 | Customer fee on the digital alternative (merchant payment) | 0 | ASSUMPTION | S13 |
| B11 | Merchant discount rate earned by upay on migrated value | 0.005 | ASSUMPTION | S2; S13 |
| B12 | Small cash-out limit defining eligible cash-outs | 1,500 | ASSUMPTION | S13 |

### Source list

| ID | Source | Where | Use |
|---|---|---|---|
| S1 | Bangladesh Bank, Mobile Financial Services (MFS) Statistics: Transaction Statistics | https://www.bb.org.bd/econdata/fin_digitalfstat/tab9.pdf | Industry transaction counts and values; derive average ticket size and a plausible upay share. Monthly counts are in the hundreds of millions industry-wide. |
| S2 | upay / UCB annual report and Bangladesh Bank MFS provider-wise statistics | https://www.bb.org.bd (search 'MFS statistics') | Upay's own volume, active customers, revenue. Prefer the company's own internal figure. |
| S3 | Bangladesh Financial Intelligence Unit (BFIU) annual report | https://www.bfiu.org.bd | Suspicious-transaction reports and typologies involving MFS; verify the current edition. |
| S4 | Bangladesh Police / CID cyber-crime statistics and the National Cyber Security Agency | https://www.police.gov.bd (verify current page) | Reported MFS-related fraud cases and losses; reported cases understate true incidence. |
| S5 | UK Finance, Annual Fraud Report (authorised push payment scams) | https://www.ukfinance.org.uk | International benchmark for APP-scam counts, values and share recovered; use only as a cross-check, not as a Bangladesh figure. |
| S6 | GSMA, State of the Industry Report on Mobile Money | https://www.gsma.com/sotir | Mobile-money fraud and consumer-protection context across markets. |
| S7 | This project: results/step2_main_results.csv, results/step3_scenarios.csv, models/metrics.json | (in repository) | Recall and false-alarm rate. Synthetic data; say so whenever you cite them. |
| S8 | UK Payment Systems Regulator, APP scams performance data | https://www.psr.org.uk | Share of APP-scam losses recovered or reimbursed; indicates how often a flagged payment can really be stopped. |
| S9 | Your own pilot measurements (time-and-motion study, call-centre tags, cancellation logs, retention) | (internal) | The only credible source for analyst minutes, support contacts, abandonment and churn. |
| S10 | Bangladesh Bureau of Statistics (BBS) wage and labour statistics; job-portal salary surveys | https://bbs.gov.bd | Salary level for analysts and call-centre staff; cross-check against upay HR. |
| S11 | Bangladesh Bank, Monthly Economic Trends / interest-rate statistics | https://www.bb.org.bd | Cost of funds for idle-cash valuation (Agent Copilot calculator). |
| S12 | BTRC (telecom regulator) SMS tariff / your SMS gateway invoice | https://www.btrc.gov.bd | Cost per SMS. |
| S13 | upay official tariff page / app charges and Bangladesh Bank circulars on MFS charges | https://www.upaybd.com (verify current tariff) | Send-money and cash-out fee schedule. A news report states Bangladesh Bank sets no fixed cash-out cap, so the provider's own tariff is the authority. |
| S14 | Helix Institute of Digital Finance / InterMedia agent-network surveys (Bangladesh) | https://www.helix-institute.com (verify availability) | Agent liquidity problems, stock-out frequency, agent commission levels. |
| S15 | Kohavi, Tang, Xu, Trustworthy Online Controlled Experiments (Cambridge University Press, 2020) | (book) | A/B test design, sample size, guardrail metrics. |
| S16 | Duflo, Glennerster, Kremer, Using Randomization in Development Economics Research: A Toolkit (2007) | https://economics.mit.edu (search the title) | Randomization units, stratification, spillovers, power. |
| S17 | Deng, Xu, Kohavi, Walker, Improving the Sensitivity of Online Controlled Experiments by Utilizing Pre-Experiment Data (CUPED, WSDM 2013) | (paper) | Variance reduction with pre-period data. |

## 5. Limitations (state them)

* All inputs are placeholders; the model shows *how* value would be computed, not how much.
* Recall and false-alarm rate come from synthetic data written by the same team; Step 3 shows they do not transfer under shift.
* The scam rate here (0.01% to 0.06%) is an invented range. The 2.9% in the synthetic data is injected by construction and must not be used.
* One average loss and one scam rate per scenario hide a skewed real distribution (few large losses).
* No discounting, no growth, no fraud-displacement effects, no regulatory or reputational value.
* Agent Copilot and Cost Advisor are defined for measurement, not valued in money, on purpose.
