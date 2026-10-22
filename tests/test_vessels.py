import json, numpy as np, pytest
from core import api, params as P
from schemas.closure import Closure
import vessels.cvd_tube as tube, vessels.ampoule as amp, vessels.flask as fl, vessels.sorbent as sb


def D(m, **kw): return P.defaults(m.DEFS) | kw


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("mass_balance")
def test_tube_mass_balance_and_trend():
    assert tube.solve(D(tube))["balance_err"] < 5e-3
    lo, hi = tube.solve(D(tube, T_boat_Mo_C=650))["ratio_Mo_S"], tube.solve(D(tube, T_boat_Mo_C=720))["ratio_Mo_S"]
    assert hi > lo  # hotter MoO3 boat -> more Mo at the substrate


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_tube_no_condensation_limit_and_position_knob():
    x, T, o, m = tube.march(D(tube), condense=False)
    assert m["NM_out"] == pytest.approx(m["NM_in"])  # nothing lost without a sink
    assert tube.solve(D(tube, x_substrate_cm=6))["ratio_Mo_S"] != tube.solve(D(tube, x_substrate_cm=16))["ratio_Mo_S"]


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_ampoule_schafer_scaling():
    c1, c2 = amp._core(D(amp, L_cm=10, tilt_deg=0)), amp._core(D(amp, L_cm=20, tilt_deg=0))
    assert c1["J"] == pytest.approx(2 * c2["J"], rel=1e-9)  # J ~ 1/s
    assert amp._core(D(amp, T_sink_C=900))["dp"] == pytest.approx(0, abs=1e-6)
    assert amp.solve(D(amp, D_mm=40, L_cm=10))["convection_enhancement"] > 1  # wide tube -> convection


@pytest.mark.vessel("flask")
@pytest.mark.check("known_answer")
def test_flask_mixing_scaling_and_vd_trend():
    t = lambda N: fl._mix(D(fl, stir_rpm=N))["t_micro"]
    slope = np.log(t(1600) / t(800)) / np.log(2)
    assert -1.6 < slope < -1.4  # t_m ~ eps^-1/2 ~ N^-3/2
    xs = [fl.solve(D(fl, stir_rpm=N))["Xs_villermaux_dushman"] for N in (100, 200, 400, 800)]
    assert all(a > b for a, b in zip(xs, xs[1:])) and 0 < xs[0] < 1  # segregation falls with stirring
    with pytest.raises(ValueError):
        fl.solve(D(fl, volume_mL=10, bar_mm=60))


@pytest.mark.vessel("sorbent")
@pytest.mark.check("analytic_limit")
def test_sorbent_shock_time_isothermal():
    s = sb.solve(D(sb, energy="isothermal", k_ldf=10.0))
    assert s["t_break50_min"] == pytest.approx(s["t_stoich_min"], rel=0.03)  # favourable isotherm: shock at stoichiometric time
    assert sb.solve(D(sb))["dT_peak_K"] > 5  # exothermic adsorption heats the bed


@pytest.mark.vessel("sorbent")
def test_closure_overrides_isotherm():
    base = api.solve("sorbent", n_mc=2)
    clo = Closure(name="isotherm", law="langmuir", params={"qmax": 2.0}, method="GCMC", source="test")
    got = api.solve("sorbent", closures=[clo], n_mc=2)
    assert got["values"]["isotherm.qmax"] == 2.0
    assert got["passport"]["derived"]["capacity_mol_kg"]["p50"] < base["passport"]["derived"]["capacity_mol_kg"]["p50"]


@pytest.mark.vessel("core")
def test_api_editable_params_contract():
    for v in api.list_vessels():
        sch = api.schema(v["name"])
        assert sch and all({"name", "label", "unit", "default", "lo", "hi", "group", "source"} <= set(r) for r in sch)
        json.dumps(sch)
    with pytest.raises(ValueError):
        api.solve("flask", {"stir_rpm": -5}, n_mc=2)  # out of bounds bounces
    with pytest.raises(ValueError):
        api.solve("flask", {"nope": 1}, n_mc=2)
    assert api.presets("sorbent")
    out = api.solve("sorbent", preset="sorbent__CALF20_CO2", n_mc=2)
    assert out["values"]["isotherm.qmax"] == 2.387 and out["provenance"]["isotherm.qmax"] != "synthetic"  # CALF-20 now Nguyen 2021 Tab 2.1 (sorbent_data.json)
    assert out["passport"]["synthetic"]  # still true: h_wall/h_in placeholders


@pytest.mark.vessel("llm")
def test_spec_units_converted_to_canonical():
    from core.pipeline import run
    from schemas.setupspec import Field, SetupSpec, Status
    text = "a 25.4 mm tube"
    spec = SetupSpec(vessel="cvd_tube", params={"tube_id_in": Field(value=25.4, unit="mm", span="25.4 mm", status=Status.stated)})
    out = run(spec, text=text, n_mc=2)
    assert out["values"]["tube_id_in"] == pytest.approx(1.0) and out["provenance"]["tube_id_in"] == "stated"


@pytest.mark.vessel("cvd_tube")
def test_api_returns_shape_map_for_tube():
    o = api.solve("cvd_tube", n_mc=4)
    assert o["extras"]["shape_map"]["shape"] and o["extras"]["knob_sensitivity"]
    assert any(d["name"].startswith("k_attach_Mo") for d in api.schema("cvd_tube"))  # wulff knobs are editable too
    assert api.solve("flask", n_mc=2)["extras"] is None
