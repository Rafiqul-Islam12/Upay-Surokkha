import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent.parent   # যেকোনো ফোল্ডার থেকে চালানো যাবে
FEE_RATE = 0.014   # অনুমানকৃত হার (প্রোটোটাইপ); upay-এর অফিশিয়াল বর্তমান ফি নয়
SMALL_LIMIT = 1500
SHIFT_SHARE = 0.4

tx = pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"])
co = tx[tx.tx_type == "cashout"].copy()
co["week"] = ((co.timestamp.dt.day - 1) // 7 + 1).clip(upper=4)
MONTHS = max(co.timestamp.dt.to_period("M").nunique(), 1)

g = co.groupby("customer_id").agg(
    n=("amount", "count"), total=("amount", "sum"), avg=("amount", "mean"))
small = co[co.amount < SMALL_LIMIT].groupby("customer_id").agg(
    small_n=("amount", "count"), small_total=("amount", "sum"))
g = g.join(small).fillna(0)
g["monthly_n"] = g.n / MONTHS
g["small_share"] = g.small_n / g.n
g["saving"] = g.small_total / MONTHS * SHIFT_SHARE * FEE_RATE

# ML: গ্রাহকদের আচরণ অনুযায়ী ৩ দল
X = StandardScaler().fit_transform(g[["monthly_n", "avg", "small_share"]])
g["cluster"] = KMeans(n_clusters=3, random_state=42, n_init=10).fit_predict(X)
order = g.groupby("cluster").monthly_n.mean().sort_values().index.tolist()
NAMES = {order[0]: "কম ক্যাশ-আউট", order[1]: "নিয়মিত ক্যাশ-আউট",
         order[2]: "ঘন ঘন ক্যাশ-আউট"}

AVG_SAVING = float(g.saving.mean())

def demo_customers(k=5):
    return g.sort_values("saving", ascending=False).head(k).index.tolist()

def advice(cid: str) -> dict:
    if cid not in g.index:
        return {"found": False}
    r = g.loc[cid]
    weeks = co[co.customer_id == cid].groupby("week").amount.sum()
    peak = int(weeks.idxmax())
    msg = (f"এ মাসে আপনি গড়ে {r.monthly_n:.0f} বার ক্যাশ-আউট করেছেন "
           f"(মাসে প্রায় ৳{r.total / MONTHS:,.0f})। মাসের {peak} নম্বর সপ্তাহে "
           f"সবচেয়ে বেশি তোলেন। ৳{SMALL_LIMIT:,}-এর নিচের ছোট ক্যাশ-আউটের কিছু "
           f"মার্চেন্ট পেমেন্টে সরালে, অনুমানভিত্তিক হিসাবে, মাসে প্রায় ৳{r.saving:,.0f} বাঁচতে পারে (প্রোটোটাইপ অনুমান)।")
    return {"found": True, "monthly_count": round(float(r.monthly_n), 1),
            "monthly_total": round(float(r.total / MONTHS)),
            "small_share_pct": round(float(r.small_share) * 100),
            "peak_week": peak, "saving": round(float(r.saving), 1),
            "segment": NAMES[int(r.cluster)], "message_bn": msg,
            "avg_saving_all": round(AVG_SAVING, 1),
            "fee_rate_assumed": FEE_RATE, "small_limit": SMALL_LIMIT,
            "shift_share_assumed": SHIFT_SHARE}