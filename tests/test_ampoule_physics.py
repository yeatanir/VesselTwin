"""Ampoule CVT physics: limits, conservation, tilt trend, published-rate anchoring (Schmidt et al. 2013, WO2/HgX2)."""
import json, pathlib, time
import numpy as np, pytest
from scipy.optimize import brentq
import vessels.ampoule as amp
from core import params as P

R = 8.314462618
PRE = pathlib.Path(__file__).resolve().parents[1] / "presets"
LEGACY = dict(dissociation="off", stefan="dilute", conv_model="placeholder")  # the pre-multispecies model


def D(**kw): return P.defaults(amp.DEFS) | kw
def preset(n, **kw): return D(**json.loads((PRE / f"ampoule__{n}.json").read_text())) | kw


def old_schafer(p):
    """Independent re-implementation of the original single-reaction Schafer model (A + n/2 I2 = AI_n)."""
    n, Tm = p["n_I_per_C"], 0.5 * (p["T_source_C"] + p["T_sink_C"]) + 273.15
    P0 = p["agent_mg_per_cm3"] * 1e3 / 253.81 * R * Tm
    def pc(T):
        K = np.exp(-(p["dH_kJmol"] * 1e3 - T * p["dS_JmolK"]) / (R * T))
        f = lambda c: c / 1e5 - K * (max(P0 - n * c / 2, 0) / 1e5) ** (n / 2)
        hi = 2 * P0 / n * (1 - 1e-12)
        return brentq(f, 0, hi) if f(hi) > 0 else 2 * P0 / n
    p2, p1 = pc(p["T_source_C"] + 273.15), pc(p["T_sink_C"] + 273.15)
    Pt = 0.5 * ((P0 - n * p2 / 2) + p2 + (P0 - n * p1 / 2) + p1)
    Dc = p["D0_cm2s"] * 1e-4 * (Tm / 273.15) ** p["T_exp"] * 101325 / Pt
    return Dc * (p2 - p1) / (R * Tm * p["L_cm"] / 100), p2, p1, Pt


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_single_species_limit_equals_schafer():
    for kw in (dict(), dict(n_I_per_C=3.0, agent_mg_per_cm3=8.0, L_cm=22), dict(T_source_C=1000, T_sink_C=700)):
        p = D(**kw)
        c = amp._core(p | LEGACY)
        J, p2, p1, Pt = old_schafer(p)
        assert (c["J"], c["p2"], c["p1"], c["Ptot"]) == pytest.approx((J, p2, p1, Pt), rel=1e-9)
        assert c["Jnet"] == pytest.approx(J, rel=1e-9)  # film model, equal D, no inert -> exactly Fick
        s = amp._core(p | dict(dissociation="off", conv_model="placeholder"))  # stefan on, still the same single-species limit
        assert s["Jnet"] == pytest.approx(J, rel=1e-9) and s["stefan"] == pytest.approx(1.0, abs=1e-9)


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_closed_form_schafer_equation_agrees_with_solver():
    # Schafer eq: n = pref (dp/Ptot) Tm^0.75 q/s. Solver with D0 chosen so both prefactors coincide must agree.
    k = 0.1e-4 * 101325 / (R * 273.15**1.75) * 1e-2 * 3600  # mol/h per (K^0.75 cm) for D0 = 0.1 cm2/s
    for pref in (1.8e-4, 0.6e-4):
        p = D(schafer_prefactor=pref, D0_cm2s=0.1 * pref / k, **LEGACY)
        c = amp._core(p)
        assert c["J"] * c["area"] * 3600 == pytest.approx(amp.schafer_closed_form(p), rel=1e-9)
    assert 0.1 * 1.8e-4 / k == pytest.approx(0.0753, abs=1e-3)  # original prefactor <-> D0 = 0.075 cm2/s, same order as the 0.1 convention


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_nondilute_goes_to_dilute_and_binary_stefan_matters_when_concentrated():
    # tiny carrier pressure (very endothermic): film model with unequal binary D -> Fick
    p = D(diff_model="binary", dH_kJmol=300.0, dS_JmolK=0.0, agent_mg_per_cm3=3.0)
    c = amp._core(p)
    assert c["p2"] / c["Ptot"] < 1e-6 and c["stefan"] == pytest.approx(1.0, abs=1e-5)
    # concentrated carrier + unequal D: bulk flow changes the flux by percent level
    q = amp._core(preset("WO2_HgBr2", diff_model="binary", T_source_C=960, T_sink_C=880))
    assert abs(q["stefan"] - 1) > 0.01
    # Ar backfill: extra inert slows diffusion (D ~ 1/P) and the stagnant-Ar bulk flow keeps agent balance small
    # (diffusive flux only: Ra ~ P^2 so the convective factor RISES with Ar, which can offset it in a wide tube)
    r = [amp._core(D(inert_Ar_mbar=a))["Jnet"] for a in (0, 200, 800)]
    assert r[0] > r[1] > r[2] and amp._core(D(inert_Ar_mbar=800))["bal"] < 1e-9
    assert amp._core(D(inert_Ar_mbar=800, diff_model="binary"))["Jnet"] < amp._core(D(diff_model="binary"))["Jnet"]
    assert amp._core(D(inert_Ar_mbar=800, D_mm=4))["f"] < amp._core(D(inert_Ar_mbar=800))["f"]


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_convection_goes_to_diffusion_at_low_ra():
    s = amp.solve(D(D_mm=3.0, L_cm=30.0))
    assert s["convection_enhancement"] == pytest.approx(1.0, abs=1e-5) and s["convection_in_range"] == 1.0
    assert amp.solve(D(tilt_deg=-90))["convection_enhancement"] == 1.0  # stably stratified vertical: pure diffusion
    # horizontal Taylor-dispersion part is quadratic in Ra: halving the density drive (halved dT) quarters (f-1) when composition drive is small
    f = lambda **k: amp._core(D(dH_kJmol=300.0, dS_JmolK=100.0, **k))["f"] - 1
    assert f(T_source_C=900, T_sink_C=800) / f(T_source_C=850, T_sink_C=800) == pytest.approx(4.0, rel=0.35)
    old = amp.solve(D(D_mm=5.0, conv_model="placeholder"))
    assert old["convection_enhancement"] == 1.0  # previous behaviour still reachable


@pytest.mark.vessel("ampoule")
@pytest.mark.check("mass_balance")
def test_agent_and_A_conservation_across_species():
    p = D(n2_I_per_C=3.0, dH2_kJmol=120.0, dS2_JmolK=40.0, dissociation="on", T_source_C=1100, T_sink_C=800)
    c = amp._core(p)
    P0 = p["agent_mg_per_cm3"] * 1e3 / 253.81 * R * c["T"]
    for T, s in ((p["T_source_C"] + 273.15, c["s2"]), (p["T_sink_C"] + 273.15, c["s1"])):
        atoms = 2 * s["B"] + s["X"] + 2 * s["C1"] + 3 * s["C2"]  # iodine atoms: I2, I, AI2, AI3
        assert atoms == pytest.approx(2 * P0, rel=1e-9)
        K = lambda dH, dS: np.exp(-(dH * 1e3 - T * dS) / (R * T))
        assert s["C1"] / 1e5 == pytest.approx(K(p["dH_kJmol"], p["dS_JmolK"]) * (s["B"] / 1e5), rel=1e-9)  # AI2: b = 1
        assert s["C2"] / 1e5 == pytest.approx(K(p["dH2_kJmol"], p["dS2_JmolK"]) * (s["B"] / 1e5) ** 1.5, rel=1e-9)
        assert (s["X"] / 1e5) ** 2 == pytest.approx(K(p["dH_diss_kJmol"], p["dS_diss_JmolK"]) * s["B"] / 1e5, rel=1e-9)
    for kw in (dict(), dict(diff_model="binary")):  # net iodine flux zero (closed ampoule), A flux = sum of carrier fluxes
        q = amp._core(p | kw)
        assert q["bal"] < 1e-9 and q["Jnet"] == pytest.approx(q["Nsp"]["C1"] + q["Nsp"]["C2"])
    b = amp._core(preset("WO2_HgBr2", diff_model="binary"))  # coproduct case: Br balance exact, Hg element residual reported not hidden
    assert b["bal"] < 1e-9


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_iodine_dissociation_matches_janaf_and_grows_with_T():
    from core import props
    p = D()
    frac = []
    for T in (1100.0, 1500.0):
        s = amp._spec(p, T, 1.0 * 1e5)
        Kd = np.exp(-(153.874e3 - T * 105.796) / (R * T))  # JANAF 1000 K constants
        assert (s["X"] / 1e5) ** 2 == pytest.approx(Kd * s["B"] / 1e5, rel=1e-9)
        frac.append(s["X"] / (2 * s["B"] + s["X"] + 2 * s["C1"]))
    assert frac[1] > 5 * frac[0] and frac[1] > 0.3  # atoms dominate at 1500 K / 1 bar I2-equivalent
    assert amp._spec(D(dissociation="off"), 1500.0, 1e5)["X"] == 0.0


# Published: Schmidt, Binnewies, Glaum, Schmidt, "Chemical Vapor Transport Reactions - Methods, Materials, Modeling", InTech 2013,
# DOI 10.5772/55547, Fig. 13 (experimental, WO2 + HgX2, 1 g charge consumed) read off the graph (+-10%), text: HgBr2 800>720 "above 30 mg/h",
# HgI2 980>900 "up to 15 mg/h". Ampoule size/agent amount are NOT given for these runs: chapter-typical 15 cm x 15 mm, agent 1 bar at Tmean.
PUB = [("HgBr2", 800, 720, 28.0), ("HgI2", 980, 900, 14.7), ("HgBr2", 960, 880, 6.3), ("HgCl2", 720, 640, 2.3), ("HgI2", 840, 760, 1.3)]


def _anchor(**kw):
    return [(a, s, k, pub, amp.solve(preset(f"WO2_{a}", T_source_C=s, T_sink_C=k, **kw))["mass_rate_mg_h"]) for a, s, k, pub in PUB]


@pytest.mark.vessel("ampoule")
@pytest.mark.check("known_answer")
def test_published_wo2_hgx2_rates():
    res = _anchor()
    err = [m / pub for *_, pub, m in res]
    msg = "; ".join(f"{a} {s}>{k}: model {m:.1f} vs pub {pub:.1f} mg/h (x{m / pub:.1f})" for a, s, k, pub, m in res)
    print("\nANCHOR (not tuned):", msg)
    assert all(e > 0 for e in err)  # transport to the cold end, right sign
    assert max(max(e, 1 / e) for e in err) < 50  # regression guard on the REPORTED error (2-40x over-prediction), not a claim of agreement
    m = {(a, s): m for a, s, k, pub, m in res}
    assert m[("HgBr2", 800)] > m[("HgBr2", 960)] and m[("HgI2", 980)] > m[("HgI2", 840)]  # hotter-pair ordering within an agent
    assert m[("HgBr2", 800)] > m[("HgI2", 980)]  # agent ordering seen in Fig. 13 (Br best)
    # preset dH/dS reproduce the chapter's own dG(1000 K) (eqs. 33-35): HgBr2 +20.0, HgI2 +70.4, HgCl2 -56.4 kJ/mol
    for a, dG in (("HgBr2", 20.0), ("HgI2", 70.4), ("HgCl2", -56.4)):
        q = preset(f"WO2_{a}")
        assert q["dH_kJmol"] - 1000 * q["dS_JmolK"] / 1e3 == pytest.approx(dG, abs=0.15)


@pytest.mark.vessel("ampoule")
@pytest.mark.check("known_answer")
def test_tilt_trend_matches_geSe_geI4_qualitative():
    # Wiedemeier et al. (GeSe-GeI4, J. Cryst. Growth 1981/82; IAEA record): transport highest vertical destabilising, lowest stabilising.
    r = [amp.solve(D(tilt_deg=t))["transport_rate_mmol_h"] for t in (-90, -45, 0, 45, 90)]
    assert r[0] <= r[1] <= r[2] < r[3] <= r[4]
    assert r[4] > 3 * r[2] and r[0] == pytest.approx(amp.solve(D(tilt_deg=-90, conv_model="placeholder"))["transport_rate_mmol_h"], rel=0.2)


@pytest.mark.vessel("ampoule")
@pytest.mark.check("analytic_limit")
def test_profile_growth_rate_and_validity_flag_and_speed():
    lin, two = amp._core(D(T_profile="linear")), amp._core(D(T_profile="two_zone", zone_frac=0.25))
    assert two["Leff"] != pytest.approx(lin["Leff"], rel=1e-5) and two["J"] != lin["J"]
    assert amp._core(D(T_profile="two_zone", zone_frac=0.0))["Leff"] == pytest.approx(lin["Leff"], rel=2e-2)
    s = amp.solve(D(crystal_density_gcm3=7.0, sink_area_frac=2.0))
    area = np.pi * 0.0075**2
    assert s["growth_rate_mm_day"] * 1e-3 / 86400 * 7.0e6 * area * 2.0 / 100.0 == pytest.approx(s["transport_rate_mmol_h"] / 3.6e6, rel=1e-9)
    assert amp.solve(D(D_mm=60, L_cm=10))["convection_in_range"] == 0.0 and amp.solve(D(D_mm=40))["convection_in_range"] == 1.0 and amp.solve(D(D_mm=4, L_cm=30))["convection_in_range"] == 1.0  # scan: L=15 cm, A 0.067-0.4, Ra<=1.64e6
    t = time.perf_counter(); amp.solve(D()); assert time.perf_counter() - t < 0.05


SCAN = pathlib.Path(__file__).resolve().parents[1] / "docs" / "ampoule_convection_scan.json"


@pytest.mark.vessel("ampoule")
@pytest.mark.check("known_answer")
def test_calibrated_convection_vs_openfoam_scan():
    """Fit (conv_c, conv_fmax, conv_n) used ONLY the tilt-0 diameter scan; the rest is held out. Laminar CFD, square duct for tilt, mesh sensitivity 4-16%."""
    d = json.loads(SCAN.read_text())
    f = lambda **kw: amp._core(D(**kw))["f"]
    train = [(r["f_cfd_fine"], f(D_mm=r["D_mm"])) for r in d["vs_diameter_tilt0"]]
    assert all(abs(m / c - 1) < 0.05 for c, m in train)  # training error (5 pts, 3 params: weak evidence)
    held = {t["tilt_deg"]: (t["f_cfd_fine"], f(D_mm=40, tilt_deg=t["tilt_deg"])) for t in d["vs_tilt_D40"]}
    print("\nHELD-OUT tilt (CFD fine, T1):", {k: (round(a, 2), round(b, 2)) for k, (a, b) in held.items()})
    assert abs(held[30.0][1] / held[30.0][0] - 1) < 0.15 and abs(held[-90.0][1] - 1) < 1e-9
    assert all(abs(m / c - 1) < 0.5 for c, m in held.values())  # regression guard: reported errors up to 46% at tilt 60/90/-60 (unsteady, 16% mesh)
    for r in d["presets"]:  # held-out presets: weak convection (CFD 1.05-1.36), T1 within 25%
        q = preset(r["preset"])
        assert abs(amp._core(q)["f"] / r["f_cfd_fine"] - 1) < 0.25
    assert amp.solve(D(D_mm=60))["convection_enhancement"] < 12  # saturates (uncalibrated model gave 4850)
    assert amp.solve(D(D_mm=40, conv_model="buoyancy"))["convection_enhancement"] > 100  # old model still reachable


def test_stable_tilt_not_zeroed_near_horizontal():
    # regression: the stratification cutoff used an L-based Ra and zeroed the lateral counterflow at tilt -0.4 deg (CFD: f ~ same as +0.4)
    f = lambda t: amp.solve(D(D_mm=43, L_cm=15, T_source_C=900, tilt_deg=t))["convection_enhancement"]
    assert f(-0.4) > 0.5 * f(0.4) > 1.5
