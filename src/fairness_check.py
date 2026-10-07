import pandas as pd, numpy as np, joblib, json
from pathlib import Path

ROOT = Path.cwd()
b = joblib.load(ROOT / "models" / "scam_model.pkl")
model, FEATURES, T = b["model"], b["features"], b["threshold"]

tx = pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"])
cust = pd.read_csv(ROOT / "data" / "customers.csv")
tx = tx.merge(cust[["customer_id", "avg_amount", "gender", "area", "age"]],
on="customer_id", how="left")
tx = tx.sort_values("timestamp").reset_index(drop=True)

tx["hour"] = tx.timestamp.dt.hour
tx["is_night"] = tx.hour.between(0, 5).astype(int)
tx["amount_ratio"] = tx.amount / tx.avg_amount.fillna(tx.amount.median())
tx["is_new_recipient"] = (~(tx.customer_id + "_" + tx.receiver).duplicated()).astype(int)
t2 = tx.set_index("timestamp")
tx = tx.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)
tx["tx_last_10min"] = (tx.set_index("timestamp").groupby("customer_id")["amount"]
.rolling("10min").count().values)
tx = tx.sort_values("timestamp").reset_index(drop=True)
recv = tx[["receiver", "timestamp"]].rename(columns={"receiver": "customer_id", "timestamp": "recv_time"}).sort_values("recv_time")
tx = pd.merge_asof(tx, recv, left_on="timestamp", right_on="recv_time", by="customer_id",
direction="backward", allow_exact_matches=False)
tx["just_received_money"] = (((tx.timestamp - tx.recv_time).dt.total_seconds() / 60) <= 15).fillna(False).astype(int)

test = tx[tx.split == "test"].copy()
test["pred"] = (model.predict_proba(test[FEATURES])[:, 1] >= T).astype(int)
test["age_group"] = pd.cut(test.age, [17, 30, 45, 70], labels=["18-30", "31-45", "46-69"])

out = {}
for col in ["gender", "area", "age_group"]:
    rows = {}
    for g, d in test.groupby(col, observed=True):
        pos, neg = d[d.is_scam == 1], d[d.is_scam == 0]
        rows[str(g)] = {
            "n": len(d),
            "recall": round(float(pos.pred.mean()), 3),
            "false_alarm_rate": round(float(neg.pred.mean()), 4),
        }
    out[col] = rows
    print(col, json.dumps(rows, indent=1))

(ROOT / "models" / "fairness.json").write_text(json.dumps(out, indent=2))
