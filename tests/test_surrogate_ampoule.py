"""Ampoule CFD verification data + GP surrogate (surrogate/ampoule.py). Solver test skips without OpenFOAM on PATH."""
import json, pathlib, shutil, sys
import numpy as np
import pytest
from surrogate import ampoule as sa

ROOT = pathlib.Path(__file__).resolve().parents[1]
V = json.load(open(ROOT / "docs" / "ampoule_cfd_verification.json"))


@pytest.mark.vessel("ampoule")
@pytest.mark.check("cfd_sweep_schema")
def test_sweep_json_schema():
    rows = V["sweep"]
    assert len(rows) >= 40
    for r in rows:
        assert {"id", "values", "tier0_f", "tier0_regime", "f_cfd", "ok", "drift_last_quarter"} <= set(r)
        assert r["ok"] and r["f_cfd"] > 0.9 and r["tier0_regime"] in ("convection_assisted", "transport_limited")
        x = sa._x(r["values"])
        assert np.all(x[[1, 2, 3]] >= [sa.LO[1], sa.LO[2], sa.LO[3]]) and np.all(x[[1, 2, 3]] <= [sa.HI[1], sa.HI[2], sa.HI[3]])
    for th in ("threshold_1.1", "threshold_1.2"):
        a = V["regime_agreement"][th]
        assert a["agreement"] == pytest.approx(1 - a["n_disagree"] / a["n"]) and a["n_disagree"] == len(a["disagreeing"])
    assert {r["tier0_regime"] for r in rows} == {"convection_assisted", "transport_limited"}  # sweep covers both regimes


@pytest.mark.vessel("ampoule")
@pytest.mark.check("surrogate_heldout")
def test_surrogate_reproduces_stored_heldout_error():
    s = V["surrogate"]
    rows = {r["id"]: r for r in V["sweep"]}
    err = [abs(sa.predict(rows[i]["values"]) / rows[i]["f_cfd"] - 1) for i in s["test_ids"]]
    assert len(err) == s["n_test"] >= 0.25 * len(rows) - 1
    assert np.mean(err) == pytest.approx(s["mean_rel_err_f"], rel=0.02, abs=1e-4) and max(err) <= s["max_rel_err_f"] * 1.02 + 1e-4


@pytest.mark.vessel("ampoule")
@pytest.mark.check("surrogate_range")
def test_in_range_flag_and_output():
    v = dict(D_mm=20.0, L_cm=15.0, T_source_C=900.0, T_sink_C=800.0, tilt_deg=0.0, agent_mg_per_cm3=3.0)
    o = sa.predict_full(v)
    assert o["in_range"] and o["f_lo"] <= o["f"] <= o["f_hi"] and o["f"] > 0
    assert not sa.predict_full(v | {"D_mm": 80.0})["in_range"] and not sa.predict_full(v | {"tilt_deg": 120.0})["in_range"]
    assert sa.predict_full(v | {"T_source_C": 1100.0})["in_range"] is False  # dT = 300 K outside 10-150


@pytest.mark.vessel("ampoule")
@pytest.mark.check("openfoam_run")
@pytest.mark.skipif(not (shutil.which("blockMesh") and shutil.which("ampouleBoussinesqFoam")), reason="OpenFOAM v2512 + ampouleBoussinesqFoam not on PATH")
def test_diffusion_case_f_near_one(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import ampoule_cfd_sweep as sw
    r = sw.run({"id": "d", "values": {"D_mm": 10.0, "tilt_deg": 0.0, "cells_per_cm": 3.0, "n_cross": 8}}, tmp_path)
    assert r["ok"] and 0.98 < r["f_cfd"] < 1.03
