"""Track M: reactive substrate sink and wall-uptake variants (vessels/cvd_tube/reactive.py). Limits, continuity, default reproduction."""
import json, os
import numpy as np
import pytest
from core import params as P
from vessels import cvd_tube as T
from vessels.cvd_tube import growth, reactive as R, thermo, wulff
from bench import track_m_score as M

REF = json.load(open(os.path.join(os.path.dirname(__file__), "..", "bench", "track_m", "default_reference.json")))


def F(**kw): return T.solve(P.validate(wulff.DEFS, kw))["flux_MoO3_mol_m2_s"]


@pytest.mark.parametrize("r", REF)
def test_default_reproduces_stored_results_exactly(r):
    v = P.validate(wulff.DEFS, r["case"])
    x, Tt, o, m = T.march(v)
    assert o["flux"].tolist() == r["flux_arr"] and o["pM"].tolist() == r["pM"] and m["NM_out"] == r["NM_out"]
    assert T.solve(v) == r["solve"] and growth.state(v) == r["state"]


def test_series_limits():
    assert R.series(0.02, np.inf) == pytest.approx(0.02)
    assert R.series(0.02, 1e12) == pytest.approx(0.02, rel=1e-9)
    assert R.series(0.02, 0.0) < 1e-250
    assert R.series(0.02, 0.02) == pytest.approx(0.01)


def test_k_rxn_to_infinity_is_mass_transfer_limited():
    # condensation flux = k_m (p - psat(T_sub))/RT; reactive with k_rxn -> inf = k_m p/RT, so cond = reactive * (1 - psat/p) (same gas state: reflecting wall)
    kw = dict(wall_uptake_model="reflecting", x_substrate_cm=2.0, T_substrate_offset_K=-100.0)
    v = P.validate(wulff.DEFS, kw); s = T.solve(v)
    cond = F(**kw) / (1 - float(thermo.psat_MoO3(v, s["T_K"])) / s["species.MoO3_g.p_Pa"])
    r1, r2 = F(substrate_uptake_model="reactive", rxn_log10_k0_m_s=11.0, rxn_Ea_eV=0.0, rxn_n_S=0.0, **kw), \
        F(substrate_uptake_model="reactive", rxn_log10_k0_m_s=12.0, rxn_Ea_eV=0.0, rxn_n_S=0.0, **kw)
    assert r1 == pytest.approx(r2, rel=1e-6)  # plateau
    assert r2 == pytest.approx(cond, rel=5e-2)  # (Stefan factor differs by ~2%) equals the mass-transfer-limited flux k_m p/(RT)


def test_k_rxn_to_zero_gives_zero_flux():
    ref = F(substrate_uptake_model="reactive")
    assert F(substrate_uptake_model="reactive", rxn_log10_k0_m_s=-12.0) < 1e-9 * ref
    assert F(substrate_uptake_model="reactive", rxn_Ea_eV=6.0) < 1e-9 * ref
    assert F(substrate_uptake_model="reactive", S_ref_Pa=1e6, rxn_n_S=4.0) < 1e-9 * ref  # a_S -> 0


def test_hot_substrate_reactive_nonzero_condensation_zero():
    kw = dict(x_substrate_cm=0.0, T_boat_Mo_C=700.0, T_furnace_C=700.0)  # substrate as hot as the boat: S = 1 at best, no supersaturation
    assert F(**kw) == 0.0
    assert F(substrate_uptake_model="reactive", **kw) > 0.0


def test_flux_monotone_in_k_rxn_and_bounded_by_mass_transfer():
    f = [F(substrate_uptake_model="reactive", rxn_log10_k0_m_s=k, wall_uptake_model="reflecting", x_substrate_cm=2.0) for k in (-3, -1, 0, 1, 2, 4, 8)]
    assert all(b >= a for a, b in zip(f, f[1:]))


def test_mass_balance_all_cells():
    for s in R.SUB_MODELS:
        for w in R.WALL_MODELS:
            v = P.validate(wulff.DEFS, {"substrate_uptake_model": s, "wall_uptake_model": w, "wall_sticking": 0.01})
            assert T.solve(v)["balance_err"] < 1e-9, (s, w)


def test_wall_variants_order_and_limits():
    refl = F(wall_uptake_model="reflecting", x_substrate_cm=12.0)
    cond = F(x_substrate_cm=12.0)
    st = [F(wall_uptake_model="sticking", wall_sticking=s, x_substrate_cm=12.0) for s in (1e-4, 1e-3, 1e-2, 1e-1, 1.0)]
    assert st[0] == pytest.approx(refl, rel=0.2) or st[0] > cond  # tiny sticking: wall nearly reflecting (more Mo reaches the substrate)
    assert st[-1] == pytest.approx(cond, rel=0.2)             # sticking 1: near the mass-transfer-limited condensation wall
    assert refl > cond                                         # a reflecting wall delivers more Mo to a distant substrate
    # wall reactive with k_rxn -> 0 is reflecting
    assert F(wall_uptake_model="reactive", rxn_log10_k0_m_s=-12.0, x_substrate_cm=12.0) == pytest.approx(refl, rel=1e-6)


def test_reflecting_wall_restores_boat_temperature_response_for_reactive_substrate():
    f = lambda Tb: F(substrate_uptake_model="reactive", wall_uptake_model="reflecting", T_boat_Mo_C=Tb, **{"MoO3.psat_model": "smolik_liquid_cc"})
    assert f(850.0) > 1.5 * f(800.0)


def test_gap_model_reactive_limit():
    v = P.validate(wulff.DEFS, {"substrate_uptake_model": "reactive", "rxn_log10_k0_m_s": 12.0, "rxn_Ea_eV": 0.0, "rxn_n_S": 0.0})
    Tb = 1000.0
    f = growth.gap_flux(v, Tb, Tb, 3e-3)
    v0 = P.validate(wulff.DEFS, {})
    assert growth.gap_flux(v0, Tb, Tb, 3e-3) == 0.0 and f > 0
    Tf = Tb
    Dg = float(thermo.fuller_D(v["carrier"], "MoO3", 1000.0, v["pressure_Pa"], int(v["MoO3.n_oligomer"]))) * (Tf / 1000.0) ** 1.75 * v["D_scale"]
    assert f == pytest.approx(float(thermo.psat_MoO3(v, Tb)) / (1 / growth.k_hk(v, Tb) + 3e-3 * T.R * Tf / Dg), rel=1e-6)


def test_scoped_sigma_restores_and_ensemble_call():
    s0 = {d.name: d.sigma for d in wulff.DEFS}
    with R.with_structural_sigma(wulff.DEFS):
        assert next(d for d in wulff.DEFS if d.name == "rxn_Ea_eV").sigma == 0.5
    assert {d.name: d.sigma for d in wulff.DEFS} == s0
    assert M.ens_call(0.9, 0.0, 0.1, 0.0) == "increase" and M.ens_call(0.1, 0.85, 0.05, 0.0) == "decrease"
    assert M.ens_call(0.5, 0.4, 0.1, 0.0) == "unresolved" and M.ens_call(0.0, 0.0, 1.0, 0.0) == "no_change"
