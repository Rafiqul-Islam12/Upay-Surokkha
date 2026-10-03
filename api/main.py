import sys, json, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

import joblib, shap
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rules import (decide, template_message, reason_texts, feature_label,
                   REASON_BN, LOW, HIGH)
from cashout_saver import advice, demo_customers
from agent_float import agent_float, demo_agents, METRICS as AGENT_METRICS

app = FastAPI(title="upay Surokkha+ API")
bundle = joblib.load(ROOT / "models" / "scam_model.pkl")
model, FEATURES = bundle["model"], bundle["features"]
explainer = shap.TreeExplainer(model)

CASES = []  # অ্যানালিস্টের কেস তালিকা (ডেমোর জন্য মেমোরিতে, সিন্থেটিক ডেটা)

class Tx(BaseModel):
    amount: float
    amount_ratio: float
    hour: int
    is_new_recipient: int
    tx_last_10min: int = 1
    just_received_money: int = 0
    recipient: str = ""   # শুধু প্রদর্শনের জন্য (ডেমো নম্বর); মডেলে যায় না

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/score")
def score(tx: Tx):
    t = tx.model_dump()
    row = pd.DataFrame([{
        "amount": tx.amount, "amount_ratio": tx.amount_ratio, "hour": tx.hour,
        "is_night": int(0 <= tx.hour <= 5), "is_new_recipient": tx.is_new_recipient,
        "tx_last_10min": tx.tx_last_10min, "just_received_money": tx.just_received_money,
    }])[FEATURES]
    p = float(model.predict_proba(row)[0, 1])

    # SHAP: প্রতিটি ফিচার স্কোরে কতটা যোগ/বিয়োগ করেছে (log-odds)
    sv = explainer.shap_values(row)
    sv = sv[1] if isinstance(sv, list) else sv
    if getattr(sv, "ndim", 2) == 3:
        sv = sv[:, :, 1]
    contrib = pd.Series(sv[0], index=FEATURES)
    top = contrib[contrib > 0].sort_values(ascending=False).head(3).index.tolist()
    drivers = [{"feature": f, "label": feature_label(f, t), "shap": round(float(contrib[f]), 4),
                "direction": "increases risk" if contrib[f] > 0 else "reduces risk"}
               for f in contrib.abs().sort_values(ascending=False).head(5).index]

    d = decide(p)
    reasons = reason_texts(top, t)
    if not reasons:
        reasons = ["No strong risk signals found"] if d["risk_level"] == "LOW" else \
                  ["Combination of features raised the model score"]
    msg_bn = template_message(d["level"], top)

    if d["risk_level"] != "LOW":
        CASES.append({
            "id": len(CASES) + 1, "score": round(p, 3), "risk_level": d["risk_level"],
            "amount": tx.amount, "recipient": tx.recipient, "reasons": reasons,
            "drivers": drivers, "recommended_action": d["recommended_action"],
            "tx": t, "created": datetime.datetime.now().strftime("%H:%M:%S"),
            # HIGH → মানুষের পর্যালোচনার অপেক্ষায়; MEDIUM → গ্রাহককে সতর্ক করা হয়েছে
            "status": "pending" if d["needs_human_review"] else "customer_warned",
        })
    return {"score": round(p, 3), "risk_score": round(p, 3), **d,
            "reasons": reasons, "reasons_bn": [REASON_BN.get(f, f) for f in top],
            "top_features": top, "drivers": drivers,
            "thresholds": {"medium": LOW, "high": HIGH},
            "message": d["recommended_action"], "message_bn": msg_bn,
            "note": "Model output is a risk score; the recommended action is a policy suggestion. "
                    "No transaction is permanently blocked automatically."}

@app.get("/cases")
def cases():
    return CASES

@app.post("/cases/{case_id}/{decision}")
def review(case_id: int, decision: str):
    # মানুষের সিদ্ধান্ত: allow = নিরাপদ নিশ্চিত, escalate = পর্যালোচনার জন্য ধরে রাখা/এসকেলেট
    status = {"allow": "confirmed_safe", "escalate": "held_for_review"}.get(decision)
    if status is None:
        raise HTTPException(400, "decision must be 'allow' or 'escalate'")
    for c in CASES:
        if c["id"] == case_id:
            c["status"] = status
            return c
    raise HTTPException(404, "case not found")

@app.get("/metrics")
def metrics():
    path = ROOT / "models" / "metrics.json"
    scam = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return {"scamshield": scam, "agent_forecast": AGENT_METRICS}

@app.get("/customer/{cid}/savings")
def savings(cid: str):
    return advice(cid)

@app.get("/demo_customers")
def demo_list():
    return demo_customers()

@app.get("/agent/{aid}/float")
def float_forecast(aid: str):
    return agent_float(aid)

@app.get("/demo_agents")
def demo_agent_list():
    return demo_agents()
