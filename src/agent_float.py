import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent   # যেকোনো ফোল্ডার থেকে চালানো যাবে
CASH_SHARE = 0.25          # অনুমান: ফ্লোট ক্ষমতার ২৫% এজেন্ট নগদ হিসেবে রাখেন
WARN, DANGER = 0.8, 1.0    # বিজনেস রুল: চাহিদা/নগদ অনুপাত
HORIZON = 7
COLS = ["dow", "dom", "month_start", "lag1", "lag7", "mean7", "cap"]

tx = pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"])
agents = pd.read_csv(ROOT / "data" / "agents.csv").set_index("agent_id")
co = tx[tx.tx_type == "cashout"].copy()
co["date"] = co.timestamp.dt.normalize()
daily = co.groupby(["receiver", "date"]).amount.sum().unstack(0).fillna(0)
daily = daily.reindex(pd.date_range(daily.index.min(), daily.index.max()), fill_value=0)
daily = daily[[a for a in daily.columns if a in agents.index]]
LAST = daily.index.max()

def feats(s, d, cap):
    return [d.dayofweek, d.day, int(d.day <= 7),
            s.iloc[-1], s.iloc[-7], s.iloc[-7:].mean(), cap]

rows, ys, dates, base = [], [], [], []
for a in daily.columns:
    s, cap = daily[a], agents.loc[a, "float_capacity"]
    for i in range(7, len(s)):
        rows.append(feats(s.iloc[:i], s.index[i], cap))
        ys.append(s.iloc[i]); dates.append(s.index[i]); base.append(s.iloc[i-7:i].mean())
X = pd.DataFrame(rows, columns=COLS)
y, dates, base = np.array(ys), pd.Series(dates), np.array(base)

# শেষ ১৪ দিন টেস্ট, আগের সব ট্রেনিং
test = (dates > LAST - pd.Timedelta(days=14)).values
params = dict(n_estimators=200, learning_rate=0.05, num_leaves=15, random_state=42, verbose=-1)
m = lgb.LGBMRegressor(**params).fit(X[~test], y[~test])
mae_model = float(np.abs(m.predict(X[test]) - y[test]).mean())
mae_base = float(np.abs(base[test] - y[test]).mean())
METRICS = {"mae_model": round(mae_model), "mae_baseline": round(mae_base),
           "improvement_pct": round((1 - mae_model / mae_base) * 100, 1)}

# চূড়ান্ত মডেল: সব ডেটায়
model = lgb.LGBMRegressor(**params).fit(X, y)

def _forecast(a):
    s, cap = daily[a].copy(), agents.loc[a, "float_capacity"]
    out = []
    for k in range(1, HORIZON + 1):
        d = LAST + pd.Timedelta(days=k)
        p = max(float(model.predict(pd.DataFrame([feats(s, d, cap)], columns=COLS))[0]), 0)
        s.loc[d] = p
        out.append((d, p))
    return out

FORE = {a: _forecast(a) for a in daily.columns}

def _ratio(a):
    cash = agents.loc[a, "float_capacity"] * CASH_SHARE
    return max(p for _, p in FORE[a]) / cash

def demo_agents(k=6):
    return sorted(FORE, key=_ratio, reverse=True)[:k]

def agent_float(a: str) -> dict:
    if a not in FORE:
        return {"found": False}
    cash = float(agents.loc[a, "float_capacity"] * CASH_SHARE)
    fc = FORE[a]
    alert = next(((d, p) for d, p in fc if p / cash >= DANGER), None)
    warn = next(((d, p) for d, p in fc if p / cash >= WARN), None)
    if alert:
        d, p = alert
        level = "high"
        msg = (f"⚠️ {d.date()} নাগাদ আপনার নগদ শেষ হতে পারে "
               f"(পূর্বাভাস চাহিদা ৳{p:,.0f}, হাতে আনুমানিক ৳{cash:,.0f})। "
               f"অন্তত ৳{p - cash:,.0f} আগে থেকে রিব্যালান্স করুন।")
    elif warn:
        d, p = warn
        level = "medium"
        msg = f"{d.date()} তারিখে চাহিদা বাড়তে পারে (৳{p:,.0f})। নগদ বাড়িয়ে রাখা ভালো।"
    else:
        level = "low"
        msg = "আগামী ৭ দিন নগদ যথেষ্ট থাকার কথা।"
    peak_d, peak_p = max(fc, key=lambda x: x[1])
    if level == "high":
        rec = (f"Consider rebalancing liquidity before {alert[0].date()}. Forecast demand "
               f"BDT {alert[1]:,.0f} exceeds estimated cash BDT {cash:,.0f}; "
               f"a top-up of about BDT {alert[1] - cash:,.0f} may be needed.")
    elif level == "medium":
        rec = (f"Demand is expected to approach available cash around {warn[0].date()} "
               f"(BDT {warn[1]:,.0f}). Consider increasing cash on hand.")
    else:
        rec = "Estimated cash looks sufficient for the next 7 days."
    hist = daily[a].iloc[-14:]
    return {"found": True, "level": level, "message_bn": msg, "recommendation": rec,
            "peak_demand": round(peak_p), "peak_date": str(peak_d.date()),
            "cash_share_assumed": CASH_SHARE,
            "cash_on_hand": round(cash),
            "history": [{"date": str(d.date()), "demand": round(v)} for d, v in hist.items()],
            "forecast": [{"date": str(d.date()), "demand": round(p)} for d, p in fc],
            "metrics": METRICS}