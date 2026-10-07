# Step 1: Repo audit (no code was changed in this step)

Everything below was read from the code or reproduced by running it. Line numbers refer to the files as received.

## 1. Architecture
```
src/generate_data.py --> data/{customers,agents,transactions}.csv   (synthetic, seed 42)
src/train_model.py   --> models/scam_model.pkl + models/metrics.json  (LightGBM, 7 features)
src/fairness_check.py--> models/fairness.json                          (offline script)
api/main.py  (FastAPI)  loads the .pkl, serves /score /cases /cases/{id}/{allow|escalate} /metrics
                        /customer/{id}/savings /agent/{id}/float
app/demo.py  (Streamlit, 1016 lines, 5 tabs) calls the API with requests
src/rules.py = POLICY layer (score -> LOW/MEDIUM/HIGH, English/Bangla text). It is NOT a rules detector.
src/agent_float.py, src/cashout_saver.py = supporting modules; they read the CSV and TRAIN at import time.
```

## 2. Where features are built
- Offline, from full history: `src/train_model.py` (and the same code is duplicated in `src/fairness_check.py`).
- At serving time the API trusts the client: `Tx` (api/main.py lines 22-28) requires `amount_ratio`, `is_new_recipient`, `tx_last_10min`, `just_received_money` from the caller. The Streamlit form sends them (app/demo.py ~lines 696-704). The server only computes `is_night`.
- Consequence: nothing in the repo computes these features from raw history at serving time, and a client can send any value (training/serving skew + trust problem).

## 3. Where the analyst queue is stored
`CASES = []` at api/main.py line 20: a Python list in process memory. Case id = `len(CASES)+1`. Lost on restart, not shared across workers, no database, no audit trail, no reviewer identity. Only MEDIUM/HIGH scores are stored.

## 4. How the model is trained / evaluated
- Chronological split 70/15/15 (train 295,173 / val 63,252 / test 63,252); test = 2026-09-15 to 2026-09-29.
- LightGBM (max 300 trees, early stopping 30 on validation logloss, `scale_pos_weight`), threshold chosen on validation by best F1 (0.30), test metrics computed once.
- Reproduced by running `src/train_model.py`: identical to shipped `metrics.json` (recall 0.859, precision 0.566, false-alarm 1.95%, AUC 0.981).
- Not present: PR-AUC, rules baseline, cost-based threshold, calibration check, independent/shifted data, confidence intervals.

## 5. Existing tests
None. No `tests/` folder, no CI file, no Docker file. (README section 9 says so.)

## 6. Other findings that matter for scoring
1. **The model has only 6 trees** (early stopping stopped at iteration 6 of 300). Its scores lie in 0.02-0.37 and are not probabilities: score ~0.34 corresponds to ~69% actual scam rate on test, score ~0.02 to 0%. A cut-off of 0.5 flags nothing. The UI/README should not present the score as "probability of scam".
2. **Synthetic data is circular**: the generator creates scams from the same signals the features measure (amount 3-8x usual to a new recipient; hour 1-4am; 3-4 transfers within 6 minutes; refund within 3-10 minutes). High scores on this data show the pipeline works, not that it will work on real traffic.
3. `amount_ratio` divides by `customers.csv avg_amount`, which is the generator's own parameter, not something computed from past transactions.
4. `is_new_recipient` is 1 for 79% of legitimate rows (first time a customer/receiver pair appears in 90 days, including bill-pay and merchants), so it is only useful in combination with other signals.
5. Existing `src/rules.py` is not a baseline (see section 1).
6. API: no authentication, SHAP computed per request (latency never measured).
7. Cost Advisor saving uses a placeholder fee rate (1.4%) and shift share (40%); both are assumptions in the code.

## 7. Prioritized TODO mapped to judge criteria
| # | Task | Criterion improved | Status |
|---|------|--------------------|--------|
| 1 | Rules baseline, ablation, PR curve, cost-sensitive table | AI/ML depth, Business impact | **Done in Step 2** |
| 2 | Server-side feature computation from raw history (client sends only raw fields) | Prototype, Scalability, AI/ML depth | todo |
| 3 | Persistent case store (SQLite) + audit log + reviewer identity + simple roles/token auth | Prototype, Responsible AI, Scalability | todo |
| 4 | Automated tests (features, rules, API, time-split no-leak) + one-command run | Prototype | todo |
| 5 | Independently generated test data (different seed AND different generating process) + distribution-shift test | AI/ML depth | todo |
| 6 | Fix early-stopping/score compression, check calibration, choose threshold by cost | AI/ML depth, Business impact | todo (changes reported numbers) |
| 7 | Load benchmark (p50/p95 latency, requests/sec, SHAP cost) | Scalability | todo |
| 8 | ROI with explicit, editable assumptions | Business impact | todo |
| 9 | Segment-wise fairness beyond gender/area/age, with synthetic-data caveat | Responsible AI | todo |
| 10 | Security plan (auth/roles/TLS) + mobile layout | Scalability, Prototype, Responsible AI | todo |
| 11 | Pitch focus: ScamShield as the one main problem; Agent Copilot / Cost Advisor as supporting | Problem relevance, Innovation | pitch task |
