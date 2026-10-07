"""Training/serving parity check (STEP 3).

Replays a transaction history in time order through the SERVER-SIDE FeatureStore
(compute features, then record the transaction) and compares every feature with the
BATCH code the model was trained on (src/features.py). Any disagreement is training/serving skew.

Run:  python src/check_feature_parity.py            # training data + a validation scenario
Writes results/step3_feature_parity.json
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from features import build_features                      # noqa: E402
from feature_service import FeatureStore                  # noqa: E402

COLS = ["amount_ratio", "is_new_recipient", "tx_last_10min", "just_received_money", "hour", "is_night"]


def replay(tx: pd.DataFrame, cust: pd.DataFrame) -> pd.DataFrame:
    """Online features for every row whose sender has a profile, in chronological order."""
    store = FeatureStore(cust)
    d = tx.sort_values(["timestamp", "tx_id"], kind="stable").reset_index(drop=True)
    out = []
    for r in d[["tx_id", "customer_id", "receiver", "amount", "timestamp", "tx_type"]].itertuples(index=False):
        ts = r.timestamp.to_pydatetime()
        if store.has_customer(r.customer_id):
            f = store.compute(r.customer_id, r.receiver, r.amount, ts)["features"]
            out.append({"tx_id": r.tx_id, **{c: f[c] for c in COLS}})
        store.record(r.customer_id, r.receiver, ts, r.tx_type)
    return pd.DataFrame(out)


def compare(tx: pd.DataFrame, cust: pd.DataFrame) -> dict:
    batch = build_features(tx, cust)[["tx_id"] + COLS]
    online = replay(tx, cust)
    m = online.merge(batch, on="tx_id", suffixes=("_online", "_batch"))
    res = {"rows_compared": int(len(m)), "features": {}}
    for c in COLS:
        a, b = m[c + "_online"].astype(float), m[c + "_batch"].astype(float)
        bad = (a - b).abs() > 1e-9
        res["features"][c] = {"mismatches": int(bad.sum()),
                              "match_rate": round(float(1 - bad.mean()), 6)}
    res["rows_with_any_mismatch"] = int(
        pd.concat([(m[c + "_online"].astype(float) - m[c + "_batch"].astype(float)).abs() > 1e-9
                   for c in COLS], axis=1).any(axis=1).sum())
    return res


def main():
    import generate_validation_data as gv
    tx = pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"])
    cust = pd.read_csv(ROOT / "data" / "customers.csv")
    report = {"training_history": compare(tx, cust)}
    c2, t2 = gv.generate(seed=100, **gv.SCENARIOS["external_validation"][1])
    report["validation_history"] = compare(t2, c2)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "step3_feature_parity.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for k, v in report.items():
        print(k, "rows", v["rows_compared"], "rows with any mismatch", v["rows_with_any_mismatch"])
        for c, x in v["features"].items():
            print(f"   {c:22s} mismatches {x['mismatches']:>6}  match {x['match_rate'] * 100:.4f}%")


if __name__ == "__main__":
    main()
