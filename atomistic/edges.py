"""MoS2 zigzag-edge energies and attachment energies from the MACE-MP-0 foundation potential (ASE). See docs/edge_energies.md.

Lattice picture: Mo at i*a1+j*a2 (a1=(a,0), a2=(a/2,a*sqrt3/2)); an S "site" (i,j) sits over the centre of the Mo triangle
(i,j),(i+1,j),(i,j+1) and carries two S atoms (z=+-h). Edges: Mo-zigzag = Mo row whose outer S sites (1 Mo neighbour) are
missing/partial; S-zigzag = outermost S row with 2 Mo neighbours (Mo fully 6-coordinated).
Edge S coverage is the fraction of the 2 S atoms per outer site that are present (100%, 50% = one of two, alternating
top/bottom along the edge, 0%).
ponytail: MLIP only, no DFT; attachment = energies of relaxed end states, not barriers (no NEB)."""
import json, os, pathlib
import numpy as np
from ase import Atoms
from ase.optimize import FIRE, BFGS

DATA = pathlib.Path(__file__).parent / "data" / "mos2_edges.json"
MACE_FILES = {"medium": "20231203mace128L1_epoch199model", "small": "20231210mace128L0_energy_epoch249model"}
KB = 8.617333e-5
H_S = 1.56  # S-Mo plane offset (A), fixed here; relaxed anyway


# ---------------- builders ----------------
def _site_atoms(a, mo, s_sites, h=H_S):
    """mo: iterable (i,j); s_sites: iterable (i,j,layer) layer in {+1,-1}. Returns positions/symbols."""
    a1, a2 = np.array([a, 0.0]), np.array([a / 2, a * np.sqrt(3) / 2])
    pos, sym = [], []
    for i, j in mo:
        pos.append([*(i * a1 + j * a2), 0.0]); sym.append("Mo")
    for i, j, l in s_sites:
        xy = i * a1 + j * a2 + (a1 + a2) / 3
        pos.append([*xy, l * h]); sym.append("S")
    return np.array(pos), sym


def _sites_for(mo_set, cov_mo=1.0, cov_s=1.0):
    """S atoms for a Mo set. Site neighbour count n_Mo = 3 (bulk, always full), 2 (S-edge, coverage cov_s), 1 (Mo-edge, cov_mo).
    Candidate sites are scanned around the set. Partial coverage keeps alternate layers along the row."""
    mo = set(mo_set)
    cand = {(i + di, j + dj) for i, j in mo for di in (-2, -1, 0, 1) for dj in (-2, -1, 0, 1)}
    out = []
    for (i, j) in sorted(cand):
        n = sum(p in mo for p in ((i, j), (i + 1, j), (i, j + 1)))
        cov = {3: 1.0, 2: cov_s, 1: cov_mo}.get(n, 0.0)
        if cov >= 1.0:
            out += [(i, j, 1), (i, j, -1)]
        elif cov > 0:  # 50%: one S per site, layer alternating with i+j
            out += [(i, j, 1 if (i + j) % 2 == 0 else -1)]
    return out


def ribbon(J=6, Nx=2, a=3.19, cov_mo=0.0, cov_s=1.0, vac=15.0, h=H_S, add_mo=(), add_s=(), pbc_all=False):
    """Periodic-along-x zigzag ribbon: Mo rows 0..J, Mo-edge at the bottom (row 0), S-edge at the top. Both edges present
    (zigzag edges of 2H come in this pairing). Periodic image sites are wrapped by cell translation, not mod arithmetic."""
    mo = [(i, j) for j in range(J + 1) for i in range(Nx)]
    s = []
    for j in range(-1, J + 1):
        n_mo = 1 if j == -1 else (2 if j == J else 3)
        cov = {3: 1.0, 2: cov_s, 1: cov_mo}[n_mo]
        for i in range(Nx):
            if cov >= 1.0: s += [(i, j, 1), (i, j, -1)]
            elif cov > 0: s += [(i, j, 1 if i % 2 == 0 else -1)]  # 50%: alternate layer (needs Nx even)
    pos, sym = _site_atoms(a, list(mo) + list(add_mo), list(s) + list(add_s), h)
    at = Atoms(sym, pos)
    ymin, ymax = at.positions[:, 1].min(), at.positions[:, 1].max()
    at.positions[:, 1] += vac - ymin
    at.positions[:, 2] += vac
    at.set_cell([Nx * a, ymax - ymin + 2 * vac, 2 * vac]); at.set_pbc([True, pbc_all, pbc_all])
    return at


def triangle(n, edge="Mo", cov=1.0, a=3.19, vac=15.0, h=H_S):
    """Triangular flake, n Mo per side, three identical edges. edge 'Mo' (up triangle, outer 1-coordinated S sites at `cov`)
    or 'S' (inverted, outer 2-coordinated S sites at `cov`)."""
    if edge == "Mo": mo = [(i, j) for j in range(n) for i in range(n - j)]
    else: mo = [(i, j) for j in range(n) for i in range(-j, 1)]  # inverted equilateral triangle
    s = _sites_for(mo, cov_mo=cov if edge == "Mo" else 0.0, cov_s=cov if edge == "S" else 0.0)
    pos, sym = _site_atoms(a, mo, s, h)
    at = Atoms(sym, pos); at.center(vacuum=vac); at.set_pbc(False)
    return at


def counts(at):
    s = np.array(at.get_chemical_symbols())
    return int((s == "Mo").sum()), int((s == "S").sum())


# ---------------- MLIP ----------------
def calc(model="medium"):
    """MACE-MP-0 (medium: 2023-12-03 mace128L1_epoch199; small: 2023-12-10 mace128L0_energy_epoch249) from the local cache only."""
    import io, torch
    from mace.calculators import mace_mp
    import e3nn.util.codegen._mixin as M
    if not getattr(M.CodeGenMixin, "_legacy_ok", False):  # MACE-MP-0 files pickle codegen state as raw TorchScript bytes (e3nn 0.4);
        orig = M.CodeGenMixin.__setstate__  # e3nn 0.6 expects (type, bytes). Wrap, do not edit site-packages.

        def setstate(self, d):
            d = dict(d); cg = d.get("__codegen__")
            if cg: d["__codegen__"] = {k: (("torchscript", v) if isinstance(v, bytes) else v) for k, v in cg.items()}
            orig(self, d)
        M.CodeGenMixin.__setstate__ = setstate; M.CodeGenMixin._legacy_ok = True
    p = pathlib.Path.home() / ".cache" / "mace" / MACE_FILES[model]
    if not p.exists(): raise FileNotFoundError(p)  # never download here
    torch.set_num_threads(int(os.environ.get("EDGES_THREADS", "8")))
    c = mace_mp(model=str(p), device="cpu", default_dtype="float64", dispersion=False)
    from e3nn.o3 import _spherical_harmonics as SH  # attributes added to SphericalHarmonics after the files were pickled
    for m in c.models:
        for sm in m.modules():
            if isinstance(sm, SH.SphericalHarmonics) and not hasattr(sm, "sph_func"):
                ls = list(sm.irreps_out.ls); sm.sph_func = SH._spherical_harmonics
                sm._ls_list = ls; sm._lmax = max(ls); sm._is_range_lmax = ls == list(range(max(ls) + 1))
        for sm in m.modules():
            if type(sm).__name__ == "Activation" and not hasattr(sm, "paths"):
                sm.paths = [(mul, (l, p), act) for (mul, (l, p)), act in zip(sm.irreps_in, sm.acts)]
    return c


def relax(at, c, fmax=0.02, steps=600):
    at.calc = c
    BFGS(at, logfile=None).run(fmax=fmax, steps=steps)
    f = np.linalg.norm(at.get_forces(), axis=1).max()
    if f > fmax: FIRE(at, logfile=None).run(fmax=fmax, steps=steps)
    return float(at.get_potential_energy()), float(np.linalg.norm(at.get_forces(), axis=1).max())


# ---------------- closures ----------------
def closures(path=DATA, which="stable_ref"):
    """Closure objects gamma_edge_Mo / gamma_edge_S (law const, params gamma_eV = eV per edge site at the stored reference
    condition) for vessels.cvd_tube.wulff.apply_wulff_closures."""
    from schemas.closure import Closure
    d = json.loads(pathlib.Path(path).read_text())["closure_values"]
    out = []
    for e in ("Mo", "S"):
        v = d[e]
        out.append(Closure(name=f"gamma_edge_{e}", law="const", params={"gamma_eV": v["gamma_eV"]},
                           sigma={"gamma_eV": v["sigma_eV"]}, method=d["method"], source=d["source"], synthetic=False))
    return out


# ---------------- computation driver (python -m atomistic.edges refs|run|analyze) ----------------
RAW = DATA.parent / "raw_results.json"


def refs(model="medium"):
    """Relaxed reference energies: MoS2 monolayer (a, h, E/f.u.), bcc Mo, S8 ring (E/atom), S2 triplet is not used."""
    from ase.build import mx2, bulk, molecule
    from ase.filters import FrechetCellFilter
    c = calc(model)
    ml = mx2("MoS2", "2H", a=3.18, thickness=3.13, vacuum=10); ml.pbc = True; ml.calc = c
    BFGS(FrechetCellFilter(ml, mask=[1, 1, 0, 0, 0, 1]), logfile=None).run(fmax=0.002, steps=500)
    z = ml.positions[:, 2]; h = float(np.ptp(z[np.array(ml.get_chemical_symbols()) == "S"]) / 2)
    mo = bulk("Mo", "bcc", a=3.15, cubic=False); mo.calc = c
    BFGS(FrechetCellFilter(mo), logfile=None).run(fmax=0.002, steps=300)
    r = 2.2  # S8 crown ring: radius 2.2 A, z = +-0.5 A alternating; relaxed below
    pos = [[r * np.cos(2 * np.pi * k / 8), r * np.sin(2 * np.pi * k / 8), 0.5 * (-1) ** k] for k in range(8)]
    s8 = Atoms("S8", pos, cell=[20] * 3, pbc=False); s8.center(); s8.calc = c
    BFGS(s8, logfile=None).run(fmax=0.005, steps=500)
    dd = s8.get_all_distances(); sd = float(np.sort(dd[0])[1])
    return {"model": model, "a_A": float(ml.cell.cellpar()[0]), "h_S_A": h, "E_MoS2_fu_eV": float(ml.get_potential_energy()),
            "E_Mo_bcc_eV": float(mo.get_potential_energy()), "a_Mo_bcc_A": float((2 * mo.get_volume()) ** (1 / 3)),
            "E_S8_per_atom_eV": float(s8.get_potential_energy() / 8), "S8_SS_A": sd}


def run_job(spec):
    spec = dict(spec); model = spec.pop("model", "medium"); kind = spec.pop("kind")
    at = ribbon(**spec) if kind == "ribbon" else triangle(**spec)
    E, f = relax(at, calc(model))
    nmo, ns = counts(at)
    return {"kind": kind, "model": model, **spec, "N_Mo": nmo, "N_S": ns, "E_eV": E, "fmax": f, "natoms": len(at),
            "L_A": float(at.cell[0, 0]) if kind == "ribbon" else None}


def job_list(a, h):
    J = []
    g = dict(a=a, h=h)
    for w in (4, 6, 8, 10): J.append(dict(kind="ribbon", J=w, Nx=2, cov_mo=0.0, cov_s=1.0, **g))  # width convergence
    for v in (6.0, 10.0, 15.0, 20.0): J.append(dict(kind="ribbon", J=4, Nx=2, cov_mo=0.0, cov_s=1.0, vac=v, pbc_all=True, **g))  # vacuum, periodic box
    J.append(dict(kind="ribbon", J=4, Nx=4, cov_mo=0.0, cov_s=1.0, **g))  # length convergence
    for cm in (0.0, 0.5, 1.0):
        for cs in (1.0, 0.5):
            J.append(dict(kind="ribbon", J=8, Nx=2, cov_mo=cm, cov_s=cs, **g))
            J.append(dict(kind="ribbon", J=8, Nx=2, cov_mo=cm, cov_s=cs, model="small", **g))
    for n in (4, 5, 6, 7, 8):
        for k, covs in (("Mo", (1.0, 0.5, 0.0)), ("S", (1.0, 0.5))):
            for cv in covs:
                J.append(dict(kind="triangle", n=n, edge=k, cov=cv, **g))
                if n in (5, 6, 7): J.append(dict(kind="triangle", n=n, edge=k, cov=cv, model="small", **g))
    return J


def attach_jobs(a, h, J=6, Nx=4):
    """Edge-growth end states on Nx=4 ribbons. 'tag' names the configuration. Mo edge: S added at the outer (1-Mo) sites of a bare
    Mo edge. S edge: Mo (+x S) added as a new Mo row beyond the S row (row J+1), m adjacent units; sites (i,J+1)."""
    g = dict(a=a, h=h, J=J, Nx=Nx, kind="ribbon")
    out = [dict(tag="Mo_base", cov_mo=0.0, cov_s=1.0, **g)]
    t, b = +1, -1
    pats = {"S1_adatom": [(0, -1, t)], "S2_adjacent_same_layer": [(0, -1, t), (1, -1, t)], "S2_adjacent_opposite_layer": [(0, -1, t), (1, -1, b)],
            "S2_same_site_pair": [(0, -1, t), (0, -1, b)], "S2_separated": [(0, -1, t), (2, -1, t)],
            "S4_all_top_(50pct_row)": [(i, -1, t) for i in range(Nx)], "S3_adjacent_chain": [(i, -1, t) for i in range(3)]}
    for k, v in pats.items(): out.append(dict(tag="Mo_" + k, cov_mo=0.0, cov_s=1.0, add_s=v, **g))
    out.append(dict(tag="Mo_S8_full_row_100pct", cov_mo=1.0, cov_s=1.0, **g))
    out.append(dict(tag="S_base", cov_mo=0.0, cov_s=1.0, **g))
    R = J + 1

    def unit(i, x):  # Mo(i,R) + x S: first the (i,R) site top/bottom, then the (i-1,R) site top
        sites = [(i, R, t), (i, R, b), (i - 1, R, t)][:x]
        return [(i, R)], sites
    for x in (0, 1, 2, 3):
        mo, s = unit(0, x); out.append(dict(tag=f"S_Mo1_S{x}", cov_mo=0.0, cov_s=1.0, add_mo=mo, add_s=s, **g))
    for m in (2, 3, 4):
        mo, s = [], []
        for i in range(m): u = unit(i, 2); mo += u[0]; s += u[1]
        out.append(dict(tag=f"S_MoS2_x{m}", cov_mo=0.0, cov_s=1.0, add_mo=mo, add_s=s, **g))
    return out


def _work(spec):
    tag = spec.pop("tag", None); r = run_job(spec); r["tag"] = tag
    for k in ("add_s", "add_mo"):
        if k in spec: r[k] = [list(x) for x in spec[k]]
    return r


def main(what):
    import sys, multiprocessing as mp
    os.environ["EDGES_THREADS"] = "3"
    if what == "refs":
        out = {m: refs(m) for m in ("medium", "small")}
        DATA.parent.mkdir(exist_ok=True); (DATA.parent / "refs.json").write_text(json.dumps(out, indent=1)); print(json.dumps(out, indent=1))
    elif what == "analyze": analyze()
    elif what == "run":
        r = json.loads((DATA.parent / "refs.json").read_text())["medium"]
        jobs = job_list(r["a_A"], r["h_S_A"]) + attach_jobs(r["a_A"], r["h_S_A"])
        res = json.loads(RAW.read_text()) if RAW.exists() else []  # resume
        key = lambda d: (d["kind"], d.get("model", "medium"), d.get("J"), d.get("Nx"), d.get("cov_mo"), d.get("cov_s"), d.get("vac"),
                         bool(d.get("pbc_all", False)), d.get("n"), d.get("edge"), d.get("cov"), d.get("tag"))
        done = {key(d) for d in res}
        jobs = [j for j in jobs if key(j) not in done]
        with mp.get_context("spawn").Pool(6) as pool:
            for x in pool.imap_unordered(_work, [dict(j) for j in jobs]):
                res.append(x); RAW.write_text(json.dumps(res, indent=1)); print(len(res), "/", len(jobs), x.get("kind"), x.get("tag"), x["E_eV"], x["fmax"], flush=True)




# ---------------- analysis ----------------
def _fit(n, y):
    A = np.vstack([n, np.ones_like(n)]).T
    c, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    r = y - A @ c
    se = float(np.sqrt((r @ r) / max(len(n) - 2, 1) / ((n - n.mean()) ** 2).sum())) if len(n) > 2 else float("nan")
    return float(c[0]), float(c[1]), se, float(np.abs(r).max())


_S8_CACHE = {}


def s8_gibbs_minus_Eel(T, p_bar=1.0, c=None):
    """G(T,p) - E_el for the S8 crown ring (ideal gas, harmonic MLIP frequencies, rotor D4d sigma=8), per S8, eV.
    Modes below 3 meV (3 trans+3 rot residues, any imaginary mode) are dropped; their number is returned."""
    from ase.vibrations import Vibrations
    from ase.thermochemistry import IdealGasThermo
    import tempfile
    if "s8" not in _S8_CACHE:
        c = c or calc("medium"); r = 2.2
        s8 = Atoms("S8", [[r * np.cos(2 * np.pi * k / 8), r * np.sin(2 * np.pi * k / 8), 0.5 * (-1) ** k] for k in range(8)], cell=[20] * 3, pbc=False)
        s8.center(); s8.calc = c; s8.rattle(0.08, seed=1)  # break symmetry: the symmetric crown is a saddle for MACE (one imaginary mode)
        BFGS(s8, logfile=None).run(fmax=0.0005, steps=2000)
        with tempfile.TemporaryDirectory() as d:
            v = Vibrations(s8, name=os.path.join(d, "vib")); v.run(); en = v.get_energies()
        _S8_CACHE["s8"] = (s8, en)
    s8, en = _S8_CACHE["s8"]
    real = np.real(en[np.isreal(en)]); keep = real[real > 0.003]
    th = IdealGasThermo(vib_energies=keep, potentialenergy=float(s8.get_potential_energy()), atoms=s8, geometry="nonlinear", symmetrynumber=8, spin=0)
    return float(th.get_gibbs_energy(T, p_bar * 1e5, verbose=False) - s8.get_potential_energy()), int(len(en) - len(keep))


def dmu_S(T, pS2_Pa, dG_S8):
    """Delta mu_S (eV, vs E_el(S8)/8) for S2(g) at T, pS2: mu = 1/2 G_S2 = (1/8)[G_S8(T,1bar) + DG_rxn + 4 kT ln p] with S8=4S2."""
    from vessels.cvd_tube import thermo
    kT = KB * T
    dG_rxn = -kT * np.log(float(thermo.kp_S8_S2(T))) / 1.0  # per reaction S8 -> 4 S2, eV (K_p in bar^3)
    return float((dG_S8 + dG_rxn + 4 * kT * np.log(pS2_Pa / 1e5)) / 8)


def analyze(out=DATA):
    ref = json.loads((DATA.parent / "refs.json").read_text()); raw = json.loads(RAW.read_text())
    R = ref["medium"]; a = R["a_A"]; e = R["E_MoS2_fu_eV"]; mu0 = R["E_S8_per_atom_eV"]
    dHf = e - R["E_Mo_bcc_eV"] - 2 * mu0
    res = {"method": "MACE-MP-0 (medium, 2023-12-03 mace128L1_epoch199; small 2023-12-10 mace128L0_energy_epoch249 for model spread), ASE BFGS/FIRE fmax<=0.02 eV/A, float64, no D3",
           "reference": "mu_S = E_MACE(S8 crown ring)/8 (Dmu_S = 0 is S8-rich/S-saturated limit); lower limit Dmu_S = dHf(MoS2)/2 (Mo bulk coexistence)",
           "monolayer": {"a_A": a, "h_S_A": R["h_S_A"], "E_per_MoS2_eV": e, "dHf_MoS2_eV_vs_Mo_bcc_S8": dHf, "Dmu_S_min_eV": dHf / 2,
                         "a_Mo_bcc_A": R["a_Mo_bcc_A"], "small_model": ref["small"], "literature": "a(MoS2 ML) 3.16-3.19 A (PBE ~3.18-3.19, exp bulk 3.16); exp dHf(MoS2) -2.44 eV (-235 kJ/mol, vs rhombic S)"},
           "a_site_A": a}
    rib = [r for r in raw if r["kind"] == "ribbon" and "tag" not in r or (r["kind"] == "ribbon" and r.get("tag") is None)]

    def sumg(r, m=mu0):  # gamma_Mo + gamma_S per length, eV/A, as (intercept at Dmu=0, slope -x/L)
        x = r["N_S"] - 2 * r["N_Mo"]
        return (r["E_eV"] - r["N_Mo"] * e - x * m) / r["L_A"], -x / r["L_A"]
    g = lambda r: {k: r.get(k) for k in ("J", "Nx", "cov_mo", "cov_s", "vac", "pbc_all", "model")}
    conv = {"width": [], "vacuum": [], "length": []}
    for r in rib:
        if r["model"] != "medium" or r["cov_mo"] != 0.0 or r["cov_s"] != 1.0: continue
        i0, sl = sumg(r)
        row = g(r) | {"N_Mo": r["N_Mo"], "N_S": r["N_S"], "sum_gamma_Mo0_S100_at_Dmu0_eV_per_A": i0, "fmax": r["fmax"], "natoms": r["natoms"]}
        if r.get("pbc_all"): conv["vacuum"].append(row)
        elif r["Nx"] == 4: conv["length"].append(row)
        elif r["Nx"] == 2: conv["width"].append(row)
    conv['width'] = list({(r['J'], r['Nx']): r for r in conv['width']}.values())
    for k in conv: conv[k].sort(key=lambda d: (d.get("vac") or 0, d["J"]))
    res["convergence"] = conv
    tri = {}
    for model in ("medium", "small"):
        for edge, covs in (("Mo", (1.0, 0.5, 0.0)), ("S", (1.0, 0.5))):
            for cv in covs:
                t = sorted([r for r in raw if r["kind"] == "triangle" and r["model"] == model and r["edge"] == edge and r["cov"] == cv], key=lambda r: r["n"])
                if len(t) < 3: continue
                m0 = (ref["medium"] if model == "medium" else ref["small"])
                ee, mm = m0["E_MoS2_fu_eV"], m0["E_S8_per_atom_eV"]
                n = np.array([r["n"] for r in t], float)
                E0 = np.array([r["E_eV"] - r["N_Mo"] * ee - (r["N_S"] - 2 * r["N_Mo"]) * mm for r in t])
                X = np.array([r["N_S"] - 2 * r["N_Mo"] for r in t], float)
                al, be, se, mx = _fit(n, E0); xi, ze, _, xr = _fit(n, X)
                assert xr < 1e-9, "excess S not linear in n"
                tri.setdefault(model, {})[f"{edge}_{int(cv*100)}"] = {"n": n.astype(int).tolist(), "alpha_eV_per_n": al, "beta_eV": be, "slope_se": se, "max_resid_eV": mx,
                     "xi_excessS_per_n": xi, "gamma_site_Dmu0_eV": al / 3, "gamma_site_se_eV": se / 3,
                     "dgamma_site_dDmu": -xi / 3, "E0_eV": E0.tolist(), "fmax_max": max(r["fmax"] for r in t)}
    res["triangles"] = tri
    # ribbon sums and triangle sums at Dmu = 0 (medium), for each coverage combination, J=8
    cmp_ = []
    for r in rib:
        if r["J"] == 8 and r["Nx"] == 2 and not r.get("pbc_all"):
            i0, sl = sumg(r, mu0)
            em, es = int(r["cov_mo"] * 100), int(r["cov_s"] * 100)
            tt = tri.get(r["model"], {})
            km, ks = f"Mo_{em}", f"S_{es}"
            ts = (tt[km]["gamma_site_Dmu0_eV"] + tt[ks]["gamma_site_Dmu0_eV"]) / a if km in tt and ks in tt else None
            cmp_.append({"model": r["model"], "Mo_cov_pct": em, "S_cov_pct": es, "ribbon_sum_eV_per_A": i0, "ribbon_sum_slope_eV_per_A_per_eV": sl,
                         "triangle_sum_eV_per_A": ts, "diff_eV_per_A": None if ts is None else i0 - ts, "fmax": r["fmax"]})
    res["ribbon_vs_triangle_sum_Dmu0"] = cmp_
    # Separation of the two edges. Ribbons carry one Mo edge + one S edge, so only sums are defined; the S_100 edge is taken from the
    # triangle fits (3 identical edges, residual < 0.01 eV) and every other edge from ribbon differences at J=8 (converged in width).
    mn = res["monolayer"]["Dmu_S_min_eV"]
    t100 = tri["medium"]["S_100"]
    gS100 = lambda d: (t100["gamma_site_Dmu0_eV"] + t100["dgamma_site_dDmu"] * d) / a  # eV/A
    rb = {(int(r["cov_mo"] * 100), int(r["cov_s"] * 100)): r for r in rib if r["J"] == 8 and r["Nx"] == 2 and not r.get("pbc_all") and r["model"] == "medium"}
    rs = {(int(r["cov_mo"] * 100), int(r["cov_s"] * 100)): r for r in rib if r["J"] == 8 and r["Nx"] == 2 and not r.get("pbc_all") and r["model"] == "small"}
    def phases(rb, g100):
        out = {}
        for th in (0, 50, 100):
            i0, sl = sumg(rb[(th, 100)], rb["mu"]); out[f"Mo_{th}"] = (i0 - g100(0), sl - (g100(1) - g100(0)))
        for ph in (100, 50):
            d0 = [sumg(rb[(th, ph)], rb["mu"])[0] - sumg(rb[(th, 100)], rb["mu"])[0] for th in (0, 50, 100)]
            dsl = [sumg(rb[(th, ph)], rb["mu"])[1] - sumg(rb[(th, 100)], rb["mu"])[1] for th in (0, 50, 100)]
            out[f"S_{ph}"] = (g100(0) + float(np.mean(d0)), (g100(1) - g100(0)) + float(np.mean(dsl)))
        return out
    rb["mu"] = mu0
    P_ = phases(rb, gS100)
    res["phase_gamma_eV_per_A"] = {k: {"at_Dmu0": v[0], "slope_per_eV": v[1], "gamma_site_Dmu0_eV": v[0] * a, "slope_site": v[1] * a} for k, v in P_.items()}
    res["additivity_check_S50_minus_S100_eV_per_A"] = [sumg(rb[(th, 50)])[0] - sumg(rb[(th, 100)])[0] for th in (0, 50, 100)]
    if all(k in rs for k in [(0, 100), (50, 100), (100, 100), (0, 50), (50, 50), (100, 50)]):
        rs["mu"] = ref["small"]["E_S8_per_atom_eV"]
        # small model: ribbon sums only (its S_100 triangle fit is noisy), anchored with the MEDIUM S_100 value (so only the ribbon differences differ)
        def sumg_s(r): return (r["E_eV"] - r["N_Mo"] * ref["small"]["E_MoS2_fu_eV"] - (r["N_S"] - 2 * r["N_Mo"]) * ref["small"]["E_S8_per_atom_eV"]) / r["L_A"]
        res["small_model_ribbon_sums_Dmu0_eV_per_A"] = {f"Mo{k[0]}_S{k[1]}": sumg_s(r) for k, r in rs.items() if k != "mu"}
        res["medium_model_ribbon_sums_Dmu0_eV_per_A"] = {f"Mo{k[0]}_S{k[1]}": sumg(r)[0] for k, r in rb.items() if k != "mu"}
    grid = np.linspace(mn, 0, 8)
    stab = {}
    for edge in ("Mo", "S"):
        rows = []
        for d in grid:
            gs = {k: (v[0] + v[1] * d) * a for k, v in P_.items() if k.startswith(edge + "_")}
            kbest = min(gs, key=gs.get)
            rows.append({"Dmu_S_eV": float(d), "best": kbest, "gamma_site_eV": gs[kbest], "gamma_eV_per_A": gs[kbest] / a, "all_site_eV": gs})
        stab[edge] = rows
    res["gamma_vs_Dmu_S"] = stab
    # model spread (small vs medium) of gamma_site at the S-rich limit and at the lower limit
    spread = {}
    for k, v in tri["medium"].items():
        if k in tri.get("small", {}):
            vs = tri["small"][k]
            spread[k] = {"medium_Dmu0": v["gamma_site_Dmu0_eV"], "small_Dmu0": vs["gamma_site_Dmu0_eV"],
                         "medium_slope": v["dgamma_site_dDmu"], "small_slope": vs["dgamma_site_dDmu"]}
    res["model_spread"] = spread
    # attachment
    byt = {r["tag"]: r for r in raw if r.get("tag")}
    att = {}
    if "Mo_base" in byt:
        b = byt["Mo_base"]; Eb = b["E_eV"]
        for t_, r in byt.items():
            if not t_.startswith("Mo_") or t_ == "Mo_base": continue
            dn = r["N_S"] - b["N_S"]
            att[t_] = {"dN_S": dn, "E_attach_total_eV_Dmu0": r["E_eV"] - Eb - dn * mu0, "per_S_eV_Dmu0": (r["E_eV"] - Eb - dn * mu0) / dn, "fmax": r["fmax"]}
    if "S_base" in byt:
        b = byt["S_base"]; Eb = b["E_eV"]
        for t_, r in byt.items():
            if not t_.startswith("S_Mo") or t_ == "S_base": continue
            dMo, dS = r["N_Mo"] - b["N_Mo"], r["N_S"] - b["N_S"]
            att[t_] = {"dN_Mo": dMo, "dN_S": dS, "E_attach_total_eV_Dmu0": r["E_eV"] - Eb - dMo * e - (dS - 2 * dMo) * mu0,
                       "per_Mo_eV_Dmu0": (r["E_eV"] - Eb - dMo * e - (dS - 2 * dMo) * mu0) / dMo, "slope_per_Dmu_S": -(dS - 2 * dMo), "fmax": r["fmax"]}
    res["attachment"] = att
    out = pathlib.Path(out); out.write_text(json.dumps(res, indent=1)); return res




REF_COND = {"T_K": 1073.15, "pS2_Pa": 50.0}  # representative CVD substrate condition (S2 partial pressure of the tube defaults ~50-110 Pa)
FLOOR_EV_SITE = 0.15  # assumed MLIP floor (~0.05 eV/atom x ~3 under-coordinated atoms per edge site); NOT derived
DMU_SIGMA_EV = 0.3  # uncertainty of Dmu_S(T,p) from the MLIP/ideal-gas S8 reference


def finalize(path=DATA):
    """Add Dmu_S(T,p) conversion and the closure values (stable phase at REF_COND) to the JSON."""
    d = json.loads(pathlib.Path(path).read_text())
    a = d["a_site_A"]
    dG, f_low = s8_gibbs_minus_Eel(REF_COND["T_K"])
    conv = {"formula": "Dmu_S = (G_S8(T,1bar)-E_el(S8) + DG_rxn(S8=4S2) + 4 kT ln(pS2/1bar))/8, DG_rxn=-kT ln Kp (JANAF Shomate, vessels.cvd_tube.thermo)",
            "G_S8_minus_Eel_eV_at_ref_T": dG, "S8_modes_dropped_(6_expected)": f_low,
            "table": {f"T={T:.0f}K,pS2={p:g}Pa": dmu_S(T, p, s8_gibbs_minus_Eel(T)[0])
                      for T, p in ((REF_COND["T_K"], 50.0), (REF_COND["T_K"], 1.0), (REF_COND["T_K"], 1e3), (973.15, 50.0))}}
    dmu = dmu_S(REF_COND["T_K"], REF_COND["pS2_Pa"], dG)
    dmu_eff = float(np.clip(dmu, d["monolayer"]["Dmu_S_min_eV"], 0.0))  # outside the stability window the edge table is not applicable
    conv.update(Dmu_ref_unclipped_eV=dmu, Dmu_ref_used_eV=dmu_eff, vessel_mu_S_eV_note="the vessel's mu_S_eV is an OFFSET added to ln pS (pS exp(mu/kT)); mu_S_eV=0 corresponds to Dmu_ref here; an offset x shifts Dmu by x")
    d["dmu_conversion"] = conv
    cv = {}
    ph = d["phase_gamma_eV_per_A"]
    ms, mm = d["small_model_ribbon_sums_Dmu0_eV_per_A"], d["medium_model_ribbon_sums_Dmu0_eV_per_A"]
    for e in ("Mo", "S"):
        g = {k: (v["at_Dmu0"] + v["slope_per_eV"] * dmu_eff) * a for k, v in ph.items() if k.startswith(e + "_")}
        kb = min(g, key=g.get)
        slope = ph[kb]["slope_site"]
        cv[e] = {"phase": kb, "gamma_eV": g[kb], "gamma_eV_per_A": g[kb] / a, "slope_eV_per_eV": slope, "all_phases_site_eV": g}
    kbest = (cv["Mo"]["phase"], cv["S"]["phase"])
    key = f"Mo{kbest[0].split('_')[1]}_S{kbest[1].split('_')[1]}"
    spread = abs(ms[key] - mm[key]) * a  # medium vs small, ribbon sum of the two stable phases, eV/site
    for e in ("Mo", "S"):
        comp = {"anchor_and_ribbon_triangle_mismatch": 0.03 * a, "model_spread_medium_vs_small": spread, "mlip_floor_assumed": FLOOR_EV_SITE,
                "Dmu_condition": DMU_SIGMA_EV * abs(cv[e]["slope_eV_per_eV"])}
        cv[e]["sigma_components_eV"] = comp; cv[e]["sigma_eV"] = float(np.sqrt(sum(v * v for v in comp.values())))
    cv.update(method="MACE-MP-0 (medium) ribbons+triangles, ASE", source=f"atomistic/edges.py -> atomistic/data/mos2_edges.json; stable phase at T={REF_COND['T_K']:.0f} K, pS2={REF_COND['pS2_Pa']:g} Pa, "
              f"Dmu_S={dmu_eff:.2f} eV vs S8; eV per edge site (a={a:.3f} A); NOT a barrier", ref_condition=REF_COND)
    d["closure_values"] = cv
    at = d["attachment"]
    tot = [0.0, at["S_Mo1_S2"]["E_attach_total_eV_Dmu0"], at["S_MoS2_x2"]["E_attach_total_eV_Dmu0"], at["S_MoS2_x3"]["E_attach_total_eV_Dmu0"], at["S_MoS2_x4"]["E_attach_total_eV_Dmu0"]]
    d["attachment_summary"] = {
        "S_edge_MoS2_unit_incremental_eV": [tot[i + 1] - tot[i] for i in range(4)],
        "meaning": "energy (vs bulk MoS2 per f.u., composition-neutral so independent of mu_S) of adding the 1st/2nd/3rd/4th MoS2 unit to a new row on the S edge of a 4-cell ribbon: 1st = adatom on the straight edge, 2nd = kink-pair/dimer, 3rd ~ kink site (half-crystal, ~0 expected), 4th closes the row (annihilates 2 kinks)",
        "kink_formation_eV_estimate": tot[2] / 2,
        "Mo_adatom_on_S_edge_vs_extra_S_eV_Dmu0": {f"MoS{x}": at[f"S_Mo1_S{x}"]["E_attach_total_eV_Dmu0"] for x in range(4)},
        "Mo_edge_S_binding_eV_per_S_vs_S8": {k: v["per_S_eV_Dmu0"] for k, v in at.items() if k.startswith("Mo_")},
        "NOT_computed": "barriers (no NEB); gas-phase precursors (MoO3, S2) as reference; starts from bare (0%) Mo edge only, i.e. an unstable edge, so Mo-edge numbers mix edge-phase change with attachment"}
    pathlib.Path(path).write_text(json.dumps(d, indent=1)); return cv


if __name__ == "__main__":
    import sys
    main(sys.argv[1]) if sys.argv[1] != "finalize" else print(json.dumps(finalize(), indent=1))


# ---------------- Mo-edge S-coverage kink (docs/wulff_reanchor.md) ----------------
def mo_kink(J=6, Nx=4, model="medium", out=DATA.parent / "mo_kink.json"):
    """Fill the second S of each outer site of the stable 50 %-S Mo edge one site at a time (n = 0..Nx on a periodic row):
    increment d_n = E_n - E_(n-1) - E_S8/8 (eV, vs S8 ring; negative = bound). n=1 makes a kink pair, n=2..Nx-1 move a kink (the
    half-crystal step), n=Nx closes the row. E_kink_Mo = -mean(d_2..d_(Nx-1)) = S binding energy at the kink. End-state energies, no barrier.
    ponytail: one S pattern, one model, no gas-phase S2 (the S8 ring is the MLIP reference, like gamma_edge)."""
    r = json.loads((DATA.parent / "refs.json").read_text())[model]
    c = calc(model); eS = r["E_S8_per_atom_eV"]
    E = []
    for n in range(Nx + 1):
        add = [(i, -1, -1 if i % 2 == 0 else 1) for i in range(n)]  # layer opposite to the 50 % pattern of ribbon()
        at = ribbon(J=J, Nx=Nx, a=r["a_A"], cov_mo=0.5, cov_s=1.0, h=r["h_S_A"], add_s=add)
        E.append(relax(at, c)); print(n, E[-1], flush=True)
    d = [E[n][0] - E[n - 1][0] - eS for n in range(1, Nx + 1)]
    res = {"model": model, "J": J, "Nx": Nx, "E_eV": [e[0] for e in E], "fmax": [e[1] for e in E], "increment_vs_S8_eV": d,
           "E_kink_Mo_eV": -float(np.mean(d[1:Nx - 1])), "E_kink_Mo_spread_eV": float(np.ptp(d[1:Nx - 1]))}
    pathlib.Path(out).write_text(json.dumps(res, indent=1)); return res


def closures_kink(path=DATA, mo_path=DATA.parent / "mo_kink.json", floor=0.15):
    """Closures E_kink_Mo / E_kink_S (law const, params E_eV; detachment energy, positive = bound) for wulff.apply_wulff_closures.
    E_kink_Mo: S atom at a coverage kink of the 50 %-S Mo edge vs the S8 ring (mo_kink). E_kink_S: MoS2 unit at the S-edge kink vs bulk
    MoS2 (3rd increment of attachment_summary, sign flipped). sigma = quadrature of half the kink-increment spread and an ASSUMED
    MLIP floor (0.15 eV, same assumption as closures(); not derived). Single MACE model (medium); no small-model check of these."""
    from schemas.closure import Closure
    a = json.loads(pathlib.Path(path).read_text())["attachment_summary"]["S_edge_MoS2_unit_incremental_eV"]
    m = json.loads(pathlib.Path(mo_path).read_text())
    vals = {"Mo": (m["E_kink_Mo_eV"], m["E_kink_Mo_spread_eV"] / 2, "mo_kink.json: S at 50 %-S Mo-edge coverage kink vs S8 ring"),
            "S": (-a[2], abs(a[1] - a[2]) / 2, "mos2_edges.json attachment_summary: 3rd MoS2 unit on S edge vs bulk MoS2")}
    return [Closure(name=f"E_kink_{e}", law="const", params={"E_eV": x}, sigma={"E_eV": float(np.hypot(sp, floor))},
                    method="MACE-MP-0 (medium) end-state energies, no barrier; sigma incl. assumed floor", source=src, synthetic=False)
            for e, (x, sp, src) in vals.items()]
