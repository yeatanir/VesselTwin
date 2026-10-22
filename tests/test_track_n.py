"""Track N: furnace/quartz/gas/boat model (vessels/cvd_tube/furnace.py). Legacy bit-for-bit reproduction, analytic limits, schema."""
import json, math, os
import numpy as np
import pytest
from core import params as Pm, props
from vessels import cvd_tube as T
from vessels.cvd_tube import furnace as F, wulff
from bench.track_n import capture_reference as CR
from bench import track_n_score as S

HERE = os.path.dirname(os.path.abspath(__file__))
REF = json.load(open(os.path.join(HERE, "..", "bench", "track_n", "default_reference.json")))


def V(**kw):
    tab = kw.pop("wall_profile_table", None)  # extra key, not a ParamDef (see furnace.TABLE_KEY)
    v = Pm.validate(wulff.DEFS, kw)
    return v | ({"wall_profile_table": tab} if tab is not None else {})


def test_legacy_default_reproduces_stored_reference_bit_for_bit():
    now = json.loads(json.dumps(CR.capture()))  # same JSON round trip as the stored file (exact floats)
    assert now == REF


def test_thermal_model_default_is_legacy_and_adds_no_mc_sigma():
    assert V()["thermal_model"] == "legacy"
    assert all(d.sigma == 0.0 for d in T.DEFS if d.name in F.FNAMES)  # MC streams of the legacy model unchanged
    assert any(d.sigma for d in F.FDEFS)  # the real sigmas live in FDEFS (used by furnace.profile)


def test_every_furnace_paramdef_has_unit_bounds_source():
    for d in F.FDEFS:
        assert d.unit is not None and d.source
        if d.choices is None and not isinstance(d.default, str):
            assert d.lo is not None and d.hi is not None and d.lo <= d.default <= d.hi, d.name


def test_expansion_factor_exact():
    for t in (300.0, 873.15, 1273.0):
        assert F.expansion_factor(t) == t / 273.15
    v = V(pressure_Pa=101325.0, flow_sccm=100.0)
    pr = F.profile(v | {"gas_model": "graetz_1d"}, n=60, n_mc=0)
    d = v["tube_id_in"] * 0.0254
    q_std = 100e-6 / 60 / (math.pi * d**2 / 4)  # m/s at standard conditions
    for i in (5, 30, 45):
        assert pr["u_mean_m_s"][i] == pytest.approx(q_std * pr["T_gas_mean_K"][i] / 273.15, rel=1e-12)


def test_uniform_wall_gives_uniform_gas_far_downstream():
    tab = "0:800;100:800"
    for gm in ("energy_2d", "graetz_1d"):
        pr = F.profile(V(wall_profile_table=tab, gas_model=gm, S_heat_belt="off", quartz_coupling="off"), n=101, n_mc=0)
        assert pr["T_gas_mean_K"][-1] == pytest.approx(800 + 273.15, abs=0.5)
        assert pr["T_gas_centre_K"][-1] == pytest.approx(800 + 273.15, abs=0.5)
        assert np.all(np.array(pr["T_gas_mean_K"]) <= 800 + 273.15 + 1e-6)  # heats monotonically, never overshoots


def test_zero_flow_limit_gas_follows_wall():
    # gentle wall ramp: the gas keeps a radial-conduction smoothing length ~ R/2.4 (~0.5 cm) even at zero flow, so a steep edge would show O(10 K) smoothing
    xs = np.linspace(0, 100, 51)
    ss = lambda t: np.clip(t, 0, 1) ** 2 * (3 - 2 * np.clip(t, 0, 1))  # smoothstep: no kinks (a kink smears over ~R)
    tab = [[a, 25 + 775 * ss((a - 20) / 60)] for a in xs]
    pr = F.profile(V(flow_sccm=1.0, quartz_coupling="off", wall_profile_table=tab, S_heat_belt="off"), n=101, n_mc=0)
    assert np.max(np.abs(np.array(pr["T_gas_mean_K"]) - np.array(pr["T_quartz_K"]))) < 1.0
    assert np.max(np.abs(np.array(pr["T_gas_centre_K"]) - np.array(pr["T_quartz_K"]))) < 1.0


def test_energy_balance_closes():
    pr = F.profile(V(), n=60, n_mc=0)
    assert pr["scalars"]["energy_balance_residual"] < 1e-8


def test_fully_developed_nusselt_in_2d_solver():
    """Constant wall T, constant properties, far downstream: Nu = q'/(pi k dT) -> 3.66 (Graetz problem, Nu_inf)."""
    v = V(gas_props="cfd_const", flow_sccm=2000.0, L_tube_cm=300.0)
    L = 3.0
    res = F.energy_2d(v, lambda x: np.full_like(np.asarray(x, float), 1000.0), L, nx=1200, nr=40)
    k = float(F.gas_props(v)[0](1000.0))
    dT = 1000.0 - res["Tm"]
    i = int(np.argmin(np.abs(dT - 1.0)))  # where the bulk is within 1 K of the wall
    Nu = res["q_w"][i] / (math.pi * k * dT[i])
    assert Nu == pytest.approx(3.66, rel=0.05)


def test_band_fraction_planck():
    from scipy.integrate import quad
    pl = lambda lam, Tk: 1 / lam**5 / (math.exp(C2 / (lam * Tk)) - 1)
    C2 = F.C2
    for Tk in (600.0, 1000.0, 1500.0):
        tot = quad(lambda l: pl(l, Tk), 0.1, 400, limit=400, points=[1, 3, 10])[0]
        part = quad(lambda l: pl(l, Tk), 0.1, 4.0, limit=400)[0]
        assert float(F.band_fraction(4.0, Tk)) == pytest.approx(part / tot, abs=3e-3)
    assert float(F.band_fraction(2898.0 / 1000.0, 1000.0)) == pytest.approx(0.25, abs=0.01)  # lam T = 2898 um K
    assert float(F.band_fraction(1000.0, 1500.0)) == pytest.approx(1.0, abs=1e-6)  # lam T -> infinity
    assert float(F.band_fraction(0.01, 1000.0)) == pytest.approx(0.0, abs=1e-12)


def test_body_in_isothermal_enclosure_takes_the_enclosure_temperature():
    for kind in ("boat", "sub"):
        for Tk in (500.0, 1000.0, 1300.0):
            Tb, UA = F.body_balance(V(), kind, Tk, Tk, Tk)
            assert float(Tb) == pytest.approx(Tk, abs=1e-6) and float(UA) > 0
    Tb, _ = F.body_balance(V(), "boat", 1000.0, 600.0, 300.0)  # between the sources
    assert 300.0 < float(Tb) < 1000.0


def test_nir_window_heats_a_body_above_the_quartz_when_the_element_is_hotter():
    v = V(boat_nir_abs=0.9, quartz_nir_transmit=1.0)
    hot, _ = F.body_balance(v, "boat", 1200.0, 1000.0, 1000.0)
    blind, _ = F.body_balance(V(boat_nir_abs=0.05, quartz_nir_transmit=0.3), "boat", 1200.0, 1000.0, 1000.0)
    assert float(hot) > float(blind) > 1000.0 - 1e-9


def test_quartz_network_limits():
    pr_off = F.profile(V(quartz_coupling="off"), n=60, n_mc=0)
    assert pr_off["T_quartz_K"] == pr_off["T_wall_K"]
    v = V(quartz_k_W_mK=3.2, gap_conduction_W_m2K=40.0, quartz_wall_mm=0.5)
    a = F.r_prime(v, 1000.0, 1000.0)[0]
    b = F.r_prime(V(), 1000.0, 1000.0)[0]
    assert a < b
    pr = F.profile(V(), n=60, n_mc=0)  # loaded quartz never exceeds the element profile when heating the gas on average
    assert pr["scalars"]["quartz_fin_length_cm"] < 0.2 * 12.0


def test_table_profile_and_zones():
    p = V(wall_profile_table="0:25;20:25;30:900;70:900;80:25;100:25", S_heat_belt="off")
    x = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    assert np.allclose(F.element_T(p, x), np.interp(x, [0, .2, .3, .7, .8, 1.0], [25, 25, 900, 900, 25, 25]) + 273.15)
    z = V(furnace_zones=3, T_furnace_C=600.0, T_zone2_C=800.0, T_zone3_C=700.0, L_hot_cm=60.0, ramp_cm=5.0, zone_blend_cm=3.0, x_furnace_center_cm=50.0)
    T3 = F.element_T(z, np.array([0.30, 0.50, 0.70])) - 273.15  # three 20 cm zones: centres at 30, 50, 70 cm
    assert T3 == pytest.approx([600, 800, 700], abs=5.0)
    assert F.element_T(V(), np.array([0.0]))[0] == pytest.approx(298.15, abs=0.5)


def test_positions_from_centre():
    q = F.resolve_positions(V(positions_from_centre="on", L_tube_cm=100.0, dx_MoO3_from_centre_cm=-5.0, dx_S_from_centre_cm=-30.0))
    assert q["x_MoO3_cm"] == 45.0 and q["x_S_boat_cm"] == 20.0 and q["x_substrate_cm"] == 12.0


def test_profile_schema_finite_and_complete():
    n = 80
    pr = F.profile(V(), n=n, n_mc=6)
    arrays = ["x_cm", "T_wall_K", "T_quartz_K", "T_gas_centre_K", "T_gas_mean_K", "T_boat_K", "T_substrate_K", "u_mean_m_s", "u_centre_m_s", "Re", "Pe_thermal", "Pe_mass",
              "Gr", "Ri", "Ra", "tau_cum_s"]
    for k in arrays:
        assert len(pr[k]) == n and np.all(np.isfinite(pr[k])), k
        assert k in pr["units"]
    assert set(pr["flags"]) == {"laminar", "buoyancy_matters", "axial_conduction_matters", "thermally_developed"}
    for k in ("T_wall_K", "T_gas_mean_K", "T_boat_K", "T_substrate_K", "u_mean_m_s", "Re", "Ri"):
        assert len(pr["p05"][k]) == n and len(pr["p95"][k]) == n
        assert np.all(np.array(pr["p05"][k]) <= np.array(pr["p95"][k]) + 1e-9)
    for s in ("boat_MoO3", "boat_S", "substrate"):
        assert np.isfinite(pr["stations"][s]["T_gas_mean_K"]) and "flags" in pr["stations"][s]
    assert pr["notes"] and pr["constants"] and pr["schema"] == "cvd_tube.furnace.profile/1"
    assert all(np.isfinite(v) for v in pr["scalars"].values() if isinstance(v, float))
    json.dumps(pr)  # serialisable
    assert pr["stations"]["substrate"]["T_body_p05_K"] <= pr["stations"]["substrate"]["T_body_p95_K"]


def test_centreline_lags_the_mean_when_heating_and_leads_when_cooling():
    pr = F.profile(V(), n=200, n_mc=0)
    x, Tm, Tc, Tw = (np.array(pr[k]) for k in ("x_cm", "T_gas_mean_K", "T_gas_centre_K", "T_quartz_K"))
    up = (x > 25) & (x < 40)
    dn = (x > 60) & (x < 72)
    assert np.all(Tc[up] <= Tm[up] + 0.2) and np.all(Tc[dn] >= Tm[dn] - 0.2)


def test_furnace_switch_runs_through_solve_and_conserves_mass():
    s = T.solve(V(thermal_model="furnace"))
    assert s["balance_err"] < 1e-6 and np.isfinite(s["supersaturation_MoO3"])
    s_in = T.solve(V(thermal_model="furnace", boat_temperature="input"))
    assert s_in["balance_err"] < 1e-6
    reg, margin, nums = T.tier0(V(thermal_model="furnace"))
    assert np.isfinite(nums["Re"])


def test_computed_boat_is_close_to_local_quartz_at_the_plateau():
    q = F.apply(V(thermal_model="furnace"))
    wall = float(F.twall(V(), np.array([0.5]))[0]) - 273.15
    assert abs(q["T_boat_Mo_C"] - wall) < 15.0  # radiation + contact dominate the gas at these flows (assumptions synthetic)


def test_legacy_gas_helper_matches_the_march():
    v = V()
    x, Tt, o, m = T.march(v)
    dx = m["dx"]
    edges = np.r_[x[0] - dx, x]
    xo, Tg = S.legacy_gas(v, edges, lambda xx: T.twall(v, xx))
    assert np.allclose(Tg, o["Tg"], rtol=0, atol=1e-9)  # o['Tg'] is the cell-exit gas temperature


def test_cfd_extract_is_complete_and_gravity_free():
    d = json.load(open(os.path.join(HERE, "..", "bench", "track_n", "cfd_extract.json")))
    assert len(d) == 52 and all("error" not in v for v in d.values())
    assert all(v["gravity"] == "0 0 0" for v in d.values())
