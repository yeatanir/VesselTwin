"""CVD tube physics added Oct 18: every switch has a limit/isolation test; mass balance is checked against closed forms and an
independent flux integral (not the march's own bookkeeping); mesh convergence of the 1D march; sourced-constant sanity checks."""
import math, time
import numpy as np, pytest
from core import params as P
import vessels.cvd_tube as tube
from vessels.cvd_tube import thermo, wulff as w

IN = 0.0254


def D(**kw): return P.defaults(w.DEFS) | kw


def state(p, n=400):
    x, T, o, m = tube.march(p, n=n)
    g = {k: tube._at(x, o[k], m["xcen"]) for k in ("pM", "pS", "Tg")}
    Ts = tube._at(x, m["Twe"], m["xcen"])  # saturation ratios from interpolated p and T (psat is steep in T)
    g["ss"], g["ssg"] = g["pM"] / float(tube.psat_MoO3(p, Ts)), g["pM"] / float(tube.psat_MoO3(p, g["Tg"]))
    return g, (x, T, o, m)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_buoyancy_off_recovers_forced_convection():
    a, b = tube.solve(D(buoyancy="off")), tube.solve(D(buoyancy="flag"))
    assert all(a[k] == pytest.approx(b[k]) for k in ("species.MoO3_g.p_Pa", "supersaturation_MoO3", "ratio_Mo_S"))  # flag never changes the answer
    assert b["Ri_buoyancy"] > 1  # default 1 in tube at ~3 sccm-cm/s is buoyancy-competing (Gr/Re^2 >> 1)
    # enhance with an unreachable threshold = forced convection; with a low threshold wall uptake rises -> less Mo left in the gas
    e0 = tube.solve(D(buoyancy="enhance", Ri_c=1e9))
    assert e0["species.MoO3_g.p_Pa"] == pytest.approx(b["species.MoO3_g.p_Pa"])
    e1 = tube.solve(D(buoyancy="enhance", Ri_c=0.01, buoy_exp=0.5))
    assert e1["species.MoO3_g.p_Pa"] < b["species.MoO3_g.p_Pa"]
    # Gr ~ d^3: a narrow tube is forced-convection dominated, a wide one is not
    assert tube.solve(D(tube_id_in=0.3))["Ri_buoyancy"] < tube.solve(D(tube_id_in=2.0))["Ri_buoyancy"]


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_gas_temperature_lag_limits():
    on, off = D(gas_T_lag="on"), D(gas_T_lag="off")
    s_on, _ = state(on)
    s_off, _ = state(off)
    x, T, o, m = tube.march(off)
    assert np.allclose(o["Tg"], T)  # off: gas = wall
    assert abs(s_on["Tg"] - s_off["Tg"]) > 3  # ramp-down: gas still hot at the substrate
    lag = lambda **k: abs(state(D(**k))[0]["Tg"] - s_off["Tg"])
    assert lag(Nu=10.0) < lag(Nu=1.0)  # better heat transfer -> less lag
    assert lag(flow_sccm=5) < 0.3 * lag(flow_sccm=100)  # slow flow -> gas follows the wall (Graetz limit)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_stefan_factor_limits():
    assert tube._stefan(1e-7, 1e-6) == pytest.approx(1.0, abs=1e-5)
    assert tube._stefan(0.0, 0.5) == pytest.approx(math.log(2) / 0.5)  # film theory, evaporation into pure carrier
    assert tube._stefan(0.5, 0.5) == pytest.approx(2.0)  # limit y_b -> y_w : 1/(1-y)
    lo = dict(T_boat_Mo_C=650)  # dilute MoO3: correction ~ 0
    a, b = tube.solve(D(stefan="on", **lo)), tube.solve(D(stefan="off", **lo))
    assert a["species.MoO3_g.p_Pa"] == pytest.approx(b["species.MoO3_g.p_Pa"], rel=2e-3)
    hot = dict(T_boat_S_C=380)  # S vapour mole fraction ~ 0.3: evaporation is Stefan-enhanced
    n_on, n_off = tube.march(D(stefan="on", **hot))[3]["NS_in"], tube.march(D(stefan="off", **hot))[3]["NS_in"]
    assert n_on > 1.1 * n_off


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_growth_size_linear_in_time_and_hexagon_area():
    v = D()
    g1, g2 = w.growth(v | {"duration_min": 5.0}, 2e-3, 1e-3), w.growth(v | {"duration_min": 10.0}, 2e-3, 1e-3)
    assert g2["size_um"] == pytest.approx(2 * g1["size_um"]) and g2["apothem_Mo_um"] == pytest.approx(2 * g1["apothem_Mo_um"])
    h = w.growth(v, 1e-3, 1e-3)  # regular hexagon, apothem a: area 2 sqrt(3) a^2
    a = 1e-3 * v["duration_min"] * 60
    assert h["size_um"] == pytest.approx(math.sqrt(4 * 2 * math.sqrt(3) * a * a / math.pi))
    t = w.growth(v, 1e-6, 1e-3)  # v_Mo << v_S : Mo-edge triangle of apothem a: area 3 sqrt(3) a^2
    a = 1e-6 * v["duration_min"] * 60
    assert t["size_um"] == pytest.approx(math.sqrt(4 * 3 * math.sqrt(3) * a * a / math.pi)) and t["edge_len_S_um"] == pytest.approx(0, abs=1e-9)
    s = w.shape_at(v, (0.1, 50.0), 900.0)
    assert s["size_um"] > 0 and "coalesced" in s
    assert w.shape_at(v | {"N_nuc_cm2": 1e8}, (0.1, 50.0), 900.0)["L_coalesce_um"] < s["L_coalesce_um"]


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("mass_balance")
def test_isothermal_deposition_matches_closed_form():
    """Hot MoO3 boat feeding a uniformly cooler tube: N(x) = Nsat + (N0 - Nsat) exp(-km pi d L / Q) (independent of the march)."""
    p = D(T_furnace_C=700.0, L_hot_cm=200.0, ramp_cm=0.5, T_boat_Mo_C=1000.0, T_boat_S_C=150.0, x_S_boat_cm=2.0,
          substrate_width_cm=0.0, stefan="off", gas_T_lag="off", buoyancy="off", **{"MoO3.n_oligomer": 1})
    x, T, o, m = tube.march(p, n=1600)
    Tw, d, Pt = 973.15, IN, p["pressure_Pa"]
    i0 = int(np.searchsorted(x, 0.5))
    Nc = m["flow"]
    N0, Nsat = m["NM_in"], float(tube.psat_MoO3(p, Tw)) * (Nc + 0) / Pt
    km = p["Sh"] * float(thermo.fuller_D("Ar", "MoO3", Tw, Pt, 1)) / d
    Q = Nc * 8.314462618 * Tw / Pt
    L = x[-1] - x[i0]
    pred = Nsat + (N0 - Nsat) * math.exp(-km * math.pi * d * L / Q)
    assert N0 > Nsat * 1.5  # actually supersaturated, so the test is not trivial
    assert m["NM_out"] == pytest.approx(pred, rel=0.03)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("mass_balance")
def test_deposited_moles_match_independent_flux_integral():
    """Integrate the reported wall flux over the wall area (profile arrays, trapezoid) and compare with the march's deposit tally."""
    p = D(substrate_width_cm=0.0)
    x, T, o, m = tube.march(p, n=3200)
    integral = np.trapezoid(o["flux"] * np.pi * m["d"], x)
    assert integral == pytest.approx(m["dep"]["M"], rel=0.04)
    assert abs(m["NM_in"] - m["NM_out"] - m["dep"]["M"]) < 1e-6 * m["NM_in"]  # and the tally itself closes


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("mesh_convergence")
def test_march_mesh_convergence():
    ref = state(D(), n=1600)[0]
    for n in (400, 800):
        s = state(D(), n=n)[0]
        for k in ("pM", "pS", "ss", "ssg"):
            assert abs(s[k] / ref[k] - 1) < 0.02, (n, k, s[k], ref[k])
    s4, s8 = state(D(), n=400)[0], state(D(), n=800)[0]
    assert abs(s4["pM"] / s8["pM"] - 1) < 0.02


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_sourced_constants_sanity():
    p = D()
    assert float(tube.psat_MoO3(p, 1000.0)) == pytest.approx(53.3, rel=1e-3)  # Smolik et al. 2000 HSC fit (doi:10.2172/752007), ~0.40 Torr
    T = 973.0  # shape check against the HSC fit itself and Berkowitz 1957 (29 Pa, as reprinted by Fletcher 1966): same decade
    assert 10 < float(tube.psat_MoO3(p | {"MoO3.P_ref_Pa": 53.3}, T)) < 40
    old = D(**{"MoO3.psat_model": "simnad_ocr", "MoO3.P_ref_Pa": 1.2})
    assert float(tube.psat_MoO3(old, 1000.0)) == pytest.approx(1.2, rel=1e-3)  # earlier OCR'd fit stays reachable (likely misread: ~30x low)
    assert float(tube.psat_S(p, 717.8)) == pytest.approx(101325, rel=0.02)  # normal boiling point 444.6 C
    assert float(thermo.s2_fraction(1.0, 800.0, 13332.0)) > 0.8  # Meyer: >80 % S2 at 800 K, 100 Torr (as quoted in a search summary)
    assert float(thermo.s2_fraction(1.0, 453.0, 100.0)) < 0.01  # boat vapour is S8
    assert thermo._shomate(thermo._S2, 298.15)[1] == pytest.approx(228.19, abs=0.05)  # NIST S0(S2) and S0(S8) reproduce
    assert thermo._shomate(thermo._S8, 298.15)[1] == pytest.approx(430.23, abs=0.05)
    leg = D(thermo_basis="legacy_synthetic", **{"MoO3.P_ref_Pa": 30.0})
    assert float(tube.psat_MoO3(leg, 1000.0)) == pytest.approx(30.0)  # old placeholder still reachable for the CFD comparison
    assert float(thermo.fuller_D("Ar", "MoO3", 900, 1e5, 3)) < float(thermo.fuller_D("Ar", "MoO3", 900, 1e5, 1))  # trimer diffuses slower


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_substrate_geometry_temperature_carrier_and_pressure():
    base = tube.solve(D())
    assert tube.solve(D(T_substrate_offset_K=50.0))["supersaturation_MoO3"] < base["supersaturation_MoO3"]  # hotter deposit, higher p_sat
    assert tube.solve(D(T_substrate_offset_K=50.0))["T_K"] == pytest.approx(base["T_K"] + 50.0)
    assert tube.solve(D(x_substrate_cm=8.0))["T_K"] > base["T_K"]  # nearer the furnace plateau
    a = tube.solve(D(substrate_length_cm=1.0))["MoO3_to_substrate_frac"]
    assert tube.solve(D(substrate_length_cm=4.0))["MoO3_to_substrate_frac"] > a
    assert tube.solve(D(substrate_width_cm=0.0))["MoO3_to_substrate_frac"] == 0.0
    h2 = tube.solve(D(carrier="H2"))
    assert np.isfinite(h2["ratio_Mo_S"]) and thermo.fuller_D("H2", "MoO3", 900, 1e5) > thermo.fuller_D("Ar", "MoO3", 900, 1e5)
    assert thermo.fuller_D("Ar", "S2", 900, 2e5) == pytest.approx(thermo.fuller_D("Ar", "S2", 900, 1e5) / 2)  # D ~ 1/P
    lowP = tube.solve(D(pressure_Pa=2000.0))
    assert lowP["balance_err"] < 5e-3 and np.isfinite(lowP["supersaturation_MoO3"])


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("speed")
def test_solve_time_budget():
    p = D()
    tube.solve(p)
    t = time.perf_counter()
    for _ in range(10): tube.solve(p)
    assert (time.perf_counter() - t) / 10 < 0.05
