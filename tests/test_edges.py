import json, pathlib
import numpy as np, pytest
from atomistic import edges as E
from core import params as P
from schemas.closure import Closure
from vessels.cvd_tube import wulff as w

D = json.loads(E.DATA.read_text()) if E.DATA.exists() else None
needs_data = pytest.mark.skipif(D is None, reason="atomistic/data/mos2_edges.json not generated")


@pytest.mark.vessel("atomistic")
@pytest.mark.check("stoichiometry")
def test_ribbon_and_triangle_stoichiometry():
    # Mo edge 0% / S edge 100% ribbon is exactly MoS2; Mo-edge 100% adds 2 S per edge Mo; 50% adds 1
    for J, Nx in ((4, 2), (6, 4)):
        n = Nx * (J + 1)
        assert E.counts(E.ribbon(J, Nx, cov_mo=0.0, cov_s=1.0)) == (n, 2 * n)
        assert E.counts(E.ribbon(J, Nx, cov_mo=1.0, cov_s=1.0)) == (n, 2 * n + 2 * Nx)
        assert E.counts(E.ribbon(J, Nx, cov_mo=0.5, cov_s=1.0)) == (n, 2 * n + Nx)
        assert E.counts(E.ribbon(J, Nx, cov_mo=0.0, cov_s=0.5)) == (n, 2 * n - Nx)
    for n in (4, 6):
        nm = n * (n + 1) // 2
        assert E.counts(E.triangle(n, "Mo", 0.0)) == (nm, n * (n - 1))
        assert E.counts(E.triangle(n, "Mo", 1.0)) == (nm, n * n + 5 * n)  # 4n excess S
        assert E.counts(E.triangle(n, "S", 1.0))[0] == nm


@pytest.mark.vessel("atomistic")
@pytest.mark.check("geometry")
def test_edge_coordination_and_vacuum():
    from ase.neighborlist import neighbor_list
    r = E.ribbon(6, 2, a=3.18, h=1.57, vac=15.0)
    i, _ = neighbor_list("ij", r, 2.8)
    mo = np.array(r.get_chemical_symbols()) == "Mo"
    cn = np.bincount(i, minlength=len(r))[mo]
    assert sorted(set(cn)) == [4, 6] and (cn == 4).sum() == 2  # one bare Mo-edge Mo per cell, rest bulk 6-fold
    y = r.positions[:, 1]
    assert y.min() >= 15.0 - 1e-9 and r.cell[1, 1] - y.max() >= 15.0 - 1e-9 and not r.pbc[1]


@needs_data
@pytest.mark.vessel("atomistic")
@pytest.mark.check("closure_contract")
def test_closures_validate_and_map_to_wulff_params():
    cl = E.closures()
    assert [c.name for c in cl] == ["gamma_edge_Mo", "gamma_edge_S"]
    for c in cl:
        assert isinstance(c, Closure) and c.law == "const" and c.method.startswith("MACE-MP-0") and not c.synthetic
        assert c.sigma["gamma_eV"] > 0
    v = w.apply_wulff_closures(P.defaults(w.DEFS), cl)
    for c in cl: assert v[f"{c.name}.gamma_eV"] == c.params["gamma_eV"] != 0.3
    P.validate(w.DEFS, v)  # inside ParamDef bounds


@needs_data
@pytest.mark.vessel("atomistic")
@pytest.mark.check("data_consistency")
def test_json_self_consistent():
    a = D["monolayer"]["a_A"]
    assert 3.14 < a < 3.21 and D["a_site_A"] == a
    for e in ("Mo", "S"):
        rows = D["gamma_vs_Dmu_S"][e]
        for r in rows:
            assert r["gamma_site_eV"] == pytest.approx(min(r["all_site_eV"].values()))
            assert r["gamma_eV_per_A"] == pytest.approx(r["gamma_site_eV"] / a)
        cv = D["closure_values"][e]
        assert cv["gamma_eV"] == pytest.approx(cv["gamma_eV_per_A"] * a)
    for k, t in D["triangles"]["medium"].items():
        assert t["gamma_site_Dmu0_eV"] == pytest.approx(t["alpha_eV_per_n"] / 3)
    # every stored relaxation met the force criterion
    assert all(r["fmax"] <= 0.02 + 1e-3 for r in D["convergence"]["width"])


@pytest.mark.vessel("atomistic")
@pytest.mark.check("mlip_smoke")
def test_mace_ribbon_energy_finite_or_skip():
    try: c = E.calc("medium")
    except Exception as ex: pytest.skip(f"MACE-MP-0 unavailable: {ex}")
    at = E.ribbon(2, 2, a=3.18, h=1.57); at.calc = c
    assert np.isfinite(at.get_potential_energy()) and np.abs(at.get_forces()).max() < 20
