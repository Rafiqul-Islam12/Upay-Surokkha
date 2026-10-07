# Step 3: limitations and what real Upay data would change (pitch text)

## Short paragraph for the pitch

Our model scores 0.98 AUC with 86% recall on a held-out split of the data it was built on, but we did not stop
there. We generated a second, independent synthetic world with different customers, different spending and timing
habits, and five scam types the model had never seen, then scored it with the same model and the same threshold.
Recall fell from 86% to 18%, and false alarms rose from 2% to about 7%. Two separate things happened. When only
honest customer behaviour changes, the model still catches about 86% of the scams it knows, but it raises roughly
three times as many false alarms. When the scam types change, it largely misses them: it learned four signatures,
not a general idea of fraud. The hand-written rules we compared against fail in the same places. We report this
because a synthetic score cannot tell you how a system behaves on real traffic. What we can claim is that the
pipeline is reproducible, the failure modes are measured instead of hidden, every decision goes to a human
analyst, and nothing is blocked automatically. With real Upay data we would (1) replace our guessed scam
typologies with confirmed fraud cases and analyst-labelled alerts, (2) compute behavioural features from real
account history (the serving path already does this on the server; only the data source changes), (3) pick the
operating threshold for the real fraud rate and the real cost of a false alarm, (4) add features the synthetic
world cannot express, such as device and SIM changes, recipient reputation and message or call context, and
(5) retrain on a rolling basis with drift monitoring and a fairness re-check on real demographics.

## Bullet version for a slide

- Same model, same threshold, independent synthetic world with unseen scam types: recall 86% -> 18%, false alarms 2% -> ~7%.
- Known scams in a changed world: recall holds (~86%) but false alarms triple. New scam types: mostly missed.
- Hand-written rules fail the same way, so the gap is about data and features, not about ML vs rules.
- Risk features are now computed on the server from raw fields; a client can no longer under-report them.
- Real data would change: labels, threshold, features, retraining cadence, monitoring, fairness evidence.

## What this validation does NOT show
- It does not show real-world performance. Both generators were written by the same team; the novel typologies
  are illustrative guesses, not observed Upay fraud.
- The shifts were chosen to stress the model. They are not a random sample of what will change in practice.
- Some novel typologies (a small "processing fee", the follow-up payments of a drip scam) look like honest
  behaviour in the 7 features. Low recall there is a feature-coverage limit as much as a model limit.
- Customer history is in memory and starts from synthetic data; a cold-start customer with no history is
  rejected by the API (404), not scored.
- The API has no authentication, and `POST /events` is unauthenticated: in production history must come from
  the payment system, not from callers.

## Reproduce
    python src/generate_validation_data.py      # optional: writes data/validation/ (not needed by the tests)
    python src/shift_test.py --seeds 5          # all tables and figures in results/step3_*
    python src/check_feature_parity.py          # server features vs training features
    python -m pytest tests -q                   # needs: pip install -r requirements-dev.txt
