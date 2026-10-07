import numpy as np
import pandas as pd
from faker import Faker
from pathlib import Path

rng = np.random.default_rng(42)
fake = Faker()
Faker.seed(42)

N_CUST, N_AGENT, DAYS = 10000, 50, 90
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)


customers = pd.DataFrame({
    "customer_id": [f"C{i:05d}" for i in range(N_CUST)],
    "age": rng.integers(18, 70, N_CUST),
    "gender": rng.choice(["M", "F"], N_CUST, p=[0.55, 0.45]),
    "area": rng.choice(["urban", "rural"], N_CUST, p=[0.45, 0.55]),
    "avg_amount": rng.lognormal(7.0, 0.6, N_CUST).round(0),   
    "tx_per_month": rng.integers(3, 25, N_CUST),
})


agents = pd.DataFrame({
    "agent_id": [f"A{i:03d}" for i in range(N_AGENT)],
    "area": rng.choice(["urban", "rural"], N_AGENT, p=[0.4, 0.6]),
    "daily_cashout_base": rng.integers(30000, 150000, N_AGENT),
    "float_capacity": rng.integers(80000, 300000, N_AGENT),
})
AGENT_W = (agents.float_capacity / agents.float_capacity.sum()).values


rows = []
start = pd.Timestamp("2026-07-01")
cust_ids = customers.customer_id.values

contacts = {c: rng.choice(cust_ids, 6, replace=False) for c in cust_ids[:N_CUST]}

for _, c in customers.iterrows():
    n = int(c.tx_per_month * DAYS / 30)
    days = rng.integers(0, DAYS, n)
    hours = np.clip(rng.normal(14, 4, n), 6, 23).astype(int)
    late = rng.random(n) < 0.02                      # বৈধ রাতের লেনদেন
    hours = np.where(late, rng.integers(0, 6, n), hours)
    mins = rng.integers(0, 60, n)
    types = rng.choice(["send", "cashout", "merchant", "billpay"], n,
                       p=[0.35, 0.30, 0.25, 0.10])
    amts = rng.lognormal(np.log(c.avg_amount), 0.5, n)
    big = rng.random(n) < 0.03                       # বৈধ বড় অঙ্ক
    amts = np.where(big, amts * rng.uniform(3, 6, n), amts).round(0)
    for k in range(n):
        t = types[k]
        if t == "send":
            if rng.random() < 0.06:                  # বৈধ নতুন প্রাপক
                rec = f"C{rng.integers(0, N_CUST):05d}"
            else:
                rec = rng.choice(contacts[c.customer_id])
        elif t == "cashout":
            rec = rng.choice(agents.agent_id.values)
        else:
            rec = f"M{rng.integers(0, 300):03d}"
        rows.append((c.customer_id, rec, t, amts[k],
                     start + pd.Timedelta(days=int(days[k]), hours=int(hours[k]),
                                          minutes=int(mins[k])), 0, "normal"))

tx = pd.DataFrame(rows, columns=[
    "customer_id", "receiver", "tx_type", "amount", "timestamp", "is_scam", "pattern"])
# ক্যাশ-আউটে প্যাটার্ন: মাসের প্রথম ৭ দিন (বেতন) বেশি, বৃহস্পতিবার বেশি, শুক্রবার কম
ts = tx["timestamp"]
f = np.ones(len(tx))
f = np.where(ts.dt.day <= 7, f * 1.6, f)
f = np.where(ts.dt.dayofweek == 3, f * 1.25, f)
f = np.where(ts.dt.dayofweek == 4, f * 0.8, f)
is_co = (tx.tx_type == "cashout").values
tx.loc[is_co, "amount"] = (tx.loc[is_co, "amount"].values * f[is_co]).round(0)


n_scam = int(len(tx) * 0.02)
scam = []
victims = rng.choice(cust_ids, n_scam)
for v in victims:
    cust = customers.loc[customers.customer_id == v].iloc[0]
    base_t = start + pd.Timedelta(days=int(rng.integers(0, DAYS)),
                                  hours=int(rng.integers(0, 24)),
                                  minutes=int(rng.integers(0, 60)))
    p = rng.choice(["new_recipient_big", "refund_scam", "night_tx", "rapid_burst"],
                   p=[0.30, 0.25, 0.25, 0.20])
    new_rec = f"C{rng.integers(N_CUST, N_CUST + 3000):05d}"
    if p == "new_recipient_big":
        scam.append((v, new_rec, "send", cust.avg_amount * rng.uniform(3, 8), base_t, 1, p))
    elif p == "refund_scam":
        # সাধারণ অঙ্ক, মূল সংকেত: টাকা পাওয়ার ৩-১০ মিনিটে ফেরত
        amt = cust.avg_amount * rng.uniform(0.8, 2.0)
        scam.append((new_rec, v, "send", amt,
                     base_t - pd.Timedelta(minutes=int(rng.integers(3, 10))), 0, "refund_in"))
        scam.append((v, new_rec, "send", amt, base_t, 1, p))
    elif p == "night_tx":
        # সাধারণ অঙ্ক, মূল সংকেত: রাত ১-৪টা
        t = base_t.replace(hour=int(rng.integers(1, 5)))
        scam.append((v, new_rec, "send", cust.avg_amount * rng.uniform(0.8, 2.5), t, 1, p))
    else:  # rapid_burst: সাধারণ অঙ্ক, মূল সংকেত: ১০ মিনিটে ৩-৪টি
        for j in range(int(rng.integers(3, 5))):
            scam.append((v, f"C{rng.integers(N_CUST, N_CUST + 3000):05d}", "send",
                         cust.avg_amount * rng.uniform(0.8, 1.6),
                         base_t + pd.Timedelta(minutes=2 * j), 1, p))

scam_df = pd.DataFrame(scam, columns=tx.columns)
tx = pd.concat([tx, scam_df], ignore_index=True).sort_values("timestamp").reset_index(drop=True)
tx["tx_id"] = [f"T{i:07d}" for i in range(len(tx))]

n = len(tx)
tx["split"] = "train"
tx.loc[int(n * 0.70):int(n * 0.85), "split"] = "val"
tx.loc[int(n * 0.85):, "split"] = "test"

customers.to_csv(OUT / "customers.csv", index=False)
agents.to_csv(OUT / "agents.csv", index=False)
tx.to_csv(OUT / "transactions.csv", index=False)

print("গ্রাহক:", len(customers), "| এজেন্ট:", len(agents), "| লেনদেন:", len(tx))
print("স্ক্যাম %:", round(tx.is_scam.mean() * 100, 2))
print(tx.split.value_counts())
print(tx[tx.is_scam == 1].pattern.value_counts())