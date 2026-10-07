"""Step 8 tests: impact model arithmetic, link to measured results, workbook formulas."""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import impact_model as im  # noqa: E402

CFG = im.load_config()


def P(scen):
    return im.scenario_inputs(CFG, scen)


def test_measured_inputs_match_step2_and_step3_results():
    m = json.load(open(ROOT / "models" / "metrics.json"))
    rows = {r["scenario"]: r for r in csv.DictReader(open(ROOT / "results" / "step3_scenarios.csv", encoding="utf-8"))}
    pct = lambda s: float(s.strip("%")) / 100
    assert P("good")["R3"] == pytest.approx(m["recall"], abs=1e-3)
    assert P("good")["F1"] == pytest.approx(m["false_alarm_rate"], abs=1e-4)
    ev = rows["Evasion (known scams, adapted)"]
    assert P("medium")["R3"] == pytest.approx(pct(ev["recall"]), abs=1e-3)
    assert P("medium")["F1"] == pytest.approx(pct(ev["false_alarm_rate"]), abs=1e-4)
    ex = rows["EXTERNAL VALIDATION (all shifts)"]
    assert P("bad")["R3"] == pytest.approx(pct(ex["recall"]), abs=1e-3)
    assert P("bad")["F1"] == pytest.approx(pct(ex["false_alarm_rate"]), abs=1e-4)


def test_every_input_is_labelled_and_has_sources():
    for a in CFG["assumptions"] + CFG["ab_pilot"]:
        assert a["kind"] in ("ASSUMPTION", "CONVENTION", "MEASURED_ON_SYNTHETIC")
        assert a["basis"]
        for sid in a["sources"]:
            assert sid in CFG["sources"]
        if a["id"] != "H1":
            assert a["sources"], a["id"]
    for a in CFG["assumptions"]:
        assert a["bad"] is not None and a["medium"] is not None and a["good"] is not None


def test_scenarios_are_ordered():
    net = {s: im.compute(P(s))["net_benefit"] for s in im.SCEN}
    assert net["bad"] < net["medium"] < net["good"]


def test_literal_formula_and_net_identity():
    for s in im.SCEN:
        p, r = P(s), im.compute(P(s))
        assert r["literal_prevented"] == pytest.approx(p["V1"] * p["R1"] * p["R2"] * p["R3"])
        assert r["prevented_loss"] == pytest.approx(r["literal_prevented"] * p["R4"])
        assert r["net_benefit"] == pytest.approx(
            r["prevented_loss"] - r["false_alarm_cost"] - r["analyst_cost"] - r["friction_cost"] - r["run_cost"])


def test_payback_and_roi():
    g = im.compute(P("good"))
    assert g["payback_months"] == pytest.approx(g["one_time"] / g["net_benefit"])
    assert g["roi"] == pytest.approx((g["net_benefit"] * P("good")["H1"] - g["one_time"]) / g["one_time"])
    b = im.compute(P("bad"))
    assert b["net_benefit"] < 0 and b["payback_months"] is None


@pytest.mark.parametrize("scen", ["medium", "good"])
def test_break_even_points_give_zero_net(scen):
    p, r = P(scen), im.compute(P(scen))
    assert im.net_closed_form(p, far=r["breakeven_far"]) == pytest.approx(0, abs=1e-3)
    assert im.net_closed_form(p, scam_rate=r["breakeven_scam_rate"]) == pytest.approx(0, abs=1e-3)


def test_sample_size_formula():
    n_arm, total = im.sample_size(sigma=19, mde=2, alpha=0.05, power=0.8, rho=0.5, attrition=0.1)
    z = 1.959964 + 0.841621
    assert abs(n_arm - 2 * z * z * 19 * 19 * 0.75 / 4) < 1      # ceil of the closed form
    assert total >= 2 * n_arm / 0.9 - 1


def test_csv_export_and_markdown(tmp_path):
    im.main(["--out-dir", str(tmp_path), "--no-xlsx"])
    for f in ("step8_assumptions.csv", "step8_scenario_results.csv", "step8_sensitivity_tornado.csv",
              "step8_sensitivity_grid.csv", "step8_agent_copilot_kpis.csv", "step8_cost_advisor_ab_design.csv",
              "step8_sources.csv", "step8_results.md"):
        assert (tmp_path / f).stat().st_size > 0, f
    rows = list(csv.DictReader(open(tmp_path / "step8_assumptions.csv", encoding="utf-8")))
    assert all(r["status"] for r in rows)


def test_workbook_uses_formulas_and_matches_python(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    im.main(["--out-dir", str(tmp_path)])
    xl = tmp_path / "step8_impact_model.xlsx"
    wb = openpyxl.load_workbook(xl)
    ws = wb["ScamShield_Model"]
    labels = {ws.cell(r, 1).value: r for r in range(5, ws.max_row + 1)}
    for lab in ("Prevented loss", "NET MONTHLY BENEFIT", "PAYBACK", "False alarms per month"):
        assert str(ws[f"D{labels[lab]}"].value).startswith("="), lab
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        pytest.skip("LibreOffice not installed: formulas not recalculated")
    out = tmp_path / "recalc"
    out.mkdir()
    subprocess.run([soffice, "--headless", "--convert-to", "xlsx", "--outdir", str(out), str(xl)],
                   check=True, capture_output=True, timeout=180)
    vals = openpyxl.load_workbook(out / xl.name, data_only=True)["ScamShield_Model"]
    for col, scen in zip("CDE", im.SCEN):
        exp = im.compute(P(scen))
        assert vals[f"{col}{labels['NET MONTHLY BENEFIT']}"].value == pytest.approx(exp["net_benefit"], rel=1e-6)
        assert vals[f"{col}{labels['Prevented loss']}"].value == pytest.approx(exp["prevented_loss"], rel=1e-6)
        assert vals[f"{col}{labels['False alarms per month']}"].value == pytest.approx(exp["fp"], rel=1e-6)
    for sh in openpyxl.load_workbook(out / xl.name, data_only=True).worksheets:
        for row in sh.iter_rows():
            for c in row:
                assert not (isinstance(c.value, str) and c.value.startswith("#")), (sh.title, c.coordinate, c.value)
