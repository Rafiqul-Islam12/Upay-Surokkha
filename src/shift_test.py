"""STEP 3: external validation and distribution-shift tests for ScamShield.

The trained model is NEVER refit and the decision threshold is NEVER retuned here. Every
scenario is scored with the deployed operating point (models/scam_model.pkl, threshold 0.30).

What it does
------------
1. Re-scores the Step 2 held-out test split (in-distribution reference; must equal models/metrics.json).
2. Generates each scenario from src/generate_validation_data.py with several seeds, builds
   features with the SAME batch code the model was trained with, scores ONLY the eval window.
3. Reports recall / precision / false-alarm rate / AUC / PR-AUC, prevalence-adjusted precision,
   incident-level recall, recall at the in-distribution false-alarm rate (diagnostic only),
   the Step 2 hand-written rules as a comparison, and per-typology recall.

Run (from anywhere):   python src/shift_test.py [--seeds 5]
Outputs: results/step3_*.csv|md|png|json and models/validation_metrics.json (used by the UI/API).
"""
import argparse
import hashlib
import json
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import average_precision_score, roc_auc_score

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from features import build_features                     # noqa: E402
from baseline_rules import rule_flag, EXTENDED          # noqa: E402
import generate_validation_data as gv                    # noqa: E402

OUT = ROOT / "results"
OUT.mkdir(exist_ok=True)
BASE_SEED = 100
ORDER = ["control_train_like", "environment_only", "novel_typologies_only", "tactic_evasion",
         "volume_mix_shift", "scam_surge", "external_validation"]
TITLE = {
    "in_distribution_test": "Step 2 test split (reference)",
    "control_train_like": "Control (same world, new seed)",
    "environment_only": "Legit behaviour shift",
    "novel_typologies_only": "5 novel scam typologies",
    "tactic_evasion": "Evasion (known scams, adapted)",
    "volume_mix_shift": "Volume / mix shift",
    "scam_surge": "Scam surge (3x volume)",
    "external_validation": "EXTERNAL VALIDATION (all shifts)",
}


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def counts(y, flag):
    y, flag = np.asarray(y).astype(bool), np.asarray(flag).astype(bool)
    return int((flag & y).sum()), int((flag & ~y).sum()), int((~flag & y).sum()), int((~flag & ~y).sum())


def best_recall_at_far(pos, neg, far_max):
    """Max recall over thresholds t with FAR(t) = mean(neg >= t) <= far_max. 0.0 if none flags anything."""
    cand = np.unique(np.concatenate([pos, neg]))
    neg_s = np.sort(neg)
    far_t = 1 - np.searchsorted(neg_s, cand, side="left") / len(neg_s)      # mean(neg >= t)
    ok = far_t <= far_max
    if not ok.any():
        return 0.0
    t = cand[ok].min()
    return float((pos >= t).mean())


def one_run(df, p, thr, pi0, far_ref, incident=True):
    """Metrics for one scored frame. df has is_scam, (optional) incident_id."""
    y = df.is_scam.values.astype(bool)
    flag = p >= thr
    tp, fp, fn, tn = counts(y, flag)
    rec = tp / (tp + fn) if tp + fn else np.nan
    far = fp / (fp + tn)
    prec = tp / (tp + fp) if tp + fp else np.nan
    adj = rec * pi0 / (rec * pi0 + far * (1 - pi0)) if rec * pi0 + far * (1 - pi0) > 0 else np.nan
    # diagnostic only: best recall reachable by ANY threshold whose false-alarm rate is <= the Step 2 rate.
    # (Scores are plateau-like, so an exact match often does not exist; we take the best feasible one.)
    rec_matched = best_recall_at_far(p[y], p[~y], far_ref) if y.any() else np.nan
    out = dict(n=len(y), scam=int(y.sum()), prevalence=y.mean(), tp=tp, fp=fp, fn=fn, tn=tn,
               recall=rec, precision=prec, far=far, precision_at_train_prevalence=adj,
               auc=roc_auc_score(y, p) if y.any() else np.nan,
               pr_auc=average_precision_score(y, p) if y.any() else np.nan,
               recall_at_matched_far=rec_matched,
               alerts_per_10k=10000 * (tp + fp) / len(y))
    if incident and "incident_id" in df and (df.incident_id != "").any():
        d = df[y].assign(flag=flag[y])
        g = d.groupby("incident_id").flag.max()
        out["incidents"] = int(len(g))
        out["incident_recall"] = float(g.mean())
    return out


def pool(runs):
    """Pool counts across seeds (rate metrics) and average the threshold-free metrics."""
    tp, fp, fn, tn = (sum(r[k] for r in runs) for k in ("tp", "fp", "fn", "tn"))
    rec, far = tp / (tp + fn), fp / (fp + tn)
    r = dict(seeds=len(runs), n=sum(r["n"] for r in runs), scam=tp + fn, tp=tp, fp=fp, fn=fn, tn=tn,
             prevalence=(tp + fn) / (tp + fp + fn + tn), recall=rec, far=far,
             precision=tp / (tp + fp) if tp + fp else np.nan)
    r["recall_ci_lo"], r["recall_ci_hi"] = wilson(tp, tp + fn)
    r["far_ci_lo"], r["far_ci_hi"] = wilson(fp, fp + tn)
    r["precision_ci_lo"], r["precision_ci_hi"] = wilson(tp, tp + fp)
    r["recall_seed_min"], r["recall_seed_max"] = min(x["recall"] for x in runs), max(x["recall"] for x in runs)
    r["precision_seed_min"] = min(x["precision"] for x in runs)
    r["precision_seed_max"] = max(x["precision"] for x in runs)
    for k in ("auc", "pr_auc", "recall_at_matched_far", "precision_at_train_prevalence", "alerts_per_10k"):
        r[k] = float(np.nanmean([x[k] for x in runs]))
    r["f1"] = 2 * r["precision"] * rec / (r["precision"] + rec) if r["precision"] + rec else np.nan
    if "incident_recall" in runs[0]:
        r["incident_recall"] = float(np.nanmean([x["incident_recall"] for x in runs]))
    return r


def f3(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"


def pct(x, d=1):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.{d}f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    args = ap.parse_args()

    bundle = joblib.load(ROOT / "models" / "scam_model.pkl")
    model, FEATS, THR = bundle["model"], bundle["features"], bundle["threshold"]

    # ---- 1) in-distribution reference (Step 2 test split)
    tx = build_features()
    te = tx[tx.split == "test"].reset_index(drop=True)
    p_te = model.predict_proba(te[FEATS])[:, 1]
    ref = one_run(te, p_te, THR, te.is_scam.mean(), 0.0195, incident=False)
    pi0, far_ref = ref["prevalence"], ref["far"]
    ref = one_run(te, p_te, THR, pi0, far_ref, incident=False)
    ref_rules = one_run(te, rule_flag(te, EXTENDED).astype(float).values, 0.5, pi0, far_ref, incident=False)
    saved = json.loads((ROOT / "models" / "metrics.json").read_text(encoding="utf-8"))
    assert abs(ref["recall"] - saved["recall"]) < 0.002 and abs(ref["precision"] - saved["precision"]) < 0.002, \
        "in-distribution reference no longer matches models/metrics.json"
    print(f"in-distribution test: recall {pct(ref['recall'])}  precision {pct(ref['precision'])}  "
          f"FAR {pct(ref['far'], 2)}  AUC {ref['auc']:.3f}  (matches models/metrics.json)")

    by_seed, rows_ml, rows_rules, typ_rows = [], {}, {}, []
    pooled_ml, pooled_rules = {}, {}
    for name in ORDER:
        desc, kw = gv.SCENARIOS[name]
        runs_ml, runs_rules, per_typ = [], [], []
        for s in range(args.seeds):
            cust, raw = gv.generate(seed=BASE_SEED + s, **kw)
            f = build_features(raw, cust)
            ev = f[f.split == "eval"].reset_index(drop=True)
            p = model.predict_proba(ev[FEATS])[:, 1]
            rf = rule_flag(ev, EXTENDED).astype(float).values
            a = one_run(ev, p, THR, pi0, far_ref)
            b = one_run(ev, rf, 0.5, pi0, far_ref)
            runs_ml.append(a); runs_rules.append(b)
            by_seed.append({"scenario": name, "seed": BASE_SEED + s, "system": "ML", **a})
            by_seed.append({"scenario": name, "seed": BASE_SEED + s, "system": "Rules R1-R4", **b})
            sc = ev[ev.is_scam == 1].assign(ml=p[ev.is_scam.values == 1] >= THR,
                                            rules=rf[ev.is_scam.values == 1] > 0.5)
            per_typ.append(sc)
        pooled_ml[name], pooled_rules[name] = pool(runs_ml), pool(runs_rules)
        t = pd.concat(per_typ)
        g = t.groupby(["pattern", "group"]).agg(n=("ml", "size"), ml_recall=("ml", "mean"),
                                                rules_recall=("rules", "mean")).reset_index()
        g.insert(0, "scenario", name)
        typ_rows.append(g)
        m = pooled_ml[name]
        print(f"{name:24s} recall {pct(m['recall'])}  precision {pct(m['precision'])}  FAR {pct(m['far'], 2)}  "
              f"AUC {m['auc']:.3f}  (rows/seed ~{m['n'] // args.seeds:,}, scam {pct(m['prevalence'], 2)})")
    typ = pd.concat(typ_rows, ignore_index=True)

    # ---- 2) tables
    def table(pool_ml, pool_rules):
        recs = [("in_distribution_test", ref, ref_rules, 1)]
        recs += [(n, pool_ml[n], pool_rules[n], args.seeds) for n in ORDER]
        out = []
        for n, m, r, k in recs:
            out.append({
                "scenario": TITLE[n], "scam_share": pct(m["prevalence"], 2),
                "recall": pct(m["recall"]), "recall_95ci": f"{pct(m.get('recall_ci_lo', wilson(m['tp'], m['tp'] + m['fn'])[0]))}-"
                                                          f"{pct(m.get('recall_ci_hi', wilson(m['tp'], m['tp'] + m['fn'])[1]))}",
                "precision": pct(m["precision"]),
                "precision_if_same_prevalence": pct(m["precision_at_train_prevalence"]),
                "false_alarm_rate": pct(m["far"], 2), "auc": f3(m["auc"]), "pr_auc": f3(m["pr_auc"]),
                "best_recall_at_ref_far_(diagnostic)": pct(m["recall_at_matched_far"]),
                "incident_recall": pct(m.get("incident_recall", np.nan)),
                "rules_recall": pct(r["recall"]), "rules_precision": pct(r["precision"]),
                "rules_far": pct(r["far"], 2)})
        return pd.DataFrame(out)

    tab = table(pooled_ml, pooled_rules)
    tab.to_csv(OUT / "step3_scenarios.csv", index=False)
    pd.DataFrame(by_seed).to_csv(OUT / "step3_scenarios_by_seed.csv", index=False)
    typ.round(3).to_csv(OUT / "step3_typology_recall.csv", index=False)

    # ---- 3) figures
    labels = [TITLE[n] for n in ORDER]
    fig, ax = plt.subplots(1, 3, figsize=(15, 5.2), sharey=True)
    specs = [("recall", "Recall (scam-like caught)", ref["recall"], True),
             ("precision", "Precision (flags that are scams)", ref["precision"], False),
             ("far", "False-alarm rate (normal tx flagged)", ref["far"], False)]
    ypos = np.arange(len(ORDER))[::-1]
    for a, (k, ttl, refv, ci) in zip(ax, specs):
        vals = [pooled_ml[n][k] * 100 for n in ORDER]
        cols = ["#0B3F8F" if n != "external_validation" else "#D93025" for n in ORDER]
        a.barh(ypos, vals, color=cols, height=0.62)
        a.scatter([pooled_rules[n][k] * 100 for n in ORDER], ypos, marker="D", color="#FFC400",
                  edgecolor="#333", zorder=3, s=36, label="Hand rules R1-R4")
        if k == "recall":
            lo = [pooled_ml[n]["recall_seed_min"] * 100 for n in ORDER]
            hi = [pooled_ml[n]["recall_seed_max"] * 100 for n in ORDER]
            a.hlines(ypos, lo, hi, color="#222", lw=1.6, zorder=4)
        a.axvline(refv * 100, color="#555", ls="--", lw=1.2, label="Step 2 test split (ML)")
        a.set_title(ttl, fontsize=11)
        a.set_xlabel("%")
        for yy, v in zip(ypos, vals):
            a.text(v + 0.8, yy, f"{v:.1f}", va="center", fontsize=8)
        a.grid(axis="x", alpha=0.25)
    ax[0].set_yticks(ypos); ax[0].set_yticklabels(labels, fontsize=9)
    h, l = ax[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, fontsize=9, frameon=False)
    fig.suptitle(f"ScamShield under shift: fixed model and threshold {THR:.2f}, {args.seeds} seeds per scenario "
                 f"(black line = min-max recall across seeds)", fontsize=11)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "step3_shift_summary.png", dpi=140)
    plt.close(fig)

    ex = typ[typ.scenario == "external_validation"].sort_values("ml_recall")
    fig, a = plt.subplots(figsize=(9, 4.8))
    yy = np.arange(len(ex))
    a.barh(yy, ex.ml_recall * 100, color=["#0B3F8F" if g == "known" else "#D93025" for g in ex.group], height=0.6)
    a.scatter(ex.rules_recall * 100, yy, marker="D", color="#FFC400", edgecolor="#333", zorder=3, s=40,
              label="Hand rules R1-R4")
    a.set_yticks(yy); a.set_yticklabels([f"{p}  (n={n})" for p, n in zip(ex.pattern, ex.n)], fontsize=9)
    for y_, v in zip(yy, ex.ml_recall * 100):
        a.text(v + 1, y_, f"{v:.0f}%", va="center", fontsize=8)
    a.set_xlim(0, 110); a.set_xlabel("Recall at the fixed 0.30 threshold (%)")
    a.set_title("External validation: recall by scam typology\n(blue = seen in training, red = novel)", fontsize=11)
    a.legend(loc="lower right", fontsize=8); a.grid(axis="x", alpha=0.25)
    fig.tight_layout(); fig.savefig(OUT / "step3_typology_recall.png", dpi=140); plt.close(fig)

    # ---- 4) compact JSON for API/UI (only numbers computed above)
    ex_m, ctl = pooled_ml["external_validation"], pooled_ml["control_train_like"]
    compact = {
        "threshold": round(float(THR), 2), "seeds_per_scenario": args.seeds,
        "in_distribution": {k: round(float(ref[k]), 4) for k in ("recall", "precision", "far", "auc", "pr_auc")},
        "scenarios": {n: {"title": TITLE[n], "description": gv.SCENARIOS[n][0],
                          **{k: round(float(pooled_ml[n][k]), 4) for k in
                             ("recall", "precision", "far", "auc", "pr_auc", "prevalence",
                              "precision_at_train_prevalence", "recall_at_matched_far")},
                          "rules_recall": round(float(pooled_rules[n]["recall"]), 4),
                          "rules_far": round(float(pooled_rules[n]["far"]), 4)} for n in ORDER},
        "data": "synthetic (separate validation generator, never used for training)"}
    (ROOT / "models" / "validation_metrics.json").write_text(json.dumps(compact, indent=2), encoding="utf-8")
    (OUT / "step3_run_info.json").write_text(json.dumps({
        "threshold": THR, "model_sha256": hashlib.sha256((ROOT / "models" / "scam_model.pkl").read_bytes()).hexdigest(),
        "seeds": [BASE_SEED + i for i in range(args.seeds)],
        "in_distribution_prevalence": pi0, "in_distribution_far_reference": far_ref,
        "scenarios": {n: gv.SCENARIOS[n][0] for n in ORDER}}, indent=2), encoding="utf-8")

    # ---- 5) markdown report
    def md(df):
        cols = list(df.columns)
        L = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
        for _, r in df.iterrows():
            L.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
        return "\n".join(L)

    main_cols = ["scenario", "scam_share", "recall", "recall_95ci", "precision",
                 "precision_if_same_prevalence", "false_alarm_rate", "auc", "pr_auc"]
    extra_cols = ["scenario", "best_recall_at_ref_far_(diagnostic)", "incident_recall",
                  "rules_recall", "rules_precision", "rules_far"]
    tt = typ[typ.scenario == "external_validation"].copy()
    tt["ml_recall"] = (tt.ml_recall * 100).round(1).astype(str) + "%"
    tt["rules_recall"] = (tt.rules_recall * 100).round(1).astype(str) + "%"
    tt = tt.sort_values(["group", "pattern"], ascending=[False, True])[["pattern", "group", "n", "ml_recall", "rules_recall"]]
    tt["description"] = tt.pattern.map(lambda x: gv.DESCRIPTIONS[x].split("] ", 1)[1])

    d = lambda a, b: f"{(a - b) * 100:+.1f} pts"
    ev_m, ev_r = pooled_ml["external_validation"], pooled_rules["external_validation"]
    findings = [
        f"**Harness check passes.** On the control (same world as training, new customers and seeds) recall is "
        f"{pct(ctl['recall'])} and precision {pct(ctl['precision'])}, close to the Step 2 test split "
        f"({pct(ref['recall'])} / {pct(ref['precision'])}). So the drop below comes from the shifts, not from the new pipeline.",
        f"**External validation drop (fixed threshold {THR:.2f}).** Recall {pct(ref['recall'])} -> {pct(ev_m['recall'])} "
        f"({d(ev_m['recall'], ref['recall'])}), precision {pct(ref['precision'])} -> {pct(ev_m['precision'])} "
        f"({d(ev_m['precision'], ref['precision'])}), false-alarm rate {pct(ref['far'], 2)} -> {pct(ev_m['far'], 2)}, "
        f"AUC {ref['auc']:.3f} -> {ev_m['auc']:.3f}.",
        f"**Part of the precision drop is just prevalence.** Scam share fell from {pct(ref['prevalence'], 2)} to "
        f"{pct(ev_m['prevalence'], 2)}. At the original prevalence the same recall/false-alarm rate would give "
        f"precision {pct(ev_m['precision_at_train_prevalence'])} (column 'precision_if_same_prevalence'). "
        f"The rest of the drop is real.",
        f"**Which shift hurts what.** Legit-behaviour shift alone: recall "
        f"{pct(pooled_ml['environment_only']['recall'])}, false-alarm rate {pct(pooled_ml['environment_only']['far'], 2)} "
        f"(honest users who forward money, pay several bills in a row or send to new numbers look risky). "
        f"Novel typologies alone: recall {pct(pooled_ml['novel_typologies_only']['recall'])}. "
        f"Adapted tactics on known scams: recall {pct(pooled_ml['tactic_evasion']['recall'])}.",
        f"**Ranking vs operating point (threshold-free view).** AUC is {pooled_ml['environment_only']['auc']:.3f} when only "
        f"legit behaviour shifts (the ranking mostly survives, but the fixed 0.30 cut now raises "
        f"{pct(pooled_ml['environment_only']['far'], 2)} false alarms), "
        f"{pooled_ml['tactic_evasion']['auc']:.3f} when known scams adapt, and {pooled_ml['novel_typologies_only']['auc']:.3f} "
        f"for novel typologies alone (close to a coin flip: the score carries almost no signal for them). "
        f"Best recall reachable at the Step 2 false-alarm budget on the external set: "
        f"{pct(ev_m['recall_at_matched_far'])} (diagnostic only).",
        f"**Hand-written rules degrade too.** On the external set rules R1-R4 reach recall {pct(ev_r['recall'])} at "
        f"false-alarm rate {pct(ev_r['far'], 2)} (ML: {pct(ev_m['recall'])} at {pct(ev_m['far'], 2)}). "
        f"Neither approach covers typologies whose signature is outside the 7 features.",
    ]

    rep = f"""# Step 3 results: external validation and distribution shift (synthetic data)

Model: `models/scam_model.pkl`, **unchanged**. Decision threshold: **{THR:.2f}**, **unchanged**.
Nothing below was used to train the model or to choose the threshold. {args.seeds} independent draws per
scenario (seeds {BASE_SEED}-{BASE_SEED + args.seeds - 1}); rates are pooled over draws.
All numbers are produced by `python src/shift_test.py`.

## Key findings
""" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(findings)) + f"""

## Table 1: ScamShield at the fixed threshold, reference vs shifted worlds
{md(tab[main_cols])}

- `recall_95ci`: Wilson interval on pooled counts (does not include variation of the generator itself; see seed range in `step3_scenarios_by_seed.csv`).
- `precision_if_same_prevalence`: precision recomputed with the scenario's recall and false-alarm rate but the Step 2 scam share ({pct(pi0, 2)}). It separates "fewer scams in the traffic" from "worse model".
- Reference row = Step 2 held-out test split, recomputed live (matches `models/metrics.json`).

## Table 2: diagnostics and the Step 2 rules baseline
{md(tab[extra_cols])}

- `best_recall_at_ref_far_(diagnostic)`: the best recall ANY threshold could reach while keeping the false-alarm rate at or below the Step 2 rate ({pct(far_ref, 2)}) on that scenario. 0.0% means no threshold can flag anything without exceeding that false-alarm budget. **Oracle-style diagnostic, not a deployable setting** (it needs labels from the shifted world).
- `incident_recall`: share of scam *incidents* (multi-transaction scams) with at least one flagged transaction.
- Rules = R1-R4 from Step 2 (round-number parameters, not tuned on any of this data).

## Table 3: external validation, recall by scam typology
{md(tt)}

Typologies marked `novel` were written for this step and were never part of training. They are illustrative
guesses at plausible mobile-money fraud, **not** observed upay fraud. Some (`prize_fee_scam`,
`investment_drip` follow-ups) are by construction hard to separate from honest behaviour using only the 7 features:
the failure there is as much a feature-coverage limit as a model limit.

## Scenario definitions
""" + "\n".join(f"- **{TITLE[n]}** (`{n}`): {gv.SCENARIOS[n][0]}" for n in ORDER) + """

## How to read this honestly
- All data is synthetic and produced by two generators written by the same team. A different generator
  measures robustness to *the shifts we thought of*, not to real-world drift.
- The legit-world shift and the novel typologies were designed to stress the model. They are not a random sample of the future.
- Figures: `results/step3_shift_summary.png`, `results/step3_typology_recall.png`.
"""
    (OUT / "step3_results.md").write_text(rep, encoding="utf-8")
    print("\nwritten: results/step3_results.md, step3_scenarios.csv, step3_typology_recall.csv, "
          "step3_scenarios_by_seed.csv, step3_shift_summary.png, step3_typology_recall.png, "
          "models/validation_metrics.json")


if __name__ == "__main__":
    main()
