"""Feature builder for ScamShield evaluation.

The logic is a line-by-line copy of the feature section of src/train_model.py
(so the evaluation uses EXACTLY the features the model was trained on).
train_model.py is intentionally left untouched in this step.

Returns the full transaction table with the engineered columns, sorted by time.
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

FEATURES = ["amount", "amount_ratio", "hour", "is_night", "is_new_recipient",
            "tx_last_10min", "just_received_money"]


def build_features(tx: pd.DataFrame = None, cust: pd.DataFrame = None) -> pd.DataFrame:
    if tx is None:
        tx = pd.read_csv(DATA / "transactions.csv", parse_dates=["timestamp"])
    if cust is None:
        cust = pd.read_csv(DATA / "customers.csv")
    tx = tx.merge(cust[["customer_id", "avg_amount"]], on="customer_id", how="left")
    tx = tx.sort_values("timestamp").reset_index(drop=True)

    tx["hour"] = tx["timestamp"].dt.hour
    tx["is_night"] = tx["hour"].between(0, 5).astype(int)
    tx["amount_ratio"] = tx["amount"] / tx["avg_amount"].fillna(tx["amount"].median())

    tx["pair"] = tx["customer_id"] + "_" + tx["receiver"]
    tx["is_new_recipient"] = (~tx.duplicated("pair", keep="first")).astype(int)

    tx = tx.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)
    counts = (tx.set_index("timestamp").groupby("customer_id")["amount"]
              .rolling("10min").count())
    tx["tx_last_10min"] = counts.values
    tx = tx.sort_values("timestamp").reset_index(drop=True)

    recv = tx[["receiver", "timestamp"]].rename(
        columns={"receiver": "customer_id", "timestamp": "recv_time"}).sort_values("recv_time")
    tx = tx.sort_values("timestamp")
    tx = pd.merge_asof(tx, recv, left_on="timestamp", right_on="recv_time",
                       by="customer_id", direction="backward", allow_exact_matches=False)
    tx["mins_since_received"] = (tx["timestamp"] - tx["recv_time"]).dt.total_seconds() / 60
    tx["just_received_money"] = (tx["mins_since_received"] <= 15).fillna(False).astype(int)
    tx = tx.sort_values("timestamp").reset_index(drop=True)
    return tx
