"""Simple, transparent rules baseline (NO machine learning).

This is a *detector* a fraud analyst could write by hand. It is different from
src/rules.py, which is the policy/message layer (thresholds -> LOW/MEDIUM/HIGH, Bangla text).

Fairness of comparison: the rules use ONLY the same 7 engineered features the ML model
sees (amount, amount_ratio, hour, is_night, is_new_recipient, tx_last_10min,
just_received_money). No extra information is given to either side.

Parameters are round numbers fixed BEFORE looking at the test split
(design used the training split only). They are NOT tuned on the test set.
"""
import pandas as pd

AMOUNT_RATIO_MIN = 3     # amount at least 3x the customer's usual
NIGHT_HOURS = (0, 5)     # 12am-5am
BURST_MIN = 3            # >=3 transactions within 10 minutes (incl. this one)
# "pass-through": money received in the last 15 min (feature definition) and now being sent out

RULE_DESCRIPTIONS = {
    "R1_big_to_new": "New recipient AND amount >= 3x customer's usual",
    "R2_night_to_new": "New recipient AND time between 00:00-05:59",
    "R3_rapid_repeat": ">= 3 transactions in 10 minutes",
    "R4_pass_through": "Money was received <= 15 min ago and is being sent out now",
}


def apply_rules(df: pd.DataFrame) -> pd.DataFrame:
    """Returns a boolean DataFrame, one column per rule."""
    r = pd.DataFrame(index=df.index)
    r["R1_big_to_new"] = (df.is_new_recipient == 1) & (df.amount_ratio >= AMOUNT_RATIO_MIN)
    r["R2_night_to_new"] = (df.is_new_recipient == 1) & df.hour.between(*NIGHT_HOURS)
    r["R3_rapid_repeat"] = df.tx_last_10min >= BURST_MIN
    r["R4_pass_through"] = df.just_received_money == 1
    return r


BASIC = ["R1_big_to_new", "R2_night_to_new", "R3_rapid_repeat"]            # the 3 classic signals
EXTENDED = BASIC + ["R4_pass_through"]                                      # + one AML-style rule


def rule_flag(df, which=EXTENDED):
    return apply_rules(df)[which].any(axis=1)


def rule_score(df, which=EXTENDED):
    """Number of rules fired (0..k). Only used to draw a PR curve / PR-AUC for a rules system."""
    return apply_rules(df)[which].sum(axis=1)
