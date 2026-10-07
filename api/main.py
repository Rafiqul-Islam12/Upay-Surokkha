import sys, json, datetime, re
from datetime import timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT / "src"))

import joblib, shap
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from rules import (decide, template_message, reason_texts, feature_label,
                   REASON_BN, LOW, HIGH)
from feature_service import FeatureStore, UnknownCustomer
from cashout_saver import advice, demo_customers
from agent_float import agent_float, demo_agents, METRICS as AGENT_METRICS

app = FastAPI(title="upay Surokkha+ API")
bundle = joblib.load(ROOT / "models" / "scam_model.pkl")
model, FEATURES = bundle["model"], bundle["features"]
explainer = shap.TreeExplainer(model)

# --- Server-side feature store: behavioural features are computed HERE, never taken from the client.
_customers = pd.read_csv(ROOT / "data" / "customers.csv")
STORE = FeatureStore(_customers)
STORE.load_history(pd.read_csv(ROOT / "data" / "transactions.csv", parse_dates=["timestamp"]))

CASES = []  # অ্যানালিস্টের কেস তালিকা (ডেমোর জন্য মেমোরিতে, সিন্থেটিক ডেটা)

# ---------------------------------------------------------------- input validation (STEP 3)
BST = timezone(timedelta(hours=6))      # Bangladesh Standard Time (no DST). Timestamps are handled as BST wall-clock.
MAX_AMOUNT = 10_000_000.0               # sanity bound against typos/overflow, NOT a product limit
MAX_AGE_DAYS = 366                      # older timestamps are rejected (replay window)
MAX_FUTURE = timedelta(minutes=5)       # tolerated clock skew
MAX_BATCH = 200
ID_PATTERN = r"^[A-Za-z0-9_-]{1,32}$"   # no spaces, quotes, slashes or control characters
DERIVED_FIELDS = {"amount_ratio", "is_new_recipient", "tx_last_10min", "just_received_money",
                  "is_night", "hour"}


def now_bst() -> datetime.datetime:
    """Server clock as naive BST wall-clock time (a function so tests can replace it)."""
    return datetime.datetime.now(timezone.utc).astimezone(BST).replace(tzinfo=None)


def _to_bst_naive(ts: datetime.datetime) -> datetime.datetime:
    return ts.astimezone(BST).replace(tzinfo=None) if ts.tzinfo else ts


class RawTx(BaseModel):
    """What a client may send: raw transaction facts only."""
    model_config = ConfigDict(extra="forbid")   # no silent whitespace stripping: reject instead
    customer_id: str = Field(pattern=ID_PATTERN, description="Sender account id")
    recipient: str = Field(pattern=ID_PATTERN, description="Recipient account / merchant / agent id")
    amount: float = Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False, description="BDT")
    tx_type: Literal["send", "cashout", "merchant", "billpay"] = "send"
    timestamp: Optional[datetime.datetime] = Field(
        default=None, description="ISO-8601. Naive = BST wall-clock; defaults to server time.")

    @model_validator(mode="before")
    @classmethod
    def _no_client_side_features(cls, data):
        if isinstance(data, dict):
            bad = sorted(DERIVED_FIELDS & set(data))
            if bad:
                raise ValueError(f"{', '.join(bad)}: risk features are computed by the server and "
                                 f"must not be sent by the client. Send raw transaction fields only.")
        return data

    @model_validator(mode="after")
    def _sanity(self):
        if self.recipient == self.customer_id:
            raise ValueError("recipient must differ from customer_id")
        if self.timestamp is not None:
            ts = _to_bst_naive(self.timestamp)
            now = now_bst()
            if ts > now + MAX_FUTURE:
                raise ValueError("timestamp is in the future")
            if ts < now - timedelta(days=MAX_AGE_DAYS):
                raise ValueError(f"timestamp is older than {MAX_AGE_DAYS} days")
            self.timestamp = ts
        return self


class Event(RawTx):
    """A COMPLETED transaction reported to the history store (used by the payments feed / demo seeding)."""
    event_id: Optional[str] = Field(default=None, pattern=r"^[A-Za-z0-9_.:-]{1,64}$",
                                    description="Optional idempotency key; repeats are ignored.")
    timestamp: datetime.datetime = Field(description="Required for events.")


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: List[Event] = Field(min_length=1, max_length=MAX_BATCH)


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError):
    """422 with field + message only. The default handler echoes the offending input, which can crash
    on NaN/Infinity (not JSON-serialisable) and would reflect hostile input back to the caller."""
    errors = [{"loc": [str(x) for x in e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/score")
def score(tx: RawTx):
    ts = tx.timestamp or now_bst()
    try:
        computed = STORE.compute(tx.customer_id, tx.recipient, tx.amount, ts)
    except UnknownCustomer:
        raise HTTPException(404, detail={"code": "unknown_customer",
                                         "message": f"customer_id {tx.customer_id!r} has no profile"})
    t = computed["features"]          # features derived on the server from raw fields + history
    row = pd.DataFrame([t])[FEATURES]
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
            "amount": tx.amount, "recipient": tx.recipient, "customer_id": tx.customer_id,
            "reasons": reasons, "drivers": drivers, "recommended_action": d["recommended_action"],
            "tx": t, "evidence": computed["evidence"], "tx_time": ts.isoformat(timespec="seconds"),
            "created": datetime.datetime.now().strftime("%H:%M:%S"),
            # HIGH → মানুষের পর্যালোচনার অপেক্ষায়; MEDIUM → গ্রাহককে সতর্ক করা হয়েছে
            "status": "pending" if d["needs_human_review"] else "customer_warned",
        })
    return {"score": round(p, 3), "risk_score": round(p, 3), **d,
            "reasons": reasons, "reasons_bn": [REASON_BN.get(f, f) for f in top],
            "top_features": top, "drivers": drivers,
            "computed_features": t, "evidence": computed["evidence"],
            "feature_source": "server", "tx_time": ts.isoformat(timespec="seconds"),
            "thresholds": {"medium": LOW, "high": HIGH},
            "message": d["recommended_action"], "message_bn": msg_bn,
            "note": "Model output is a risk score; the recommended action is a policy suggestion. "
                    "No transaction is permanently blocked automatically."}

@app.post("/events")
def record_events(batch: EventBatch):
    """Record completed transactions in the history store (idempotent when event_id is set).
    Prototype: unauthenticated. In production this is fed by the payment system, not by clients."""
    new = sum(STORE.record(e.customer_id, e.recipient, e.timestamp, e.tx_type, e.event_id)
              for e in batch.events)
    return {"received": len(batch.events), "recorded": new, "duplicates": len(batch.events) - new}

@app.get("/customer/{cid}/context")
def customer_context(cid: str):
    """Read-only profile summary shown in the demo UI (usual amount, frequent recipients)."""
    if not re.match(ID_PATTERN, cid):
        raise HTTPException(422, detail="invalid customer id")
    try:
        return {"found": True, **STORE.profile(cid)}
    except UnknownCustomer:
        return {"found": False}

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
    vpath = ROOT / "models" / "validation_metrics.json"
    validation = json.loads(vpath.read_text(encoding="utf-8")) if vpath.exists() else None
    return {"scamshield": scam, "agent_forecast": AGENT_METRICS, "validation": validation}

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
