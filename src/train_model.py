import json
import pandas as pd
import numpy as np
import joblib
import shap
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import precision_score, recall_score, roc_auc_score, confusion_matrix

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

tx = pd.read_csv(DATA / "transactions.csv", parse_dates=["timestamp"])
cust = pd.read_csv(DATA / "customers.csv")
tx = tx.merge(cust[["customer_id", "avg_amount"]], on="customer_id", how="left")
tx = tx.sort_values("timestamp").reset_index(drop=True)


tx["hour"] = tx["timestamp"].dt.hour
tx["is_night"] = tx["hour"].between(0, 5).astype(int)
tx["amount_ratio"] = tx["amount"] / tx["avg_amount"].fillna(tx["amount"].median())


tx["pair"] = tx["customer_id"] + "_" + tx["receiver"]
tx["is_new_recipient"] = (~tx.duplicated("pair", keep="first")).astype(int)


tx = tx.sort_values(["customer_id", "timestamp"]).reset_index(drop=True)
counts = (
    tx.set_index("timestamp")
    .groupby("customer_id")["amount"]
    .rolling("10min").count()
)
tx["tx_last_10min"] = counts.values
tx = tx.sort_values("timestamp").reset_index(drop=True)


recv = tx[["receiver", "timestamp"]].rename(columns={"receiver": "customer_id", "timestamp": "recv_time"})
recv = recv.sort_values("recv_time")
tx = tx.sort_values("timestamp")
tx = pd.merge_asof(tx, recv, left_on="timestamp", right_on="recv_time",
                   by="customer_id", direction="backward",
                   allow_exact_matches=False)
tx["mins_since_received"] = (tx["timestamp"] - tx["recv_time"]).dt.total_seconds() / 60
tx["just_received_money"] = (tx["mins_since_received"] <= 15).fillna(False).astype(int)
tx = tx.sort_values("timestamp").reset_index(drop=True)

tx["is_send"] = (tx["tx_type"] == "send").astype(int)

FEATURES = ["amount", "amount_ratio", "hour", "is_night", "is_new_recipient",
            "tx_last_10min", "just_received_money"]

train = tx[tx.split == "train"]
val = tx[tx.split == "val"]
test = tx[tx.split == "test"]


pos_w = (train.is_scam == 0).sum() / (train.is_scam == 1).sum()
model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                           scale_pos_weight=pos_w, random_state=42, verbose=-1)
model.fit(train[FEATURES], train.is_scam,
          eval_set=[(val[FEATURES], val.is_scam)],
          callbacks=[lgb.early_stopping(30, verbose=False)])


val_p = model.predict_proba(val[FEATURES])[:, 1]
best_t, best_f = 0.5, 0
for t in np.arange(0.1, 0.95, 0.05):
    pred = (val_p >= t).astype(int)
    p, r = precision_score(val.is_scam, pred, zero_division=0), recall_score(val.is_scam, pred)
    f = 2 * p * r / (p + r + 1e-9)
    if f > best_f:
        best_f, best_t = f, t


test_p = model.predict_proba(test[FEATURES])[:, 1]
test_pred = (test_p >= best_t).astype(int)
tn, fp, fn, tp = confusion_matrix(test.is_scam, test_pred).ravel()
print(f"থ্রেশহোল্ড: {best_t:.2f}")
print(f"AUC: {roc_auc_score(test.is_scam, test_p):.3f}")
print(f"Recall (স্ক্যাম ধরা): {tp/(tp+fn)*100:.1f}%")
print(f"Precision: {tp/(tp+fp)*100:.1f}%")
print(f"False alarm rate: {fp/(fp+tn)*100:.2f}%")

# UI-তে দেখানোর জন্য আসল টেস্ট মেট্রিক সংরক্ষণ (কোনো সংখ্যা বানানো হয়নি)
prec, rec = tp / (tp + fp), tp / (tp + fn)
METRICS = {"threshold": round(float(best_t), 2),
           "roc_auc": round(float(roc_auc_score(test.is_scam, test_p)), 3),
           "precision": round(float(prec), 3), "recall": round(float(rec), 3),
           "f1": round(float(2 * prec * rec / (prec + rec + 1e-9)), 3),
           "false_alarm_rate": round(float(fp / (fp + tn)), 4),
           "test_transactions": int(len(test)), "test_scam_transactions": int(test.is_scam.sum()),
           "data": "synthetic"}
(MODELS / "metrics.json").write_text(json.dumps(METRICS, indent=2), encoding="utf-8")

test = test.assign(pred=test_pred)
print("\nপ্যাটার্ন অনুযায়ী recall:")
print(test[test.is_scam == 1].groupby("pattern")["pred"].mean().round(3))
explainer = shap.TreeExplainer(model)
sample = test[FEATURES].sample(500, random_state=42)
sv = explainer.shap_values(sample)
sv = sv[1] if isinstance(sv, list) else sv
imp = pd.Series(np.abs(sv).mean(axis=0), index=FEATURES).sort_values(ascending=False)
print("\nসবচেয়ে গুরুত্বপূর্ণ ফিচার (SHAP):")
print(imp.round(4))

joblib.dump({"model": model, "features": FEATURES, "threshold": float(best_t)},
            MODELS / "scam_model.pkl")
print("\nsave model: models/scam_model.pkl")