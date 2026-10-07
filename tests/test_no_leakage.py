"""The validation generator must stay separate from training."""
import re

import pandas as pd
from conftest import ROOT

import generate_validation_data as gv


def test_training_code_never_touches_validation_data():
    src = (ROOT / "src" / "train_model.py").read_text(encoding="utf-8")
    assert "validation" not in src.lower()
    assert "generate_validation_data" not in src
    assert re.search(r'DATA\s*/\s*"transactions\.csv"', src)


def test_ids_and_populations_are_disjoint_from_training():
    env = gv.Env(n_cust=300, warmup_days=10, eval_days=5)
    cust, tx = gv.generate(env=env, mix=gv.MIXED_MIX, scam_rate=0.02, seed=1)
    train_c = pd.read_csv(ROOT / "data" / "customers.csv")
    train_t = pd.read_csv(ROOT / "data" / "transactions.csv", usecols=["tx_id"])
    assert set(cust.customer_id).isdisjoint(train_c.customer_id)
    assert set(tx.tx_id).isdisjoint(train_t.tx_id)
    assert tx.tx_id.str.startswith("V").all() and cust.customer_id.str.startswith("X").all()


def test_validation_has_typologies_unseen_in_training():
    train = pd.read_csv(ROOT / "data" / "transactions.csv", usecols=["pattern"]).pattern.unique()
    assert set(gv.NOVEL).isdisjoint(train)
    assert set(gv.KNOWN) <= set(train)


def test_validation_output_dir_is_not_training_dir():
    assert gv.OUT != ROOT / "data" and gv.OUT.parent == ROOT / "data"
