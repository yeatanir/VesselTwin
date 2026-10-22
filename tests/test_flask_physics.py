import time
import numpy as np, pytest
from core import params as P
import vessels.flask as fl
from vessels.flask import solvents, vd


def D(**kw): return P.defaults(fl.DEFS) | kw


COMMENGE = D(**{"vd.c_H_M": 0.01, "vd.c_B_M": 0.09, "vd.c_I_M": 0.03, "vd.c_IO3_M": 0.006})


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_vd_constants_and_ystar():
    assert vd.K_I3(298.15) == pytest.approx(10 ** (555 / 298.15 + 7.355 - 2.575 * np.log10(298.15)))
    assert 650 < vd.K_I3(298.15) < 760  # I2 + I- <-> I3-: ~700 M^-1 at 25 C (Palmer et al 1984)
    k = lambda I: vd.k2_dushman(I)
    assert k(0.166 + 1e-9) / k(0.166) == pytest.approx(1, rel=0.05)  # the two Guichardon branches meet
    assert k(0.01) > k(0.1) > k(0.5)  # k2 falls with ionic strength
    assert vd.Y_ST(COMMENGE) == pytest.approx(0.036 / 0.126)  # 0.286 for 0.006 M iodate, 0.09 M borate


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_vd_limits_perfect_and_total_segregation():
    xs = lambda t, p=COMMENGE: vd.segregation_index(p, t)[0]
    assert xs(1e-7) < 1e-4  # E -> inf: ideal micromixing, Xs -> 0
    ts = [1e-3, 1e-1, 1e1, 1e3, 1e6, 1e11]
    v = [xs(t) for t in ts]
    assert all(a < b for a, b in zip(v, v[1:]))
    assert v[-1] > 0.95  # E -> 0: total segregation, Xs -> 1 (slowly: rate ~ [H+]^2 as acid is used up)
    assert all(vd.segregation_index(COMMENGE, t)[1] <= 1 for t in ts)  # Y = 2 n_I2 / n_H+ cannot exceed 1
    # published linearity t_m ~ a Xs at small Xs (Commenge & Falk 2011; SI of arXiv:1909.11868 Eq 13)
    assert np.log(xs(1e-2) / xs(1e-3)) / np.log(10) == pytest.approx(1.0, abs=0.05)


@pytest.mark.vessel("flask")
@pytest.mark.check("mass_balance")
def test_incorporation_conserves_atoms():
    for scheme, C0 in (("consecutive", 0.0), ("parallel", 0.07)):
        A0, B0 = 0.1, 1.0
        X, y = vd.incorporation(50.0, 2.0, A0, B0, 3.0, scheme=scheme, C0=C0, return_y=True)
        V, A, C, B, R, S = y[:6]
        Vend = 1 + B0 / (A0 + C0)
        assert V == pytest.approx(Vend)
        assert A0 * (Vend - 1) == pytest.approx(A + R + (S if scheme == "consecutive" else 0), rel=1e-5)  # A-atoms
        if scheme == "parallel":
            assert C0 * (Vend - 1) == pytest.approx(C + S, rel=1e-5)
            assert B0 == pytest.approx(B + R + S, rel=1e-5)
        else:
            assert B0 == pytest.approx(B + R + 2 * S, rel=1e-5)  # B-atoms: R carries one B, S two
        assert min(A, B, C, R, S) >= -1e-9 and 0 <= X <= 1


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_selectivity_limits():
    dil = 1 + 50 * 1.0 / 0.2  # A and C in 50-fold excess so they stay constant
    # parallel, ideal micromixing: B splits as k1 A : k2 C
    X = vd.incorporation(10.0, 5.0, 0.1, 1.0, 1e7, scheme="parallel", C0=0.1, dilution=dil)
    assert X == pytest.approx(5.0 * 0.1 / (10.0 * 0.1 + 5.0 * 0.1), rel=0.04)
    # consecutive: loss of selectivity grows as mixing slows and vanishes for E -> inf
    xs = [vd.incorporation(1e3, 1e1, 0.1, 1.0, E, dilution=1 + 50 * 10.0) for E in (1e6, 1e2, 1e0, 1e-2)]
    assert xs[0] < 0.02 and all(a < b for a, b in zip(xs, xs[1:]))
    assert vd.incorporation(1e3, 1e-9, 0.1, 1.0, 1e-2, dilution=1 + 50 * 10.0) < 1e-6  # no side reaction -> no side product


@pytest.mark.vessel("flask")
@pytest.mark.check("known_answer")
def test_solvent_correlations_vs_tables():
    for s, (rho, mu) in fl.SOLVENTS.items():  # 25 C CRC-type table
        pr = solvents.props(s, 25.0)
        assert pr["mu"] == pytest.approx(mu, rel=0.08) and pr["rho"] == pytest.approx(rho, rel=0.01), s
    for T, mu in ((0, 1.7921), (50, 0.5494), (100, 0.2838)):  # Lide 2004, water
        assert solvents.props("water", T)["mu"] * 1e3 == pytest.approx(mu, rel=0.03)
    assert solvents.props("water", 4)["rho"] == pytest.approx(999.97, rel=2e-3)
    assert solvents.props("ethanol", 0)["mu"] * 1e3 == pytest.approx(1.720, rel=0.02)  # CHERIC
    assert solvents.props("toluene", -20)["mu"] * 1e3 == pytest.approx(1.0787, rel=0.02)
    assert solvents.props("DMSO", 80)["mu"] * 1e3 == pytest.approx(0.85, rel=0.02)  # ThermoML je800138b
    assert solvents.props("water", 90)["in_range"] == 1 and solvents.props("DMSO", 0)["in_range"] == 0
    for s in fl.SOLVENTS:
        assert solvents.props(s, 60)["mu"] < solvents.props(s, 30)["mu"], s


@pytest.mark.vessel("flask")
def test_temperature_changes_mixing():
    assert fl._mix(D(T_C=60.0))["t_micro"] < fl._mix(D(T_C=25.0))["t_micro"]  # hot water is thinner


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_volume_scaling_const_rpm_vs_const_eps():
    p = D(volume_mL=250.0, bar_mm=35.0, stir_rpm=400.0)
    a, b = fl.scale_up(p, 1000.0, "rpm"), fl.scale_up(p, 1000.0, "eps")
    e0 = fl._mix(p)["eps"]
    assert b["eps"] == pytest.approx(e0, rel=1e-6) and b["stir_rpm"] < 400.0  # same W/kg needs a slower, bigger bar
    assert a["eps"] > e0 * 1.5 and a["t_micro"] < fl._mix(p)["t_micro"]  # same rpm, bigger bar: more W/kg
    assert a["A_over_V"] / fl.scale_up(p, 250.0, "rpm")["A_over_V"] == pytest.approx(4 ** (-1 / 3), rel=1e-6)  # wall area per volume
    assert b["theta95"] > fl._mix(p)["theta95"]  # at constant eps the bulk blend time still grows with scale


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_hotspot_hand_calculation():
    # A0 = B0 = 1 M, dH = -100 kJ/mol, instantaneous reaction: product 0.5 M in the adiabatic mixed plume
    p = D(**{"C0_M": 1.0, "feed.c_M": 1.0, "heat.dH_kJ_mol": -100.0, "k2_M_s": 1e12})
    hand = 100e3 * 500.0 / (996.6 * 4178.7)  # J/mol * mol/m3 / (rho cp) = 12.0 K
    s = fl.solve(p)
    assert s["dT_plume_K"] == pytest.approx(hand, rel=5e-3) and s["hotspot"] == 1.0
    assert fl.solve(p | {"heat.dH_kJ_mol": -1.0})["hotspot"] == 0.0
    assert fl.solve(p | {"heat.dH_kJ_mol": +50.0})["dT_plume_K"] == 0.0  # endothermic: no rise
    # bulk cooling: heat per volume fixed, wall area per volume falls with scale (Noel: poor mixing/cooling at 250 mL - 1 L)
    r = lambda V: fl.solve(p | {"volume_mL": V, "bar_mm": 30.0})["cooling_ratio"]
    assert r(1000.0) / r(250.0) == pytest.approx(4 ** (1 / 3), rel=1e-6)


@pytest.mark.vessel("flask")
@pytest.mark.check("known_answer")
def test_validity_flags_and_bar_fit():
    v = lambda N: fl._flags(D(stir_rpm=N), fl._mix(D(stir_rpm=N)))["vortex"]
    assert v(800) / v(400) == pytest.approx(4.0, rel=1e-9)  # solid-body paraboloid depth ~ N^2
    assert fl.solve(D(stir_rpm=2000))["valid"] == 0.0 and fl.solve(D())["valid"] == 1.0
    with pytest.raises(ValueError):
        fl.solve(D(volume_mL=10, bar_mm=60))


@pytest.mark.vessel("flask")
@pytest.mark.check("analytic_limit")
def test_verdict_critical_feed_and_knob():
    p = D()
    q, why = fl.critical_feed(p)
    assert q > 0 and why in ("mesomixing", "macromixing")
    m = fl._mix(p | {"feed.time_s": fl._mix(p)["Vf"] / q})
    S = fl._sens(p | {"feed.time_s": m["Vf"] / q}, m)[0]
    assert S == pytest.approx(1.0, rel=2e-3)  # exactly at the critical addition rate
    fast = fl.solve(D(**{"feed.time_s": 1.0}))
    assert fast["mixing_sensitive"] == 1.0 and fast["sensitivity_margin"] < 1 and fast["knob_code"] in (1, 2, 3, 4)
    assert fl.solve(D(**{"feed.time_s": 3600.0}))["mixing_sensitive"] == 0.0
    assert fl.critical_feed(D(k2_M_s=1e9))[0] == 0.0  # micromixing-limited: sensitive at any rate
    assert "mL/min" in fl.verdict(p)["text"]


@pytest.mark.vessel("flask")
@pytest.mark.check("known_answer")
def test_published_trend_anchor_vd_vs_dissipation(capsys):
    """Published: Xs falls with specific power (Fournier 1996; Assirelli 2002; Yang et al. Adv Mater Phys Chem 2012, 2, 150) and rises
    with viscosity (Arian & Pauer J Flow Chem 2021, qualitatively). Yang's single-phase Rushton data, eps 0.5-3.5 W/kg, 1 M H+,
    sit in Xs ~ 0.26-0.34 (axis range read from the OCR text of Figs 5 and 7: low confidence; their buffer set was not retrievable,
    so the PMC9866573 set is used). Nothing is tuned; the error outside the band is printed and bounded loosely."""
    p = D(**{"vd.c_H_M": 1.0, "vd.c_B_M": 0.09, "vd.c_I_M": 0.03, "vd.c_IO3_M": 0.006})
    nu = fl._mix(p)["nu"]
    eps = np.array([0.5, 1.0, 2.0, 3.5])
    xs = np.array([vd.segregation_index(p, 17.3 * np.sqrt(nu / e))[0] for e in eps])
    assert np.all(np.diff(xs) < 0) and np.all((0 < xs) & (xs < 1))
    lo, hi = 0.26, 0.34
    err = np.where(xs > hi, xs / hi - 1, np.where(xs < lo, 1 - xs / lo, 0.0))
    with capsys.disabled():
        print(f"\nVD anchor: model Xs {xs.round(3)} vs published band [{lo}, {hi}]; relative excursion outside band {err.round(2)}")
    assert err.max() < 0.35
    # viscous medium: 100x viscosity -> 10x t_m -> higher Xs, same direction as sucrose-water data
    hi_visc = vd.segregation_index(p, 17.3 * np.sqrt(100 * nu / 1.0))[0]
    assert hi_visc > xs[1]
    # through the vessel: more stirring lowers Xs, thicker solvent raises it
    f = lambda **kw: fl.solve(D(**kw) | {"vd.c_H_M": 1.0})["Xs_villermaux_dushman"]
    assert f(stir_rpm=800) < f(stir_rpm=400) and f(mu_factor=50.0) > f()


@pytest.mark.vessel("flask")
def test_solve_time_budget():
    t = time.perf_counter()
    fl.solve(D())
    assert time.perf_counter() - t < 0.5  # nominal ~80 ms; loose for CI noise
