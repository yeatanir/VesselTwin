import numpy as np, pytest
from core import params as P
from vessels.cvd_tube import wulff as w

V = P.defaults(w.DEFS)
T, FLOOR = 1000.0, 1e-12


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
@pytest.mark.parametrize("e", ["Mo", "S"])
def test_detailed_balance_kink_term(e):
    # v index: rates returns (v_Mo, v_S); Mo edge fed by pS, S edge by pM
    peq = w.p_eq(V, e, T)
    big = 1e9
    feed = lambda p: (big, p) if e == "Mo" else (p, big)
    vel = lambda p: w.rates(V, *feed(p), T)[0 if e == "Mo" else 1]
    assert vel(peq) == pytest.approx(FLOOR)  # forward = reverse: no net growth
    assert vel(2 * peq) > 100 * FLOOR and vel(0.5 * peq) == pytest.approx(FLOOR)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("analytic_limit")
def test_equilibrium_pressure_limits():
    for e in ("Mo", "S"):
        k = f"E_kink_{e}.E_eV"
        assert w.p_eq(V | {k: 4.9}, e, T) < 1e-20 * w.p_eq(V, e, T) or w.p_eq(V | {k: 4.9}, e, T) < 1e-25  # tightly bound: ~0
        assert w.p_eq(V | {k: -4.9}, e, T) > 1e6  # unbound: far above any feed -> growth floor
        assert w.rates(V | {k: -4.9}, 1.0, 50.0, T)[0 if e == "Mo" else 1] == pytest.approx(FLOOR)
    # S reference: one kT of E_kink_S is exactly exp(1); Mo edge: 2 kT per kT of S binding (S2 -> 2 S)
    kT = w.KB * T
    assert w.p_eq(V | {"E_kink_S.E_eV": V["E_kink_S.E_eV"] + kT}, "S", T) == pytest.approx(w.p_eq(V, "S", T) / np.e)
    assert w.p_eq(V | {"E_kink_Mo.E_eV": V["E_kink_Mo.E_eV"] + kT}, "Mo", T) == pytest.approx(w.p_eq(V, "Mo", T) / np.e**2)


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_kink_closures_override():
    from atomistic import edges
    cl = edges.closures_kink()
    assert {c.name for c in cl} == {"E_kink_Mo", "E_kink_S"} and all(not c.synthetic and c.sigma["E_eV"] > 0.15 for c in cl)
    v2 = w.apply_wulff_closures(V, cl)
    assert v2["E_kink_Mo.E_eV"] == pytest.approx(cl[0].params["E_eV"]) and v2["E_kink_S.E_eV"] != V["E_kink_S.E_eV"]
    assert w.p_eq(v2, "Mo", T) != w.p_eq(V, "Mo", T)
    g = [c.model_copy(update={"name": "gamma_edge_Mo", "params": {"gamma_eV": 1.63}}) for c in cl[:1]]  # old names stay accepted
    assert w.apply_wulff_closures(V, g)["gamma_edge_Mo.gamma_eV"] == 1.63
    assert w.p_eq(w.apply_wulff_closures(V, g), "Mo", T) == w.p_eq(V, "Mo", T)  # ...but do not enter the kink term


@pytest.mark.vessel("cvd_tube")
@pytest.mark.check("known_answer")
def test_collapse_regression():
    mlip_gamma = V | {"gamma_edge_Mo.gamma_eV": 1.63, "gamma_edge_S.gamma_eV": 1.21}
    pM, pS, T1 = 0.1, 48.0, 970.0  # CVD feed quoted in docs/edge_energies.md
    old = w.rates(mlip_gamma | {"eq_model": "legacy_gamma"}, pM, pS, T1)
    assert old == [pytest.approx(FLOOR)] * 2  # both edges at the floor: r = 1, every point 'hexagon'
    assert w.shape_at(mlip_gamma | {"eq_model": "legacy_gamma"}, (pM, pS), T1)["shape"] == "hexagon"
    new = w.shape_at(mlip_gamma, (pM, pS), T1)  # gamma ignored by the kink term
    assert new["v_S_um_s"] > 1e-6 and new["r_vMo_vS"] != pytest.approx(1.0)
