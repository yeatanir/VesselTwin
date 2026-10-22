"""Track I: liquid-MoO3 branch and Momeni equilibrium edge model."""
import numpy as np
import pytest
from core import params as P
from vessels.cvd_tube import DEFS, momeni_edges as ME, thermo, wulff

V = P.defaults(DEFS)
LIQ = V | {"MoO3.psat_model": "smolik_liquid_cc"}
psat = lambda v, T: float(thermo.psat_MoO3(v, T))


def test_liquid_continuous_at_melting_and_solid_unchanged():
    assert psat(LIQ, 1068.0) == pytest.approx(psat(V, 1068.0), rel=1e-9)
    assert psat(LIQ, 1068.0 + 1e-6) == pytest.approx(psat(LIQ, 1068.0), rel=1e-3)
    for T in (800, 1000, 1067.9):
        assert psat(LIQ, T) == psat(V, T)


def test_liquid_pinned_to_1atm_at_Tb_and_monotonic():
    assert psat(LIQ, LIQ["MoO3.Tb_K"]) == pytest.approx(101325.0, rel=1e-9)
    Ts = np.linspace(1000, 1428, 200)
    p = [psat(LIQ, T) for T in Ts]
    assert all(b > a for a, b in zip(p, p[1:]))
    assert psat(V, 1300.0) == psat(V, 1068.0)  # old clamp still the default


def test_liquid_below_unphysical_solid_extrapolation():
    sol = 133.322 * 10 ** (8599.81 / 1300 - 186.495 + 63.1654 * np.log10(1300) - 0.0078447 * 1300 - 4154834 / 1300**2)
    assert sol > 1e6 > psat(LIQ, 1300.0)  # unclamped solid fit gives ~19 atm


def test_bfac_scaling_and_sigma_scoped():
    assert psat(LIQ | {"MoO3.liq_Bfac": 1.5}, 1300) > psat(LIQ, 1300)
    d = next(x for x in DEFS if x.name == "MoO3.liq_Bfac")
    with thermo.with_liq_sigma(LIQ):
        assert d.sigma == 0.384
    assert d.sigma == 0.0


def test_momeni_si_equations_as_printed():
    assert ME.edge_energies(0.0) == (0.75, 1.03, 0.44, 0.2)
    assert ME.edge_energies(1.0)[1:] == pytest.approx((1.2484, 0.2359, -0.2286))
    assert ME.dmu_bridge(0.0, 1000.0)[0] == pytest.approx(0.8 + 12 * ME.OMEGA * ME.C_EQ)


def test_wulff_known_answers():
    # regular hexagon limit: equal ZZ energies, AC far out -> only ZZ edges, equal lengths, s = 0
    h = {60.0 * k: 1.0 for k in range(6)} | {60.0 * k + 30: 5.0 for k in range(6)}
    L = ME._lengths(h)
    assert L[:6] == pytest.approx(2 / np.sqrt(3)) and L[6:] == pytest.approx(0, abs=1e-9)
    # v2 vs the printed text of Cao et al. 2015 p.4296: AC edges (dodecagon) at -1.32..-1.1, hexagon ~-1.0..-0.9, triangle beyond -0.04
    assert ME.wulff_edges(-1.2)["L_AC"] > 0.5 and ME.wulff_edges(-1.0)["L_AC"] < 1e-6
    assert ME.shape_from_dmu(-0.95)[0] == "hexagon" and ME.shape_from_dmu(-0.04)[0] == "triangle_Mo" and ME.shape_from_dmu(0.0)[1] == 1.0
    assert ME.shape_from_dmu(-0.5, v2=False)[0] == "triangle_S"  # first registered (wrong-orientation) version kept for the record


def test_edge_model_option_and_default_unchanged():
    assert next(d for d in wulff.WDEFS if d.name == "edge_model").default == "kinetic"
    r = wulff.shape_at(V | {"edge_model": "momeni_eq"}, (0.1, 50.0), 1073.15)
    assert wulff.shape_at(V | {"edge_model": "momeni_eq_v1"}, (0.1, 50.0), 1073.15)["dmu_S_eV"] == r["dmu_S_eV"]
    assert r["shape"] in ("hexagon", "truncated_triangle", "triangle_S", "triangle_Mo") and "dmu_S_eV" in r
    assert r["dmu_S_eV"] == pytest.approx(-1.1475, abs=1e-3)
