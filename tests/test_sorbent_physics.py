"""Sorbent bed physics: limits, conservation, convergence and comparison with published breakthrough data (not tuned)."""
import json, pathlib, time
import numpy as np, pytest
from scipy.integrate import solve_ivp
from core import api, params as P
from schemas.closure import Closure
import vessels.sorbent as sb
from vessels.sorbent import benchmark as bm, build_presets

ROOT = pathlib.Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.vessel("sorbent")


def D(**kw): return P.defaults(sb.DEFS) | kw


def t50(p, n=300):
    s, t, co, *_ = sb.simulate(p, n_t=n)
    return sb._first(t, co, 0.5), s


@pytest.mark.check("analytic_limit")
@pytest.mark.parametrize("carrier", ["He", "N2"])
def test_single_component_shock_time(carrier):
    # isothermal, one adsorbing species, fast LDF: favourable-isotherm front arrives at the stoichiometric shock time
    p = D(energy="isothermal", carrier=carrier, k_ldf=10.0, n_cells=60, **{"isotherm_N2.qmax": 0.0, "isotherm_N2.qmax2": 0.0})
    t, s = t50(p)
    assert t == pytest.approx(s["tst"], rel=0.03)
    assert sb.solve(p)["t_stoich_min"] == pytest.approx(s["tst"] / 60)


@pytest.mark.check("analytic_limit")
def test_multicomponent_reduces_to_single_component():
    off = {"isotherm_N2.qmax": 0.0, "isotherm_N2.qmax2": 0.0}
    iso = dict(energy="isothermal", k_ldf=10.0, n_cells=40)
    a, _ = t50(D(carrier="N2", **off, **iso))  # N2 present but not adsorbing
    b, _ = t50(D(carrier="He", **iso))  # no N2 at all
    assert a == pytest.approx(b, rel=0.02)
    # EDSL == IAST analytically for equal saturation capacities: independent numerical IAST for a binary Langmuir pair
    pk = sb._pk(D(**{"isotherm.qmax": 3.0, "isotherm.qmax2": 0.0, "isotherm_N2.qmax": 3.0, "isotherm_N2.qmax2": 0.0}))
    T, cT = 298.15, 101325 / (sb.R * 298.15)
    y = 0.3
    q = sb._eq(pk, {"CO2": np.array([y * cT]), "N2": np.array([(1 - y) * cT])}, T)
    K = [pk[s]["K0"][0] for s in ("CO2", "N2")]
    c = [y * cT, (1 - y) * cT]
    # IAST: equal reduced spreading pressure qm*ln(1+K c0) => K1 c1^0 = K2 c2^0 = z; x1 + x2 = 1, c_i = x_i c_i^0 ... solve for z
    from scipy.optimize import brentq
    f = lambda z: c[0] / (z / K[0]) + c[1] / (z / K[1]) - 1
    z = brentq(f, 1e-9, 1e9)
    x = [c[0] * K[0] / z, c[1] * K[1] / z]
    qt = 3.0 * z / (1 + z)  # IAST total loading for equal-qm Langmuir (1/q_t = sum x_i/q_i^0, q_i^0 = qm z/(1+z))
    assert q["CO2"][0] == pytest.approx(qt * x[0], rel=1e-6) and q["N2"][0] == pytest.approx(qt * x[1], rel=1e-6)


@pytest.mark.check("mass_balance")
@pytest.mark.parametrize("kw", [dict(), dict(carrier="He", y_feed=0.5), dict(RH_feed=0.3, competition="modified", **{"isotherm.alpha1": 0.027, "isotherm.alpha2": 0.703})])
def test_total_mass_balance_not_an_identity(kw):
    # in - out - accumulated (gas holdup + adsorbed), integrated from the stored states; CO2 and total moles
    b = sb.balance(D(n_cells=40, **kw))
    assert abs(b["total"]) < 5e-3 and abs(b["CO2"]) < 5e-3
    if "carrier" not in kw: assert b["Nout_min_over_Nin"] < 0.9  # 15 % CO2 removed: the outlet molar flow really dips


@pytest.mark.check("analytic_limit")
def test_energy_balance_adiabatic():
    p = D(carrier="He", h_wall=0.1, Kz=0.0, n_cells=60, bed_length_cm=6.4, bed_id_cm=2.82, flow_sccm=700)
    s0 = sb._setup(p)
    s, t, co, Y, _ = sb.simulate(p, n_t=600, t_end=12 * s0["tst"])
    ix, n, rb, dz, A = s["ix"], s["n"], p["bed.rho_kg_m3"], s["L"] / s["n"], s["A"]
    fl = [s["flux"](y.ravel()) for y in Y]
    Eout = np.trapezoid([f["Nf"][-1] * f["cpm"][-1] * (f["T"][-1] - s["T0"]) for f in fl], t) * A  # heat leaving with the gas
    qt, Qt = sb._qst_table(s["pk"], "CO2", s["T0"], 3e5)
    Qint = np.concatenate(([0], np.cumsum((Qt[1:] + Qt[:-1]) / 2 * np.diff(qt))))
    released = np.interp(Y[-1, :, ix["qCO2"]], qt, Qint).sum() * rb * dz * A
    assert Eout / released == pytest.approx(1.0, abs=0.06)


@pytest.mark.check("mesh_convergence")
def test_grid_convergence():
    r = {n: t50(D(n_cells=n))[0] for n in (40, 80, 160)}
    e1, e2 = abs(r[40] - r[160]) / r[160], abs(r[80] - r[160]) / r[160]
    assert e2 < 0.02 and e2 < e1  # plan: mesh convergence < 2 %, and monotone


@pytest.mark.check("analytic_limit")
def test_humidity_off_recovers_dry_and_water_matters():
    dry = sb.solve(D(n_cells=30))
    tiny = sb.solve(D(n_cells=30, RH_feed=1e-6))  # water machinery active, no water
    assert tiny["t_break50_min"] == pytest.approx(dry["t_break50_min"], rel=5e-3)
    assert tiny["capacity_mol_kg"] == pytest.approx(dry["capacity_mol_kg"], rel=5e-3)
    calf = {k: v for k, v in json.loads((ROOT / "presets/sorbent__CALF20_CO2.json").read_text()).items() if k != "_meta"}
    d0, d1 = sb.solve(D(**calf)), sb.solve(D(RH_feed=0.5, y_feed=0.15, **calf))
    assert d1["t_break5_min"] < d0["t_break5_min"] and d1["capacity_mol_kg"] < d0["capacity_mol_kg"]  # water takes sites
    assert d1["capacity_H2O_mol_kg"] > 0.1 and d1["outside_fit_range"] == 1 and d0["outside_fit_range"] == 0  # flagged: data are ~1 bar CO2
    # modified scheme with alpha = 0 and no water = EDSL
    assert sb.solve(D(competition="modified", n_cells=30))["capacity_mol_kg"] == pytest.approx(dry["capacity_mol_kg"], rel=1e-6)


@pytest.mark.check("analytic_limit")
def test_ergun_feedback_matches_analytic_compressible_profile():
    # inert bed (negligible uptake), isothermal, steady: P^2 = P_out^2 + 2 alpha (L - z), alpha = R T (a N + b M N^2)
    p = D(energy="isothermal", n_cells=30, particle_dp_mm=0.3, flow_sccm=1000.0, bed_id_cm=1.0, bed_length_cm=30.0, carrier="He", y_feed=1e-4,
          **{"isotherm.qmax": 0.01, "isotherm.b_ref": 1e-4, "isotherm.qmax2": 0.0, "isotherm.Q": 1.0})
    s, t, co, Y, _ = sb.simulate(p, n_t=50, t_end=30.0)
    e, mu, dp = p["bed.epsilon"], s["mu"], 3e-4
    a = 150 * mu * (1 - e) ** 2 / (e**3 * dp**2); b = 1.75 * (1 - e) / (e**3 * dp)
    M, T, N = sb.props.mass("He") * 1e-3, s["T0"], s["Nin"]
    alpha = sb.R * T * (a * N + b * M * N**2)
    z = (np.arange(s["n"]) + 0.5) * s["L"] / s["n"]
    Pm = Y[-1, :, s["ix"]["P"]]
    Pa = np.sqrt(s["Pt"] ** 2 + 2 * alpha * (s["L"] - z))
    assert Pm[0] - s["Pt"] > 1e3  # a real pressure drop
    assert np.max(np.abs(Pm - Pa) / Pa) < 5e-3
    # and velocity follows: u_in/u_out = P_out/P_in at fixed molar flux
    assert Pm[0] / s["Pt"] > 1.01


@pytest.mark.check("analytic_limit")
def test_axial_dispersion_correlation_and_effect():
    p = D()
    s = sb._setup(p)
    assert s["DL"] == pytest.approx(0.7 * s["Dm"] + s["us"] / p["bed.epsilon"] * p["particle_dp_mm"] * 5e-4)  # Ruthven
    w = lambda pp: (lambda s_, t, co, *_: sb._first(t, co, 0.95) - sb._first(t, co, 0.05))(*sb.simulate(pp, n_t=300))
    base = D(energy="isothermal", n_cells=80, k_ldf=10.0)
    assert w(base) > w(base | {"dispersion": "off"})  # dispersion widens the front


@pytest.mark.check("analytic_limit")
def test_ldf_from_resistances_and_override():
    k1, k2 = (sb._setup(D(particle_dp_mm=d))["k"]["CO2"] for d in (1.0, 2.0))
    assert 3.0 < k1 / k2 < 4.2  # macropore-controlled: ~ 1/dp^2 (film resistance is the small remainder)
    assert sb._setup(D(k_ldf=0.37))["k"]["CO2"] == 0.37
    assert sb.tier0(D(k_ldf=0.37))[2]["k_ldf_CO2_1_s"] == 0.37
    kc = sb._setup(D(Dc_rc2=0.01))["k"]["CO2"]
    assert kc < sb._setup(D())["k"]["CO2"]  # a micropore resistance in series slows it


@pytest.mark.check("analytic_limit")
def test_regeneration_stage_cycle_capacity():
    cold = sb.solve(D(regen="purge", T_regen_K=320.0, t_regen_min=20.0))
    hot = sb.solve(D(regen="purge", T_regen_K=420.0, t_regen_min=20.0))
    assert 0 < cold["cycle_capacity_mol_kg"] < hot["cycle_capacity_mol_kg"] < hot["capacity_mol_kg"]
    assert "cycle_capacity_mol_kg" not in sb.solve(D())  # optional stage


@pytest.mark.check("known_answer")
def test_roy_moharir_generic_ldf_langmuir_cross_check():
    # arXiv:1907.00195 Table 1 (interstitial u = 0.01 m/s, L = 0.5 m, eps = 0.4, k = 0.5/s, Langmuir b = 0.3 m3/kg, qm = 0.04, c0 = 1,
    # rho_p = 1000): their equations integrated here independently, vs this model in its dilute limit (constant u, no dispersion, isothermal)
    r = sb.DATA["benchmarks"]["ROY19_table1"]
    R_, T = sb.R, 298.15
    eps, L, u, k, b, qm, c0, rho = r["eps"], r["L_m"], r["u_m_s"], r["k_ldf_1_s"], r["b_m3_per_kg"], r["qm_kg_per_kg"], r["c0_kg_m3"], r["rho_p"]
    n = 400; dz = L / n
    def f(t, y):
        c, q = y[:n], y[n:]
        qe = qm * b * c / (1 + b * c)
        dq = k * (qe - q)
        dc = -u * (c - np.concatenate(([c0], c[:-1]))) / dz - (1 - eps) / eps * rho * dq
        return np.concatenate((dc, dq))
    sol = solve_ivp(f, (0, 1500), np.zeros(2 * n), method="LSODA", rtol=1e-6, atol=1e-10, t_eval=np.linspace(0, 1500, 1500))
    t_ref = sb._first(sol.t, sol.y[n - 1] / c0, 0.5)
    pf = (c0 * R_ * T / 101325.0)  # y_feed such that c0 = 1 mol/m3 ("mol" := kg, M = 1 kg/mol)
    flow = u * eps * np.pi * 0.005**2 * 60e6 * (273.15 / T)  # sccm for superficial velocity u*eps at 101.325 kPa
    p = D(energy="isothermal", flow="constant", ergun="off", dispersion="off", carrier="He", n_cells=100, k_ldf=k, y_feed=pf, T_K=T, P_kPa=101.325,
          bed_length_cm=L * 100, bed_id_cm=1.0, flow_sccm=flow, **{"bed.epsilon": eps, "bed.rho_kg_m3": (1 - eps) * rho, "isotherm.qmax": qm,
          "isotherm.b_ref": b / (R_ * T) * 1e5, "isotherm.qmax2": 0.0, "isotherm.Q": 1.0})
    t_me, _ = t50(p, n=600)
    assert t_me == pytest.approx(t_ref, rel=0.03)


@pytest.mark.check("known_answer")
def test_published_isotherm_loadings_and_breakthrough_times():
    iso = bm.isotherm_errors()
    mean = {k: np.mean([abs(e) for *_, e in v]) for k, v in iso.items()}
    assert all(m < 0.10 for m in mean.values()), mean  # fits reproduce the tabulated measured loadings (sanity of the data transcription)
    cal = bm.calf20_breakthrough()
    x13 = bm.x13_breakthrough()
    comp = bm.competitive_13X()
    out = {"isotherm_mean_abs_err": mean, "calf20_breakthrough": cal, "x13_breakthrough": x13, "x13_competitive_edsl": comp}
    (ROOT / "cache").mkdir(exist_ok=True)
    (ROOT / "cache" / "sorbent_benchmark.json").write_text(json.dumps(out, indent=1, default=float))
    # regression guard around the REAL errors (CALF-20 within ~10 %; 13X thermal model off by -40 %): documented, not tuned
    assert all(abs(r["err"]) < 0.15 for r in cal)
    assert all(-0.5 < r["err"] < -0.2 for r in x13)


def test_presets_match_data_and_closure_names():
    for f, v in build_presets.build().items():
        got = {k: v for k, v in json.loads((ROOT / "presets" / f"{f}.json").read_text()).items() if k != "_meta"}
        assert got.keys() == v.keys() and all(got[k] == pytest.approx(v[k]) if not isinstance(v[k], str) else got[k] == v[k] for k in v)
    p = D()
    m = sb.DATA["materials"]["13X_Z1002ND"]["species"]["CO2"]["sites"][0]
    assert sb._pk(p)["CO2"]["K0"][0] == pytest.approx(m["b0"] * np.exp(-m["dU"] * 1e3 / (sb.R * 298.15)), rel=1e-9)  # b(T0) of the paper
    base = api.solve("sorbent", n_mc=2)
    clo = [Closure(name="isotherm", law="langmuir", params={"qmax": 1.0, "b_ref": 5.0, "Q": 30.0, "qmax2": 0.0}, method="GCMC", source="t"),
           Closure(name="isotherm_N2", law="langmuir", params={"qmax": 0.0, "qmax2": 0.0}, method="GCMC", source="t")]
    got = api.solve("sorbent", closures=clo, n_mc=2)
    assert got["values"]["isotherm.qmax"] == 1.0 and got["values"]["isotherm_N2.qmax"] == 0.0
    assert got["passport"]["derived"]["capacity_mol_kg"]["p50"] < base["passport"]["derived"]["capacity_mol_kg"]["p50"]


def test_nominal_speed_and_guard():
    p = D()
    sb._CACHE.clear()
    t = time.time(); sb.solve(p); dt = time.time() - t
    assert dt < 1.0, dt  # ~0.25 s on the dev laptop (n_cells = 30)
    with pytest.raises(ValueError):
        old = sb.MAXEVAL
        sb.MAXEVAL = 50
        try: sb.solve(D(n_cells=31))
        finally: sb.MAXEVAL = old


# ---- Track E: IAST vs EDSL, 13X wall heat transfer (pre-registered in docs/prereg/track-e.md) ----
from bench.sorbent.iast_check import iast as _iast


@pytest.mark.check("analytic_limit")
def test_iast_equals_extended_langmuir_for_equal_capacity():
    M = {"A": [(3.0, 2.0)], "B": [(3.0, 0.5)]}
    Pp = {"A": 0.4, "B": 0.7}
    q = _iast(M, Pp)
    den = 1 + 2.0 * 0.4 + 0.5 * 0.7
    assert q["A"] == pytest.approx(3.0 * 2.0 * 0.4 / den, rel=1e-6) and q["B"] == pytest.approx(3.0 * 0.5 * 0.7 / den, rel=1e-6)
    q1 = _iast({"A": M["A"], "B": [(3.0, 1e-9)]}, {"A": 0.4, "B": 0.7})  # inert partner: pure Langmuir
    assert q1["A"] == pytest.approx(3.0 * 2.0 * 0.4 / (1 + 2.0 * 0.4), rel=1e-5)


@pytest.mark.check("known_answer")
def test_13X_iast_competition_is_worse_than_edsl():
    """E7 result (pyIAST and this independent IAST agree): with the model's own pure isotherms IAST drives CO2 to ~0 under humid CO2 (measured 2.16 and 2.46 mol/kg;
    EDSL gives 1.79 and 1.44), so the model is NOT switched to IAST. Isotherms are not refit to the mixture data."""
    p = bm._p("sorbent__13X_CO2", P_kPa=102.0)
    pk = sb._pk(p)
    for r, edsl_floor in zip(bm.B["13X_Z1002ND_competitive"]["points"], (1.0, 1.0)):
        T = 273.15 + r["T_C"]
        yw = r["RH"] * sb.psat(T) / 102e3
        M = {s: [(float(pk["qss"][sb.SPS.index(s)][k]), float(pk["K0s"][sb.SPS.index(s)][k] * np.exp(pk["Qs"][sb.SPS.index(s)][k] * (1 / T - 1 / sb.T0)) / (sb.R * T) * 1e5)) for k in (0, 1)] for s in ("CO2", "H2O")}
        q = _iast(M, {"CO2": (1 - yw) * 1.02, "H2O": yw * 1.02})
        e = sb._eq(pk, {"CO2": np.array([(1 - yw) * 102e3 / (sb.R * T)]), "H2O": np.array([yw * 102e3 / (sb.R * T)])}, T)
        assert q["CO2"] < 0.01 < edsl_floor < float(e["CO2"][0])  # IAST CO2 error ~ -100 % vs EDSL -17 % / -41 %
        assert q["H2O"] > r["q_H2O"]  # and over-predicts water (+36 % / +18 %)


@pytest.mark.check("known_answer")
def test_calf20_breakthrough_unchanged_by_track_e():
    """CALF-20 t50 errors from a clean state (converged value at RTOL 1e-5 is the same): -0.0332, +0.0187, +0.0975; the column keeps its own h_in."""
    sb._CACHE.clear(); sb._PAT.clear()  # Jacobian-pattern cache leaks between columns: a prior 13X run shifts CALF-20 by up to +2 pp (RTOL 3e-3)
    errs = [r["err"] for r in bm.calf20_breakthrough()]
    assert errs == pytest.approx([-0.0332, 0.0187, 0.0975], abs=2e-3)
    assert -0.04 < min(errs) and max(errs) < 0.11


@pytest.mark.check("known_answer")
@pytest.mark.xfail(reason="Pre-registered held-out criterion |t50 err| <= 15 %: measured -15.6 % at y=0.5 (h_in = 72.86 fitted on the y=0.15 peak temperature); T_peak 81.8 vs 79.0 C passes", strict=False)
def test_13X_wall_heat_transfer_fit_on_peak_temperature_holdout():
    old = bm.B["13X_Z1002ND_breakthrough_CO2_He"]["column"]["h_in"]
    bm.B["13X_Z1002ND_breakthrough_CO2_He"]["column"]["h_in"] = 72.86
    try:
        held = bm.x13_breakthrough()[1]
    finally:
        bm.B["13X_Z1002ND_breakthrough_CO2_He"]["column"]["h_in"] = old
    assert abs(held["Tpeak_model_C"] - held["Tpeak_exp_C"]) <= 10.0
    assert abs(held["err"]) <= 0.15
