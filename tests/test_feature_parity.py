"""Training/serving parity: the server-side FeatureStore must reproduce the batch training features."""
import pandas as pd
from conftest import ROOT

from check_feature_parity import compare


def test_parity_on_training_history_first_two_weeks():
    tx = pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"])
    cust = pd.read_csv(ROOT / "data" / "customers.csv")
    sub = tx[tx.timestamp < tx.timestamp.min() + pd.Timedelta(days=14)]
    res = compare(sub, cust)
    assert res["rows_compared"] > 50_000
    for feat, x in res["features"].items():
        # same-timestamp ties are ordered arbitrarily by the batch code; allow 0.1% for them
        assert x["match_rate"] >= 0.999, (feat, x)
    for feat in ("amount_ratio", "just_received_money", "hour", "is_night"):
        assert res["features"][feat]["mismatches"] == 0


def test_parity_on_validation_generator():
    import generate_validation_data as gv
    env = gv.Env(n_cust=400, warmup_days=20, eval_days=10, seconds=True)
    cust, tx = gv.generate(env=env, mix=gv.MIXED_MIX, scam_rate=0.02, seed=5)
    res = compare(tx, cust)
    assert res["rows_with_any_mismatch"] == 0, res
