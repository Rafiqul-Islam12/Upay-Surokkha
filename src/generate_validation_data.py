"""STEP 3: SEPARATE synthetic generator used ONLY for validation and distribution-shift tests.

Why this file exists
--------------------
src/generate_data.py produced the data the model was trained on. If we only ever test on a
split of that same generator, the test measures "can the model recover the rules we wrote",
not "does it survive a world that looks different". This generator is deliberately different:

  * different random seed streams and a different customer population (ids start with "X"),
  * different legitimate behaviour (amounts, hours, volume, transaction mix, contacts),
  * different fraud typologies (5 NEW ones the model never saw) plus the 4 old ones,
  * a warm-up period so "new recipient" is not inflated by a cold start (see below),
  * incident ids, so we can also measure "was this scam incident caught at all".

RULES
-----
  * Nothing here is ever used for training or threshold selection. train_model.py reads only
    data/transactions.csv. Output goes to data/validation/ and ids carry a "V"/"X" prefix,
    which tests/test_no_leakage.py checks.
  * The typologies are ILLUSTRATIVE guesses at plausible mobile-money fraud, written by us.
    They are not claims about real upay fraud.

Why a warm-up window
--------------------
`is_new_recipient` is computed as "first time this pair appears in the data". On the first
days of any dataset every saved contact looks "new". The Step 2 test split was the last 15%
of a 90-day history, so most contacts were already seen. If we scored a fresh 30-day set
without a warm-up, the model would look worse only because of this artefact. So we generate
`warmup_days` + `eval_days`, compute features over everything, and score only the eval part.

Usage
-----
    python src/generate_validation_data.py            # writes data/validation/ext_val_*.csv
    python src/generate_validation_data.py --seed 7   # another draw
Other modules import `generate()` and `SCENARIOS` directly (no files needed).
"""
import argparse
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "validation"

KNOWN = ["new_recipient_big", "refund_scam", "night_tx", "rapid_burst"]          # seen in training
NOVEL = ["account_takeover_drain", "prize_fee_scam", "investment_drip",         # never seen
         "mule_pass_through", "emergency_impersonation"]
TYPE_NAMES = ["send", "cashout", "merchant", "billpay"]


# ------------------------------------------------------------------ environment (legit world)
@dataclass(frozen=True)
class Env:
    """Parameters of the LEGITIMATE world. Scam typologies are chosen separately."""
    n_cust: int = 5000
    warmup_days: int = 60
    eval_days: int = 30
    start: str = "2026-10-01"
    prefix: str = "X"
    avg_mu: float = 7.0          # customer's usual amount ~ lognormal(avg_mu, avg_sd)
    avg_sd: float = 0.6
    tpm_lo: int = 3              # transactions per month, uniform integer range
    tpm_hi: int = 25
    contacts_lo: int = 6         # saved contacts per customer
    contacts_hi: int = 6
    hour_mu: float = 14.0        # daytime activity peak
    hour_sd: float = 4.0
    late_p: float = 0.02         # legit late-night share
    amt_sigma: float = 0.5
    big_p: float = 0.03          # legit unusually large share
    big_lo: float = 3.0
    big_hi: float = 6.0
    new_rec_p: float = 0.06      # legit send to a brand-new recipient
    type_p: tuple = (0.35, 0.30, 0.25, 0.10)   # send, cashout, merchant, billpay
    burst_p: float = 0.0         # share of tx that start a LEGIT burst (bill-pay sprees etc.)
    trader_share: float = 0.0    # customers who legitimately receive-then-forward money
    seconds: bool = False        # training data had minute resolution only


# What the training generator looked like (used for the control and the isolated-shift scenarios).
TRAIN_LIKE = Env()

# The "different world" used for the main external validation. Every knob moved on purpose.
SHIFTED = Env(avg_mu=7.3, avg_sd=0.75, tpm_lo=3, tpm_hi=40, contacts_lo=4, contacts_hi=10,
              hour_mu=16.0, hour_sd=4.5, late_p=0.05, amt_sigma=0.7,
              big_p=0.06, big_lo=2.0, big_hi=7.0, new_rec_p=0.12,
              type_p=(0.30, 0.22, 0.33, 0.15), burst_p=0.02, trader_share=0.03, seconds=True)

# Volume / mix shift only: heavier users, merchant- and bill-heavy traffic, more legit bursts.
VOLUME_MIX = replace(TRAIN_LIKE, tpm_lo=6, tpm_hi=50, type_p=(0.25, 0.15, 0.40, 0.20),
                     burst_p=0.04, late_p=0.05, new_rec_p=0.10, trader_share=0.03, seconds=True)


# ------------------------------------------------------------------ typology mixes (incident shares)
KNOWN_MIX = {"new_recipient_big": 0.30, "refund_scam": 0.25, "night_tx": 0.25, "rapid_burst": 0.20}
NOVEL_MIX = {k: 0.2 for k in NOVEL}
MIXED_MIX = {**{k: 0.2 * v for k, v in KNOWN_MIX.items()},          # 20% known, 80% novel
             **{k: 0.8 * v for k, v in NOVEL_MIX.items()}}

DESCRIPTIONS = {
    "new_recipient_big": "[known] big amount (3-8x usual) to a new recipient",
    "refund_scam": "[known] 'refund' sent minutes after receiving money",
    "night_tx": "[known] ordinary amount to a new recipient at 1-4 AM",
    "rapid_burst": "[known] 3-4 transfers to new recipients within minutes",
    "account_takeover_drain": "[novel] 2-4 evening transfers (1.5-3.5x) to one mule, spaced 4-9 min",
    "prize_fee_scam": "[novel] SMALL 'processing fee' (0.25-0.9x) to a new account, daytime",
    "investment_drip": "[novel] 3-5 normal-sized transfers to one new account over 1-3 days",
    "mule_pass_through": "[novel] receives a large sum, forwards it in chunks 18-40 min later",
    "emergency_impersonation": "[novel] 'family emergency': 1.5-4x to a new number, daytime/evening",
}


# ------------------------------------------------------------------ legit traffic
def _make_customers(rng, env):
    n = env.n_cust
    ids = np.array([f"{env.prefix}{i:05d}" for i in range(n)])
    cust = pd.DataFrame({
        "customer_id": ids,
        "age": rng.integers(18, 70, n),
        "gender": rng.choice(["M", "F"], n, p=[0.55, 0.45]),
        "area": rng.choice(["urban", "rural"], n, p=[0.45, 0.55]),
        "avg_amount": np.maximum(rng.lognormal(env.avg_mu, env.avg_sd, n).round(0), 50.0),
        "tx_per_month": rng.integers(env.tpm_lo, env.tpm_hi + 1, n),
    })
    return cust, ids


def _legit(rng, env, cust, ids):
    n, total_days = env.n_cust, env.warmup_days + env.eval_days
    start = pd.Timestamp(env.start)
    avg = cust.avg_amount.values
    n_i = (cust.tx_per_month.values * total_days / 30).astype(int)
    ci = np.repeat(np.arange(n), n_i)
    m = len(ci)

    # contacts: per-customer count, drawn from the same population (never self)
    kc = rng.integers(env.contacts_lo, env.contacts_hi + 1, n)
    kmax = int(kc.max())
    contacts = rng.integers(0, n, (n, kmax))
    self_hit = contacts == np.arange(n)[:, None]
    contacts = np.where(self_hit, (contacts + 1) % n, contacts)

    day = rng.integers(0, total_days, m)
    hour = np.clip(rng.normal(env.hour_mu, env.hour_sd, m), 6, 23).astype(int)
    late = rng.random(m) < env.late_p
    hour = np.where(late, rng.integers(0, 6, m), hour)
    minute = rng.integers(0, 60, m)
    second = rng.integers(0, 60, m) if env.seconds else np.zeros(m, dtype=int)
    ts = (start + pd.to_timedelta(day, "D") + pd.to_timedelta(hour, "h")
          + pd.to_timedelta(minute, "min") + pd.to_timedelta(second, "s"))

    ttype = rng.choice(4, m, p=list(env.type_p))
    amt = rng.lognormal(np.log(avg[ci]), env.amt_sigma, m)
    big = rng.random(m) < env.big_p
    amt = np.where(big, amt * rng.uniform(env.big_lo, env.big_hi, m), amt)
    # same weekly cash-out rhythm as the training world (salary week, Thursday up, Friday down)
    f = np.ones(m)
    f = np.where(ts.day <= 7, f * 1.6, f)
    f = np.where(ts.dayofweek == 3, f * 1.25, f)
    f = np.where(ts.dayofweek == 4, f * 0.8, f)
    amt = np.where(ttype == 1, amt * f, amt)
    amt = np.maximum(amt.round(0), 10.0)

    newr = rng.random(m) < env.new_rec_p
    col = (rng.random(m) * kc[ci]).astype(int)
    send_idx = np.where(newr, rng.integers(0, n, m), contacts[ci, col])
    send_idx = np.where(send_idx == ci, (send_idx + 1) % n, send_idx)
    recv = np.empty(m, dtype=object)
    recv[:] = [f"M{x:03d}" for x in rng.integers(0, 300, m)]
    is_send, is_cash = ttype == 0, ttype == 1
    recv[is_send] = ids[send_idx[is_send]]
    recv[is_cash] = [f"A{x:03d}" for x in rng.integers(0, 50, int(is_cash.sum()))]

    base = pd.DataFrame({"customer_id": ids[ci], "receiver": recv,
                         "tx_type": np.array(TYPE_NAMES)[ttype], "amount": amt, "timestamp": ts})
    parts = [base]

    # LEGIT bursts (paying several bills / shops in a row) -> tx_last_10min is high for honest users
    if env.burst_p > 0:
        sel = np.flatnonzero(rng.random(m) < env.burst_p)
        extra = rng.integers(2, 4, len(sel))
        rows = np.repeat(sel, extra)
        k = len(rows)
        gap = rng.uniform(1.0, 3.5, k)
        cum = pd.Series(gap).groupby(np.repeat(np.arange(len(sel)), extra)).cumsum().values
        b_ts = ts[rows] + pd.to_timedelta(cum, "min")
        b_amt = np.maximum((avg[ci[rows]] * rng.uniform(0.4, 1.2, k)).round(0), 10.0)
        b_rec = np.array([f"M{x:03d}" for x in rng.integers(0, 300, k)], dtype=object)
        parts.append(pd.DataFrame({"customer_id": ids[ci[rows]], "receiver": b_rec,
                                   "tx_type": "merchant", "amount": b_amt, "timestamp": b_ts}))

    # LEGIT pass-through (small traders): money in, similar money out minutes later
    if env.trader_share > 0:
        trader = rng.random(n) < env.trader_share
        sel = np.flatnonzero(trader[ci] & is_send & (rng.random(m) < 0.5))
        k = len(sel)
        payer = (ci[sel] + rng.integers(1, n, k)) % n
        in_ts = ts[sel] - pd.to_timedelta(rng.uniform(3, 14, k), "min")
        parts.append(pd.DataFrame({"customer_id": ids[payer], "receiver": ids[ci[sel]],
                                   "tx_type": "send",
                                   "amount": (amt[sel] * rng.uniform(0.9, 1.3, k)).round(0),
                                   "timestamp": in_ts}))

    tx = pd.concat(parts, ignore_index=True)
    tx["is_scam"], tx["pattern"], tx["incident_id"], tx["group"] = 0, "normal", "", "legit"
    return tx


# ------------------------------------------------------------------ fraud incidents
class _Scammer:
    def __init__(self, rng, env, ids, avg, start, total_days, evasion):
        self.rng, self.env, self.ids, self.avg = rng, env, ids, avg
        self.start, self.total_days, self.evasion = start, total_days, evasion
        self.n = 0

    def acct(self):
        """An account id that is not in the customer table (mule / scammer)."""
        return f"{self.env.prefix}{self.env.n_cust + int(self.rng.integers(0, 4000)):05d}"

    def base_time(self):
        r = self.rng
        t = self.start + pd.Timedelta(days=int(r.integers(0, self.total_days)),
                                      hours=int(r.integers(0, 24)), minutes=int(r.integers(0, 60)),
                                      seconds=int(r.integers(0, 60)) if self.env.seconds else 0)
        return t

    def incident(self, name):
        """Returns list of rows (customer, receiver, tx_type, amount, ts, is_scam, pattern)."""
        r, a = self.rng, None
        v = int(r.integers(0, self.env.n_cust))
        vid, a = self.ids[v], float(self.avg[v])
        t0, rows = self.base_time(), []
        P = name

        def tx(c, rcv, amt, ts, label=1):
            rows.append((c, rcv, "send", float(round(max(amt, 10.0))), ts, label, P))

        if name == "new_recipient_big":
            mult = r.uniform(1.5, 2.6) if self.evasion else r.uniform(3, 8)
            tx(vid, self.acct(), a * mult, t0)
        elif name == "refund_scam":
            amt, src = a * r.uniform(0.8, 2.0), self.acct()
            delay = r.integers(20, 40) if self.evasion else r.integers(3, 10)
            rows.append((src, vid, "send", float(round(amt)), t0 - pd.Timedelta(minutes=int(delay)),
                         0, "refund_in"))
            tx(vid, src, amt, t0)
        elif name == "night_tx":
            hr = int(r.integers(18, 23)) if self.evasion else int(r.integers(1, 5))
            tx(vid, self.acct(), a * r.uniform(0.8, 2.5), t0.replace(hour=hr))
        elif name == "rapid_burst":
            gap = int(r.integers(5, 10)) if self.evasion else 2
            for j in range(int(r.integers(3, 5))):
                tx(vid, self.acct(), a * r.uniform(0.8, 1.6), t0 + pd.Timedelta(minutes=gap * j))
        elif name == "account_takeover_drain":
            mule, hr = self.acct(), int(r.integers(17, 23))
            t = t0.replace(hour=hr)
            for j in range(int(r.integers(2, 5))):
                tx(vid, mule, a * r.uniform(1.5, 3.5), t)
                t = t + pd.Timedelta(minutes=int(r.integers(4, 10)))
        elif name == "prize_fee_scam":
            rec = self.acct()
            t = t0.replace(hour=int(r.integers(9, 21)))
            tx(vid, rec, a * r.uniform(0.25, 0.9), t)
            if r.random() < 0.4:                                    # "one more fee to release the prize"
                tx(vid, rec, a * r.uniform(0.5, 1.5), t + pd.Timedelta(minutes=int(r.integers(60, 180))))
        elif name == "investment_drip":
            rec = self.acct()
            t = t0.replace(hour=int(r.integers(10, 20)))
            for _ in range(int(r.integers(3, 6))):
                tx(vid, rec, a * r.uniform(0.8, 1.8), t)
                t = t + pd.Timedelta(hours=float(r.uniform(8, 30)))
        elif name == "mule_pass_through":
            inbound = a * r.uniform(3, 6)
            rows.append((self.acct(), vid, "send", float(round(inbound)), t0, 0, "mule_in"))
            t = t0 + pd.Timedelta(minutes=int(r.integers(18, 41)))
            for _ in range(int(r.integers(2, 4))):
                tx(vid, self.acct(), inbound * r.uniform(0.3, 0.5), t)
                t = t + pd.Timedelta(minutes=int(r.integers(3, 11)))
        elif name == "emergency_impersonation":
            rec = self.acct()
            t = t0.replace(hour=int(r.integers(11, 23)))
            tx(vid, rec, a * r.uniform(1.5, 4.0), t)
            if r.random() < 0.5:
                tx(vid, rec, a * r.uniform(0.5, 1.5), t + pd.Timedelta(minutes=int(r.integers(5, 26))))
        else:
            raise ValueError(f"unknown typology {name}")
        self.n += 1
        return rows


def _scams(rng, env, cust, ids, mix, n_target_rows, evasion):
    start = pd.Timestamp(env.start)
    sc = _Scammer(rng, env, ids, cust.avg_amount.values, start, env.warmup_days + env.eval_days, evasion)
    names, probs = list(mix), np.array(list(mix.values()), dtype=float)
    probs = probs / probs.sum()
    out, rows_n, iid = [], 0, 0
    while rows_n < n_target_rows:
        name = names[int(rng.choice(len(names), p=probs))]
        rows = sc.incident(name)
        iid += 1
        grp = "known" if name in KNOWN else "novel"
        for r_ in rows:
            out.append(r_ + (f"I{iid:06d}" if r_[5] == 1 else "", grp if r_[5] == 1 else "legit"))
        rows_n += sum(1 for r_ in rows if r_[5] == 1)
    cols = ["customer_id", "receiver", "tx_type", "amount", "timestamp", "is_scam", "pattern",
            "incident_id", "group"]
    return pd.DataFrame(out, columns=cols)


# ------------------------------------------------------------------ public API
def generate(env: Env = SHIFTED, mix: dict = None, scam_rate: float = 0.012, seed: int = 20260,
             evasion: bool = False):
    """Returns (customers_df, transactions_df).

    scam_rate : target share of scam ROWS relative to legitimate rows (training world: ~0.03).
    mix       : incident shares per typology (defaults to 20% known / 80% novel).
    evasion   : known typologies with adapted tactics (amounts <2.6x, evening not night,
                slower bursts, delayed refunds). Isolates a pure tactic change.
    """
    mix = MIXED_MIX if mix is None else mix
    rng = np.random.default_rng(seed)
    cust, ids = _make_customers(rng, env)
    legit = _legit(rng, env, cust, ids)
    scam = _scams(rng, env, cust, ids, mix, int(scam_rate * len(legit)), evasion)
    tx = pd.concat([legit, scam], ignore_index=True)
    # inbound legs of refund/mule incidents are legit rows that belong to an incident's context
    tx = tx.sort_values("timestamp", kind="stable").reset_index(drop=True)
    tx["tx_id"] = [f"V{i:07d}" for i in range(len(tx))]
    cut = pd.Timestamp(env.start) + pd.Timedelta(days=env.warmup_days)
    tx["split"] = np.where(tx.timestamp >= cut, "eval", "warmup")
    tx = tx[["tx_id", "customer_id", "receiver", "tx_type", "amount", "timestamp", "is_scam",
             "pattern", "incident_id", "group", "split"]]
    return cust, tx


SCENARIOS = {
    # name: (description, kwargs for generate())
    "control_train_like": ("Control: training-like world and the 4 known typologies, fresh seed/customers. "
                           "Should match the Step 2 test numbers; if not, the harness is wrong.",
                           dict(env=TRAIN_LIKE, mix=KNOWN_MIX, scam_rate=0.03)),
    "environment_only": ("Legit behaviour changes (amounts, hours, volume, contacts, legit bursts and "
                         "pass-through); scam tactics unchanged (4 known typologies).",
                         dict(env=SHIFTED, mix=KNOWN_MIX, scam_rate=0.03)),
    "novel_typologies_only": ("Training-like legit world, but ONLY the 5 new scam typologies.",
                              dict(env=TRAIN_LIKE, mix=NOVEL_MIX, scam_rate=0.03)),
    "tactic_evasion": ("Training-like legit world; the 4 known typologies with adapted tactics "
                       "(smaller amounts, evening not night, slower bursts, delayed refunds).",
                       dict(env=TRAIN_LIKE, mix=KNOWN_MIX, scam_rate=0.03, evasion=True)),
    "volume_mix_shift": ("Legit volume up (heavier users, more merchant/bill traffic, more honest "
                         "bursts); scam count unchanged so prevalence halves.",
                         dict(env=VOLUME_MIX, mix=KNOWN_MIX, scam_rate=0.015)),
    "scam_surge": ("Campaign surge: same world as control but 3x the scam volume (prevalence up).",
                   dict(env=TRAIN_LIKE, mix=KNOWN_MIX, scam_rate=0.09)),
    "external_validation": ("MAIN external set: shifted legit world + 20% known / 80% novel typologies, "
                            "lower prevalence (1.2%).",
                            dict(env=SHIFTED, mix=MIXED_MIX, scam_rate=0.012)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20260)
    ap.add_argument("--scenario", default="external_validation", choices=list(SCENARIOS))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    desc, kw = SCENARIOS[args.scenario]
    cust, tx = generate(seed=args.seed, **kw)
    cust.to_csv(OUT / f"{args.scenario}_customers.csv", index=False)
    tx.to_csv(OUT / f"{args.scenario}_transactions.csv", index=False)
    ev = tx[tx.split == "eval"]
    print(f"{args.scenario}: {desc}")
    print(f"customers {len(cust):,} | rows {len(tx):,} (eval {len(ev):,}) | scam rows in eval "
          f"{int(ev.is_scam.sum()):,} ({ev.is_scam.mean() * 100:.2f}%)")
    print(ev[ev.is_scam == 1].pattern.value_counts().to_string())
    print(f"written to {OUT}")


if __name__ == "__main__":
    main()
