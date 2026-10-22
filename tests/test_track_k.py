"""Track K: substrate-flux response to boat supply (intended wall-uptake saturation, not a defect). See docs/prereg/track-k.md."""
import numpy as np
from core import api
from vessels.cvd_tube import march

L = {"MoO3.psat_model": "smolik_liquid_cc"}


def _solve(**kw):
    from vessels.cvd_tube import solve
    p = api.defaults("cvd_tube"); p.update(L); p.update(kw)
    return solve(p)


def test_no_condensation_returns_supply():  # NTU -> 0 limit
    p = api.defaults("cvd_tube"); p.update(L)
    _, _, _, m = march(p, condense=False)
    assert abs(m["NM_out"] - m["NM_in"]) < 1e-12 * m["NM_in"]


def test_mass_balance():
    assert _solve()["balance_err"] < 1e-9


def test_flux_nondecreasing_in_boat_T():
    F = [_solve(T_boat_Mo_C=t)["flux_MoO3_mol_m2_s"] for t in range(700, 901, 25)]
    assert all(b >= a * (1 - 1e-3) for a, b in zip(F, F[1:]))


def test_flux_responds_near_boat():  # little wall NTU between boat and substrate: >1 % per 25 C
    F = [_solve(T_boat_Mo_C=t, x_substrate_cm=1.0)["flux_MoO3_mol_m2_s"] for t in range(775, 876, 25)]
    assert all(b > a * 1.01 for a, b in zip(F, F[1:]))


def test_documented_saturation_far_from_boat():  # wall NTU ~ 10: gas at substrate set by the falling wall saturation, not the boat
    a, b = (_solve(T_boat_Mo_C=t)["flux_MoO3_mol_m2_s"] for t in (800, 850))
    assert abs(b / a - 1) < 0.01
    assert _solve(T_boat_Mo_C=850)["MoO3_supply_mol_s"] > 2 * _solve(T_boat_Mo_C=800)["MoO3_supply_mol_s"]
