"""STEP 2: rules baseline vs ML vs risk tiers vs hybrid, on the SAME held-out test split.

Run from anywhere:   python src/evaluate_baselines.py [--fp-cost 20]
Outputs (all numbers come from this script):
  results/step2_results.md           human-readable tables (paste into pitch)
  results/step2_main_results.csv     main comparison
  results/step2_cost_table.csv       cost-sensitive table (3 thresholds)
  results/step2_cost_sensitivity.csv cost table repeated for several false-alarm costs
  results/step2_per_pattern_recall.csv
  results/step2_pr_curve.png
  results/step2_run_info.json
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_curve

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from features import build_features, FEATURES            # noqa: E402
from baseline_rules import apply_rules, BASIC, EXTENDED, RULE_DESCRIPTIONS  # noqa: E402
from rules import LOW, HIGH                               # noqa: E402  (existing policy tiers)

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)


def counts(y, flag):
    y = np.asarray(y).astype(bool)
    flag = np.asarray(flag).astype(bool)
    tp = int((flag & y).sum()); fp = int((flag & ~y).sum())
    fn = int((~flag & y).sum()); tn = int((~flag & ~y).sum())
    return tp, fp, fn, tn


def row(name, y, flag, score=None, note=""):
    tp, fp, fn, tn = counts(y, flag)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {
        "setup": name,
        "precision": round(prec, 3), "recall": round(rec, 3), "f1": round(f1, 3),
        "pr_auc": round(float(average_precision_score(y, score)), 3) if score is not None else np.nan,
        "false_alarm_rate_%": round(100 * fp / (fp + tn), 2),      # FP / legit (project's definition)
        "flags_that_are_false_%": round(100 * fp / (tp + fp), 1) if tp + fp else np.nan,  # = 1 - precision
        "legit_tx_warned": fp,
        "alerts_per_10k_tx": round(10000 * (tp + fp) / len(y), 1),
        "TP": tp, "FP": fp, "FN": fn, "TN": tn, "note": note,
    }


def md_table(df, floatfmt=None):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float) and np.isnan(v):
                v = "n/a"
            cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def cost_table(y, amount, flags: dict, fp_cost, recovery):
    """Total cost = (non-recovered amount of missed scams) + fp_cost * false alarms.
    A flagged scam is counted as fully prevented (optimistic; see limitations)."""
    y = np.asarray(y).astype(bool)
    total_scam = float(amount[y].sum())
    rows = [{"policy": "No system (all scams missed)", "missed_scam_loss": round(total_scam * (1 - recovery)),
             "false_alarm_cost": 0, "total_cost": round(total_scam * (1 - recovery)),
             "saving_vs_no_system": 0, "scam_value_caught_%": 0.0, "FN": int(y.sum()), "FP": 0}]
    base = total_scam * (1 - recovery)
    for name, flag in flags.items():
        flag = np.asarray(flag).astype(bool)
        fn_mask = ~flag & y
        fp = int((flag & ~y).sum())
        missed = float(amount[fn_mask].sum()) * (1 - recovery)
        fa = fp * fp_cost
        rows.append({"policy": name, "missed_scam_loss": round(missed), "false_alarm_cost": round(fa),
                     "total_cost": round(missed + fa), "saving_vs_no_system": round(base - missed - fa),
                     "scam_value_caught_%": round(100 * (1 - float(amount[fn_mask].sum()) / total_scam), 1),
                     "FN": int(fn_mask.sum()), "FP": fp})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fp-cost", type=float, default=None, help="override false_alarm_cost_bdt")
    args = ap.parse_args()
    cfg = json.loads((ROOT / "config" / "eval_costs.json").read_text(encoding="utf-8"))
    fp_cost = args.fp_cost if args.fp_cost is not None else cfg["false_alarm_cost_bdt"]
    recovery = cfg["recovery_rate_if_missed"]
    TH = cfg["thresholds"]

    tx = build_features()
    bundle = joblib.load(ROOT / "models" / "scam_model.pkl")
    model, T = bundle["model"], bundle["threshold"]
    test = tx[tx.split == "test"].copy().reset_index(drop=True)
    y = test.is_scam.values
    amount = test.amount.values
    p = model.predict_proba(test[FEATURES])[:, 1]

    R = apply_rules(test)
    basic_flag = R[BASIC].any(axis=1).values
    ext_flag = R[EXTENDED].any(axis=1).values
    basic_score = R[BASIC].sum(axis=1).values
    ext_score = R[EXTENDED].sum(axis=1).values

    ml_flag = p >= T
    any_warn = p >= LOW
    high = p >= HIGH
    medium_only = (p >= LOW) & (p < HIGH)
    hybrid = ml_flag | ext_flag

    # --- matched operating points (read from the TEST curve; NOT deployable thresholds) ---
    fpr, tpr, _ = roc_curve(y, p)
    ext_c = counts(y, ext_flag)
    ext_far = ext_c[1] / (ext_c[1] + ext_c[3]); ext_rec = ext_c[0] / (ext_c[0] + ext_c[2])
    ml_rec_at_far = float(tpr[fpr <= ext_far].max())
    ml_far_at_rec = float(fpr[tpr >= ext_rec].min())

    main_rows = [
        row("1a. Rules only (basic: R1-R3)", y, basic_flag, basic_score, "3 classic rules; score = #rules fired"),
        row("1b. Rules only (extended: R1-R4)", y, ext_flag, ext_score, "adds pass-through rule; score = #rules fired"),
        row(f"2. ML only (LightGBM, threshold {T:.2f})", y, ml_flag, p, "current operating point"),
        row(f"3a. ML + tiers: any warning (score >= {LOW})", y, any_warn, p, "MEDIUM + HIGH -> customer sees a warning"),
        row(f"3b. ML + tiers: HIGH only (score >= {HIGH})", y, high, p, "-> analyst queue; identical to row 2 by construction"),
        row(f"3c. ML + tiers: MEDIUM only ({LOW} to <{HIGH})", y, medium_only, p, "extra alerts the MEDIUM tier adds"),
        row("4. Integrated: ML + agent-liquidity signal", y, np.zeros(len(y), bool), None,
            "NOT APPLICABLE in this data - see note A"),
        row("5. (extra) Hybrid: ML OR rules R1-R4", y, hybrid, None, "my addition; replaces the N/A integrated row"),
    ]
    main_df = pd.DataFrame(main_rows)
    # row 4 is not computed: blank it out so nobody pastes fake zeros
    i4 = main_df.index[main_df.setup.str.startswith("4.")][0]
    for c in main_df.columns:
        if c not in ("setup", "note"):
            main_df.loc[i4, c] = np.nan

    # --- matched-point rows (extra, honest apples-to-apples) ---
    matched = pd.DataFrame([
        {"comparison": "ML recall at the SAME false-alarm rate as Rules R1-R4",
         "rules_value": f"FAR {ext_far*100:.2f}%, recall {ext_rec:.3f}", "ML_value": f"recall {ml_rec_at_far:.3f}"},
        {"comparison": "ML false-alarm rate at the SAME recall as Rules R1-R4",
         "rules_value": f"recall {ext_rec:.3f}, FAR {ext_far*100:.2f}%", "ML_value": f"FAR {ml_far_at_rec*100:.2f}%"},
    ])

    # --- note A evidence: does any scam touch an agent / cash-out? ---
    scam_test = test[test.is_scam == 1]
    all_scam = tx[tx.is_scam == 1]
    evidence = {
        "scam_tx_total": int(len(all_scam)),
        "scam_tx_that_are_cashout": int((all_scam.tx_type == "cashout").sum()),
        "scam_tx_with_agent_receiver": int(all_scam.receiver.str.startswith("A").sum()),
        "scam_tx_types": all_scam.tx_type.value_counts().to_dict(),
    }

    # --- per-pattern recall ---
    pats = []
    for name, flag in [("Rules R1-R3", basic_flag), ("Rules R1-R4", ext_flag),
                       (f"ML @{T:.2f}", ml_flag), (f"ML @{LOW} (warn)", any_warn), ("Hybrid ML OR R1-R4", hybrid)]:
        s = pd.Series(flag, index=test.index)[test.is_scam == 1]
        pats.append(s.groupby(scam_test.pattern.values).mean().round(3).rename(name))
    pat_df = pd.concat(pats, axis=1)
    pat_df.insert(0, "n_scam_tx", scam_test.pattern.value_counts())
    pat_df = pat_df.reset_index().rename(columns={"index": "pattern"})

    # --- cost tables ---
    flags = {
        f"ML strict (>= {TH['strict']})": p >= TH["strict"],
        f"ML balanced (>= {TH['balanced']})": p >= TH["balanced"],
        f"ML lenient (>= {TH['lenient']})": p >= TH["lenient"],
        "Rules R1-R3": basic_flag, "Rules R1-R4": ext_flag, "Hybrid ML(0.30) OR R1-R4": hybrid,
    }
    cost_df = cost_table(y, amount, flags, fp_cost, recovery)
    sens = []
    for c in cfg["fp_cost_sensitivity_bdt"]:
        t = cost_table(y, amount, flags, c, recovery)
        best = t.loc[t.total_cost.idxmin(), "policy"]
        d = {"false_alarm_cost_bdt": c, "cheapest_policy": best}
        for _, r in t.iterrows():
            d[r.policy] = r.total_cost
        sens.append(d)
    sens_df = pd.DataFrame(sens)

    # --- PR curve plot ---
    prec_c, rec_c, _ = precision_recall_curve(y, p)
    fig, ax = plt.subplots(figsize=(7.5, 5.5), dpi=150)
    ax.plot(rec_c, prec_c, color="#0B3F8F", lw=2, label=f"ML score (PR-AUC {average_precision_score(y, p):.3f})")
    ax.axhline(y.mean(), color="grey", ls=":", lw=1, label=f"No-skill (base rate {y.mean()*100:.2f}%)")
    def pt(flag, label, color, marker):
        tp, fp, fn, tn = counts(y, flag)
        if tp + fp == 0:
            return
        ax.scatter(tp / (tp + fn), tp / (tp + fp), s=70, color=color, marker=marker, zorder=5, label=label)
    pt(p >= TH["strict"], f"ML strict ({TH['strict']})", "#2E9E5B", "o")
    pt(p >= TH["balanced"], f"ML balanced ({TH['balanced']})", "#0B3F8F", "o")
    pt(p >= TH["lenient"], f"ML lenient ({TH['lenient']})", "#9B59B6", "o")
    pt(basic_flag, "Rules R1-R3", "#E67E22", "s")
    pt(ext_flag, "Rules R1-R4", "#C0392B", "s")
    pt(hybrid, "Hybrid ML OR rules", "#16A085", "D")
    ax.set_xlabel("Recall (share of scam transactions caught)")
    ax.set_ylabel("Precision (share of flags that are real scams)")
    ax.set_title("ScamShield vs rules baseline: precision-recall (held-out test, synthetic data)")
    ax.set_xlim(0, 1.02); ax.set_ylim(0, 1.02); ax.grid(alpha=0.3); ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout(); fig.savefig(OUT / "step2_pr_curve.png"); plt.close(fig)

    # --- save ---
    main_df.to_csv(OUT / "step2_main_results.csv", index=False)
    cost_df.to_csv(OUT / "step2_cost_table.csv", index=False)
    sens_df.to_csv(OUT / "step2_cost_sensitivity.csv", index=False)
    pat_df.to_csv(OUT / "step2_per_pattern_recall.csv", index=False)
    info = {"test_transactions": int(len(test)), "test_scam_transactions": int(y.sum()),
            "test_period": [str(test.timestamp.min()), str(test.timestamp.max())],
            "ml_threshold": T, "tiers": {"low": LOW, "high": HIGH}, "false_alarm_cost_bdt": fp_cost,
            "recovery_rate_if_missed": recovery, "agent_signal_evidence": evidence,
            "data": "synthetic", "rule_descriptions": RULE_DESCRIPTIONS}
    (OUT / "step2_run_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    show_cols = ["setup", "precision", "recall", "f1", "pr_auc", "false_alarm_rate_%",
                 "flags_that_are_false_%", "alerts_per_10k_tx", "TP", "FP", "FN"]
    md = []
    md.append("# Step 2 results: rules baseline vs ML (synthetic data, held-out chronological test split)\n")
    md.append(f"Test set: {len(test):,} transactions, {int(y.sum()):,} scam-like ({y.mean()*100:.2f}%), "
              f"{test.timestamp.min():%Y-%m-%d} to {test.timestamp.max():%Y-%m-%d}. Same split for every row.\n")
    md.append("## Rules used (no ML)\n" + "\n".join(f"- **{k}**: {v}" for k, v in RULE_DESCRIPTIONS.items()) + "\n")
    md.append("Rules use only the same 7 features as the ML model. Parameters are round numbers fixed without looking at the test split.\n")
    md.append("## Table 1: main comparison\n" + md_table(main_df[show_cols]) + "\n")
    md.append("False-alarm rate = false alarms / all legitimate transactions (the project's existing definition). "
              "For single-stage setups this is also the % of legitimate transactions that get a warning. "
              "'Flags that are false' = 1 - precision. PR-AUC for rules uses the number of rules fired as the score.\n")
    md.append("## Table 2: matched operating points (read off the test curve; NOT deployable thresholds)\n" + md_table(matched) + "\n")
    md.append("## Table 3: recall by scam pattern (test)\n" + md_table(pat_df) + "\n")
    md.append(f"## Table 4: cost-sensitive comparison (false alarm = BDT {fp_cost:g}, ASSUMPTION; missed scam = its actual amount, no recovery)\n"
              + md_table(cost_df) + "\n")
    md.append("## Table 5: does the cheapest policy change if the false-alarm cost changes?\n" + md_table(sens_df) + "\n")
    md.append("## Note A: integrated ML + agent-liquidity signal\n"
              f"In this dataset {evidence['scam_tx_that_are_cashout']} of {evidence['scam_tx_total']:,} scam transactions are cash-outs and "
              f"{evidence['scam_tx_with_agent_receiver']} go to an agent (scam transaction types: {evidence['scam_tx_types']}). "
              "The agent-liquidity forecast is about agent cash-out demand, so it carries no information about these scams. "
              "No integrated gain can be measured, so row 4 is left blank instead of inventing a number.\n")
    (OUT / "step2_results.md").write_text("\n".join(md), encoding="utf-8")

    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    print("=== TABLE 1 main ===\n", main_df[show_cols].to_string(index=False))
    print("\n=== TABLE 2 matched ===\n", matched.to_string(index=False))
    print("\n=== TABLE 3 per-pattern recall ===\n", pat_df.to_string(index=False))
    print(f"\n=== TABLE 4 cost (FP cost BDT {fp_cost:g}) ===\n", cost_df.to_string(index=False))
    print("\n=== TABLE 5 sensitivity ===\n", sens_df.to_string(index=False))
    print("\n=== NOTE A evidence ===\n", evidence)


if __name__ == "__main__":
    main()
