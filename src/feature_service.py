"""Server-side behavioural feature construction (STEP 3).

Until Step 2 the client (the demo UI) typed `amount_ratio`, `is_new_recipient`,
`tx_last_10min` and `just_received_money` straight into the API. That is unsafe in two ways:
  * a client (or an attacker) can lie about them and walk a scam under the threshold;
  * the "usual amount" and "known recipient" facts only exist in the account history, which
    the client should never need to hold.

Now the client sends RAW fields only (customer, recipient, amount, type, timestamp) and the
backend derives the risk features from its own history store. The definitions below are
deliberately identical to the batch code the model was trained with (src/features.py /
src/train_model.py). tests/test_feature_parity.py replays history through both paths and fails
if they ever disagree, which guards against training/serving skew.

Feature definitions (all measured at the transaction's own timestamp `t`)
  amount_ratio        amount / customer's usual amount (profile `avg_amount`)
  is_new_recipient    1 if this customer has no earlier transaction to this recipient
  tx_last_10min       this transaction + the customer's earlier outgoing transactions in (t-10min, t]
  just_received_money 1 if the customer received money in [t-15min, t)
  hour, is_night      hour of `t`; night = 00:00-05:59
The store is in memory (prototype). A production version would read the same facts from the
wallet's transaction database or a feature store, with the same definitions.
"""
import threading
from bisect import bisect_left, bisect_right, insort
from collections import Counter
from datetime import datetime, timedelta

import pandas as pd

EPOCH = datetime(1970, 1, 1)
BURST_WINDOW_S = 10 * 60
RECEIVED_WINDOW_S = 15 * 60
FEATURES = ["amount", "amount_ratio", "hour", "is_night", "is_new_recipient",
            "tx_last_10min", "just_received_money"]


class UnknownCustomer(KeyError):
    """The customer has no profile in the store (cold start is not handled in this prototype)."""


def _secs(ts: datetime) -> float:
    return (ts - EPOCH).total_seconds()


class FeatureStore:
    def __init__(self, customers: pd.DataFrame):
        self._lock = threading.RLock()
        self.usual = dict(zip(customers.customer_id, customers.avg_amount.astype(float)))
        self.sent = {}          # customer -> sorted epoch seconds of ALL outgoing transactions
        self.recv = {}          # account  -> sorted epoch seconds of incoming transactions
        self.first_seen = {}    # customer -> {recipient: earliest epoch seconds}
        self.send_counts = {}   # customer -> Counter of recipients of tx_type == "send"
        self.seen_events = set()

    # ------------------------------------------------------------------ loading
    def load_history(self, tx: pd.DataFrame):
        """Bulk-load completed transactions (columns: customer_id, receiver, timestamp, tx_type)."""
        d = tx[["customer_id", "receiver", "timestamp", "tx_type"]].copy()
        d["s"] = (d.timestamp - pd.Timestamp("1970-01-01")).dt.total_seconds()
        with self._lock:
            for cid, g in d.groupby("customer_id")["s"]:
                self.sent[cid] = sorted(g.tolist())
            for acc, g in d.groupby("receiver")["s"]:
                self.recv[acc] = sorted(g.tolist())
            for (cid, rcp), first in d.groupby(["customer_id", "receiver"])["s"].min().items():
                self.first_seen.setdefault(cid, {})[rcp] = first
            sends = d[d.tx_type == "send"]
            for (cid, rcp), n in sends.groupby(["customer_id", "receiver"]).size().items():
                self.send_counts.setdefault(cid, Counter())[rcp] = int(n)

    # ------------------------------------------------------------------ queries
    def has_customer(self, cid: str) -> bool:
        return cid in self.usual

    def profile(self, cid: str, k: int = 5) -> dict:
        if cid not in self.usual:
            raise UnknownCustomer(cid)
        with self._lock:
            top = [r for r, _ in self.send_counts.get(cid, Counter()).most_common(k)]
        return {"customer_id": cid, "usual_amount": self.usual[cid], "frequent_recipients": top}

    def compute(self, customer_id: str, recipient: str, amount: float, ts: datetime) -> dict:
        """Raw transaction -> model features (+ human-readable evidence). Does NOT change history."""
        if customer_id not in self.usual:
            raise UnknownCustomer(customer_id)
        t = _secs(ts)
        with self._lock:
            sent = self.sent.get(customer_id, [])
            n_prior = bisect_right(sent, t) - bisect_right(sent, t - BURST_WINDOW_S)
            first = self.first_seen.get(customer_id, {}).get(recipient)
            known = first is not None and first <= t
            recv = self.recv.get(customer_id, [])
            i = bisect_left(recv, t) - 1                       # latest receipt strictly before t
            since = (t - recv[i]) if i >= 0 else None
        usual = self.usual[customer_id]
        hour = ts.hour
        feats = {
            "amount": float(amount),
            "amount_ratio": float(amount) / usual,
            "hour": hour,
            "is_night": int(0 <= hour <= 5),
            "is_new_recipient": int(not known),
            "tx_last_10min": int(n_prior + 1),
            "just_received_money": int(since is not None and since <= RECEIVED_WINDOW_S),
        }
        evidence = {
            "usual_amount": usual,
            "known_recipient": bool(known),
            "outgoing_in_last_10min": int(n_prior),
            "minutes_since_last_incoming": None if since is None else round(since / 60, 1),
        }
        return {"features": feats, "evidence": evidence}

    # ------------------------------------------------------------------ updates
    def record(self, sender: str, receiver: str, ts: datetime, tx_type: str = "send",
               event_id: str = None) -> bool:
        """Add a COMPLETED transaction to history. Idempotent when event_id is given.
        Senders/receivers do not need a profile (counterparties are not customers)."""
        with self._lock:
            if event_id is not None:
                if event_id in self.seen_events:
                    return False
                self.seen_events.add(event_id)
            t = _secs(ts)
            insort(self.sent.setdefault(sender, []), t)
            insort(self.recv.setdefault(receiver, []), t)
            fs = self.first_seen.setdefault(sender, {})
            if receiver not in fs or t < fs[receiver]:
                fs[receiver] = t
            if tx_type == "send":
                self.send_counts.setdefault(sender, Counter())[receiver] += 1
            return True
