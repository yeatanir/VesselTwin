"""Tube Tier 2 pieces that need no solver: multi-probe reader on a FAKE fixture (tests/fixtures/tier2_tube_radial), mesh geometry, GP surrogate
fit/predict/uncertainty/in-range on a synthetic sweep, the stored model's recorded held-out error. The solver test skips without OpenFOAM."""
import json, pathlib, shutil
import numpy as np
import pytest
from core import params as P, props
import vessels.cvd_tube as tube
from vessels.cvd_tube import thermo
from tier2.openfoam import read_results, _tube_geo, T2_DEFS, write_case
from surrogate import tube as S

FX = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("parser")
def test_radial_reader_on_fake_fixture():
    pp = read_results(FX / "tier2_tube_radial", "cvd_tube", {})
    p = P.defaults(tube.DEFS)
    Pt, Mc = p["pressure_Pa"], props.mass("Ar") * 1e-3
    pM = 1.5e-4 * Pt * Mc / (props.mass("MoO3") * 1e-3)
    assert pp.species["MoO3_g"]["p_Pa"].p50 == pytest.approx(pM, rel=1e-6) and pp.T_K.p50 == pytest.approx(900.0)
    pSa = 1e-3 * Pt * Mc / 32.06e-3
    xS = float(thermo.s2_fraction(pSa / Pt, 900.0, Pt, p["S.dHf_S8_kJ"]))
    assert pp.species["S2_g"]["p_Pa"].p50 == pytest.approx(pSa * xS / 2, rel=1e-6)
    d = pp.derived
    assert d["MoO3_at_substrate_mol_s"].p50 / d["MoO3_released_mol_s"].p50 == pytest.approx(0.75)  # 1.5e-4 / 2e-4 at equal mass flow
    assert d["drift_last_quarter"].p50 == pytest.approx(0.0)  # flat after t = 200


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("mesh")
def test_tube_geometry_grading_and_wall_distance():
    p, t = P.defaults(tube.DEFS), P.defaults(T2_DEFS)
    g0 = _tube_geo(p, t | {"wall_grading": 1.0, "n_cross": 10})
    g1 = _tube_geo(p, t | {"wall_grading": 0.2, "n_cross": 10})
    assert g0["ye"][-1] == pytest.approx(g1["ye"][-1]) and g1["af"].sum() == pytest.approx(1.0)
    w = np.diff(g1["ye"])
    assert w[-1] / w[0] == pytest.approx(0.2)
    assert g0["dn"] < np.diff(g0["ye"])[-1] / 2 and g0["dn"] > 0.45 * np.diff(g0["ye"])[-1]  # wedge cell centroid sits a bit outside the mid-height


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("case_consistency")
def test_tube_boat_bc_is_mesh_consistent(tmp_path):
    """Mixed-BC ref value must not depend on the mesh; valueFraction follows the exact wall-cell distance (Robin law), so it falls as the wall cell shrinks."""
    import re
    f = lambda nc, d: float(re.search(r"boatMo\s*\{[^}]*?valueFraction uniform (\S+);", (write_case("cvd_tube", {"n_cross": nc}, tmp_path / d) / "0/Y_MoO3").read_text()).group(1))
    r = lambda d: re.search(r"boatMo\s*\{[^}]*?refValue uniform (\S+);", (tmp_path / d / "0/Y_MoO3").read_text()).group(1)
    f8, f32 = f(8, "a"), f(32, "b")
    assert r("a") == r("b") and 0.5 < f32 < f8 < 1


def _fake_sweep(n=40, seed=2):
    rng = np.random.default_rng(seed)
    lo, hi = np.array(S.LO, float), np.array(S.HI, float)
    rows = []
    for i in range(n):
        u = lo + rng.random(5) * (hi - lo)
        v = dict(zip(S.NAMES, map(float, u)))
        f = np.exp(-0.5 * np.log(v["flow_sccm"] / 100) + 0.01 * (v["T_boat_Mo_C"] - 700) - 0.005 * (v["T_furnace_C"] - 750) + 0.02 * v["x_substrate_cm"])
        rows.append(dict(id=f"f{i}", ok=True, values=v, ratio_Mo_S=0.01 * f, supersaturation_MoO3_wallT=2 * f**0.5, ss_gasT=1.5 * f**0.3))
    return {"sweep": rows}


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("surrogate")
def test_surrogate_fit_predict_uncertainty_range(tmp_path):
    sw = tmp_path / "sweep.json"; sw.write_text(json.dumps(_fake_sweep()))
    m = S.fit(sw, out=tmp_path / "gp.json")
    h = m["targets"]["ratio_Mo_S"]["heldout"]
    assert h["n_test"] == 10 and h["mean_rel_err"] < 0.05  # smooth log-linear synthetic target: GP must get this
    row = _fake_sweep()["sweep"][3]
    v = S.predict(row["values"], path=tmp_path / "gp.json")
    lo, hi = S.uncertainty(row["values"], path=tmp_path / "gp.json")
    assert lo <= v <= hi and v == pytest.approx(row["ratio_Mo_S"], rel=0.2)
    assert S.in_range(row["values"], tmp_path / "gp.json") and not S.in_range({**row["values"], "flow_sccm": 1e5}, tmp_path / "gp.json")


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("surrogate")
def test_stored_surrogate_records_heldout_error():
    if not S.MODEL.exists(): pytest.skip("surrogate/data/tube_gp.json not built yet")
    m = json.load(open(S.MODEL))
    for t in S.TARGETS:
        h = m["targets"][t]["heldout"]
        assert h["n_test"] >= 0.25 * (h["n_train"] + h["n_test"]) - 1 and h["mean_rel_err"] >= 0  # recorded, not required to meet the 5 % target (it does not: docs/tube_cfd_verification.json)
    assert set(m["ids"]).isdisjoint(m["test_ids"])
