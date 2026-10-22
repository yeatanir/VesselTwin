"""Track A: analytic-limit tests for inventory, gap, nucleation proxies and the Rosen DFT Mo-edge data."""
import numpy as np
from core import params as P
from vessels.cvd_tube import wulff, growth, rosen_sbinding as R


def V(**kw): return P.validate(wulff.DEFS, kw)


def test_infinite_inventory_recovers_old_time():
    st = growth.state(V())
    assert st["t_eff"] == V()["duration_min"] * 60 and st["t_dep_Mo"] > 1e6


def test_depletion_time_linear_in_mass_and_caps_supply():
    a, b = growth.state(V(m_MoO3_mg=10)), growth.state(V(m_MoO3_mg=20))
    assert abs(b["t_dep_Mo"] / a["t_dep_Mo"] - 2) < 1e-9
    s = growth.state(V(m_MoO3_mg=1e-3))  # tiny charge: supply stops long before t_growth
    assert s["t_eff"] == s["t_dep_Mo"] < 600


def test_gap_limits():
    v = V(); Tb, Ts = 1073.15, 900.0
    big = [growth.gap_flux(v, Tb, Ts, g) for g in (1.0, 2.0)]  # metres: diffusion-limited, F ~ 1/gap
    assert abs(big[1] / big[0] - 0.5) < 1e-3
    dp = float(growth.thermo.psat_MoO3(v, Tb) - growth.thermo.psat_MoO3(v, Ts))
    assert abs(growth.gap_flux(v, Tb, Ts, 0.0) / (growth.k_hk(v, Tb) * dp) - 1) < 1e-9  # gap -> 0: Hertz-Knudsen limit


def test_nucleation_exponent_is_i_over_i_plus_2():
    st = growth.state(V()); st2 = dict(st, F=2 * st["F"])
    for i in (1, 2, 3):
        d = growth.observables(st2, i)["nucleation"] - growth.observables(st, i)["nucleation"]
        assert abs(d - i / (i + 2) * np.log(2)) < 1e-12
    o, o2 = growth.observables(st, 1), growth.observables(st2, 1)
    assert abs((o2["domain"] - o["domain"]) / (o2["nucleation"] - o["nucleation"]) + 0.5) < 1e-12


def test_rosen_table2_and_thermo_anchor():
    assert np.allclose(R.data()["dE_S_eV_vs_H2S_H2"], [-2.91, -2.37, -0.93, -0.21, -0.08, -0.36], atol=0.005)  # printed Table 2, theta_H = 0
    assert 0.74 < R.dG_r(298.15) < 0.78  # H2S -> H2 + 1/2 S2: dH 0.88 eV (NIST dfH 84.8 kJ/mol), T dS 0.12 eV
    p = wulff.p_eq(V(eq_model="dft_rosen"), "Mo", np.array([1000.0, 1073.15]))
    assert np.all(np.isfinite(p)) and p[1] > p[0] > 0


def test_call_rule_known_answers():
    from bench.track_a_score import call_from
    up = np.tile(np.linspace(0, 1, 5), (20, 1))
    assert call_from([up])[0] == "increase" and call_from([-up])[0] == "decrease"
    assert call_from([up * 0.001])[0] == "no_change"
    hump = np.tile([0, 1, 2, 1, 0.0], (20, 1))
    assert call_from([hump])[0] == "non_monotonic"
    mixed = np.vstack([up, -up])  # band crosses zero
    assert call_from([mixed])[0] == "uncertain"
