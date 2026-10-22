"""Kinetic Wulff construction + shape map for monolayer MoS2 CVD (hexagonal crystal, Mo-zigzag and S-zigzag edges).

Literature (searched Oct 2026; abstracts/secondary summaries only, thresholds NOT checked against the originals):
 - Wang et al., Chem. Mater. 26, 6371 (2014): along the flow, crystals go triangle (near MoO3 source, Mo-rich) -> hexagon -> (S-rich)
   triangle of the other orientation as local Mo:S falls with distance from the MoO3 boat.
 - Govind Rajan, Warner, Blankschtein, Strano, ACS Nano 10, 4330 (2016): generalised mechanistic CVD model / kinetic phase
   diagram: Mo-rich -> Mo-zigzag triangles, middle -> hexagons, S-rich -> S-zigzag triangles.
 - Momeni et al., npj 2D Mater. Appl. 2, 27 (2018): edge growth kinetics.
Model: edge e in {Mo, S} advances at normal velocity v_e = k_e(T) * (p_feed - p_eq,e), Arrhenius k_e = A_e exp(-Ea_e/kT).
Mo-zz edge grows by S attachment (feed = pS), S-zz edge by Mo attachment (feed = pMoO3). Detailed balance: the reverse rate is
k_e * p_eq,e with p_eq,e = P_eq_ref * exp(gamma_edge_e * a_site / kT), so net rate -> 0 at equilibrium (a stiffer, higher-energy
edge detaches more). Slow edges survive (kinetic Wulff): hexagon with apothems a = v_Mo t (Mo edges), b = v_S t (S edges),
r = a/b: L_Mo = 2(2b-a)/sqrt3, L_S = 2(2a-b)/sqrt3, so r=1 regular hexagon, r<=1/2 Mo-edge triangle, r>=2 S-edge triangle.
Shape index s = clip((L_Mo-L_S)/(L_Mo+L_S)) = clip(3(1-r)/(1+r)) in [-1,1]; +1 triangle_Mo, 0 hexagon, -1 triangle_S.

RETUNED (Oct 18) after the sourced MoO3 vapour pressure (~1 Pa at 1000 K, 30x below the old placeholder) cut p_MoO3 at the substrate
to ~0.1 Pa: S-edge A 1->15 um/s/Pa and P_eq_ref 1e-3->1e-5 Pa so the default tube again spans all classes. Still synthetic.
HONESTY: every rate/energy below is source="synthetic" (A ratio tuned only so the default tube spans all classes). Gate 2 (Wang
trend) is NOT claimed; only the direction is checked. Anchoring needs measured edge energies / attachment barriers (DFT/MLIP
closures: names k_attach_Mo / k_attach_S (arrhenius: A, Ea_eV) and gamma_edge_Mo / gamma_edge_S (const: gamma_eV_per_site)) plus
shape-vs-position data from one real tube (boat T, flow, positions, substrate micrographs).
RE-ANCHORED (Oct 20, docs/wulff_reanchor.md): the equilibrium term now comes from KINK-site energetics (eq_model="kink", default), not
the edge excess energy: p_eq,e = p0_e(T) exp(-E_kink,e/kT) with E_kink,e = energy to remove one growth unit from a half-crystal site
to its gas-phase reference (eV, positive = bound).
 - Mo-zz edge (S feed): unit = one S atom, reference = S2 gas via the Tier 1 species; mu_S(gas) = E_S8/8 + Dmu_S(T,p) with
   Dmu_S(T,p) = Dmu_S_std(T) + 1/2 kT ln(pS2/1 bar) (MLIP S8 energy + JANAF S2 free energy), so p_eq = 1 bar exp(-2(E_kink_Mo + Dmu_S_std(T))/kT).
 - S-zz edge (Mo feed): unit = MoS2, reference = Mo-bearing vapour (MoO3 units, as Tier 1). E_kink_S is the kink energy RELATIVE TO
   BULK MoS2 (ideal half-crystal = 0); the vapour/bulk-crystal equilibrium pressure P_std_Mo_Pa needs sulfidation thermodynamics
   (MoO3 + S2 -> MoS2 + SO2) that are not in the repo: stays synthetic. p_eq = P_std_Mo_Pa exp(-E_kink_S/kT).
 Defaults (synthetic) reproduce the old p_eq at 1000 K for the S edge exactly and for the Mo edge to a factor ~2. eq_model="legacy_gamma"
 restores p_eq = P_eq_ref_Pa exp(gamma_edge a_site/kT); gamma_edge_* closures are accepted but no longer enter the equilibrium term.
ponytail: v<=0 (undersaturated) floored to 1e-12 um/s instead of etching; no edge reconstruction/passivation; local p from the
Tier 1 march at wall T; boundary defined at |s| = s_boundary."""
import numpy as np
from types import SimpleNamespace
from core import params as P, uq
from core.api import apply_closures
from core.params import ParamDef as D
import vessels.cvd_tube as tube

KB = 8.617333e-5  # eV/K
SYN = "synthetic"
WDEFS = [
    D("k_attach_Mo.A", "Mo-edge attachment prefactor (S feed)", "um/s/Pa", 0.06, 1e-6, 1e6, 0.5, source=SYN, group="wulff"),
    D("k_attach_Mo.Ea_eV", "Mo-edge attachment barrier", "eV", 0.6, 0, 3, 0.05, False, source=SYN, group="wulff"),
    D("k_attach_S.A", "S-edge attachment prefactor (Mo feed)", "um/s/Pa", 15.0, 1e-6, 1e6, 0.5, source=SYN, group="wulff"),
    D("k_attach_S.Ea_eV", "S-edge attachment barrier", "eV", 0.5, 0, 3, 0.05, False, source=SYN, group="wulff"),
    D("gamma_edge_Mo.gamma_eV", "Mo-zigzag edge energy per site", "eV", 0.3, 0, 3, 0.05, False, source=SYN, group="wulff"),
    D("gamma_edge_S.gamma_eV", "S-zigzag edge energy per site", "eV", 0.3, 0, 3, 0.05, False, source=SYN, group="wulff"),
    D("P_eq_ref_Pa", "Legacy equilibrium pressure scale (eq_model=legacy_gamma only)", "Pa", 1e-5, 1e-12, 1e3, source=SYN, group="wulff"),
    D("eq_model", "Edge equilibrium term", "", "kink", choices=["kink", "legacy_gamma", "dft_rosen"], group="model",
      help="kink: p_eq from kink-site energy and gas reference; legacy_gamma: old gamma_edge*a_site/kT form (collapses with real MLIP gamma); "
           "dft_rosen: Mo edge from the Rosen 2018 DFT S-binding (see rosen_sbinding.py), S edge as 'kink' (MACE E_kink_S, synthetic P_std_Mo)"),
    D("edge_model", "Shape model", "", "kinetic", choices=["kinetic", "momeni_eq", "momeni_eq_v1"], group="model",
      help="kinetic: edge velocities from attachment minus detached rate (eq_model picks MACE/Rosen/synthetic closures); momeni_eq: equilibrium Wulff shape "
           "from the Momeni 2018 SI edge energies at the local Delta mu_S (momeni_edges.py, corrected edge orientations per Cao 2015); momeni_eq_v1 = "
           "the first pre-registered version with ZZS2 wrongly on the S-edge orientation (kept for the record); no kinetics, no growth size"),
    D("momeni_mapping", "Local state -> Delta mu_S (edge_model=momeni_eq)", "", "kT", choices=["kT", "bridge"], group="model",
      help="kT (primary, pre-registered): Dmu_S_std + 1/2 kT ln(pS2/1 bar); bridge: the authors' Delta mu_S = 0.8 - 12 u with u = Omega (c_MoO3 - c_eq)"),
    D("E_kink_Mo.E_eV", "Mo-zz kink: S-atom detachment energy to S8/S2 reference", "eV", 1.7, -5, 5, 0.2, False, source=SYN, group="wulff",
      help="positive = bound; synthetic default reproduces the old p_eq at ~1000 K; MLIP closure E_kink_Mo (atomistic.edges.mo_kink)"),
    D("E_kink_S.E_eV", "S-zz kink: MoS2 detachment energy relative to bulk MoS2", "eV", -0.3, -5, 5, 0.2, False, source=SYN, group="wulff",
      help="ideal half-crystal site = 0; synthetic default reproduces the old p_eq; MLIP closure E_kink_S"),
    D("P_std_Mo_Pa", "Mo-vapour pressure in equilibrium with bulk MoS2 (E_kink_S=0)", "Pa", 1e-5, 1e-12, 1e3, source=SYN, group="wulff",
      help="needs MoO3+S2->MoS2+SO2 thermodynamics (not in repo)"),
    D("Dmu_S_std_eV", "S chemical potential of S2 gas at 1 bar vs E(S8 ring)/8, at 1073.15 K", "eV", -0.7960, -3, 1, 0.3, False, source="MACE-MP-0 S8 + JANAF",
      help="= Dmu_S(1073 K, 50 Pa) = -1.148 (edges_energies.md) - 1/2 kT ln(50/1e5); +-0.3 eV conversion uncertainty stated there"),
    D("mu_S_eV", "Sulfur chemical-potential offset (pS -> pS exp(mu/kT))", "eV", 0.0, -2, 2, group="wulff"),
    D("s_hex", "Hexagon if |s| below", "", 0.15, 0, 1, group="wulff", source="convention"),
    D("s_tri", "Triangle if |s| at/above", "", 0.95, 0, 1, group="wulff", source="convention"),
    D("s_boundary", "|s| defining the triangle-hexagon boundary", "", 0.5, 0.05, 0.95, group="wulff", source="convention"),
    D("duration_min", "Growth duration at the substrate", "min", 10.0, 0.1, 600, 0.1, group="operation"),
    D("N_nuc_cm2", "Nucleation density on the substrate", "1/cm2", 1e4, 1, 1e8, 1.0, source=SYN, group="wulff",
      help="placeholder: measured values span ~1e2-1e5 /cm2 depending on substrate/seeding; none sourced here"),
    D("L_map_cm", "Shape-map length downstream of MoO3 boat", "cm", 25.0, 1, 100, group="wulff"),
    D("dE_Mo_dft_eV", "Shift on the Rosen DFT Mo-edge S-binding free energy (eq_model=dft_rosen)", "eV", 0.0, -2, 2, 0.0, False,
      source="ASSUMPTION: sigma 0.25 eV (set with wulff.with_sigma; default 0 so other configurations keep their MC stream) = spread of the three theta_S 0.5->1 steps (~0.3 eV) plus an assumed PBE-D3 error; not derived", group="wulff"),
]
from vessels.cvd_tube.growth import GDEFS  # noqa: E402  (inventory / gap knobs, Track A)
DEFS = tube.DEFS + WDEFS + GDEFS
_NAMES = SimpleNamespace(params=[d.name for d in WDEFS])


def apply_wulff_closures(values, closures):
    """Same name.param mapping as core.api.apply_closures; reverse partners are implicit (detailed balance). E_kink_Mo / E_kink_S
    (param E_eV) enter the equilibrium term; gamma_edge_* are accepted but only act with eq_model="legacy_gamma"."""
    return apply_closures(_NAMES, values, closures)


_T_REF = 1073.15  # K, temperature of Dmu_S_std_eV
_S2 = None  # lazy: thermo._S2 Shomate set


def _gS2_eV(T):
    """JANAF Gibbs energy of S2(g) at 1 bar (without the T-independent part), eV/molecule; only differences are used."""
    from vessels.cvd_tube import thermo as th
    h, s = th._shomate(th._S2, T)
    return ((128.6003 + h) * 1e3 - np.asarray(T, float) * s) / 96485.332


def p_eq(v, e, T_K):
    """Equilibrium feed pressure (Pa) of edge e in {'Mo','S'} at T_K: detailed-balance partner of the attachment rate."""
    kT = KB * T_K
    if v["eq_model"] == "legacy_gamma":
        x = v[f"gamma_edge_{e}.gamma_eV"] / kT
        return v["P_eq_ref_Pa"] * np.exp(np.clip(x, -700, 700))
    if e == "Mo" and v["eq_model"] == "dft_rosen":
        # Rosen, Notestein & Snurr, JPCC 122, 15318 (2018), DOI 10.1021/acs.jpcc.8b02524, SI mos2_data.xlsx (Mo edge, theta_H=0).
        # <dF_S> = mean of the three S steps theta_S 0.5->1 (vs H2S/H2); gas ref: S2 via H2S=H2+1/2 S2 (NIST/JANAF). ASSUMPTIONS in rosen_sbinding.py.
        from vessels.cvd_tube import rosen_sbinding as R
        d = np.vectorize(lambda t: float(np.mean(R.dF_S(t)[3:6])) - R.dmu_S2_std(t))(np.asarray(T_K, float))  # <dF_S> - Dmu_S2_std(T)
        return 1e5 * np.exp(np.clip(2 * (d + v["dE_Mo_dft_eV"]) / kT, -700, 700))
    E = v[f"E_kink_{e}.E_eV"]
    if e == "Mo":  # S atom <- 1/2 S2: Dmu_S(T, p) = Dmu_std(T) + 1/2 kT ln(p/1 bar)  =>  p_eq = 1 bar exp(-2 (E + Dmu_std)/kT)
        dmu = v["Dmu_S_std_eV"] + 0.5 * (_gS2_eV(T_K) - _gS2_eV(_T_REF))
        return 1e5 * np.exp(np.clip(-2 * (E + dmu) / kT, -700, 700))
    return v["P_std_Mo_Pa"] * np.exp(np.clip(-E / kT, -700, 700))


def rates(v, pM, pS, T_K):
    """Net edge velocities (um/s) with Arrhenius forward and detailed-balance reverse. Returns (v_Mo, v_S)."""
    pS = pS * np.exp(v["mu_S_eV"] / (KB * T_K))
    out = []
    for e, feed in (("Mo", pS), ("S", pM)):
        k = v[f"k_attach_{e}.A"] * np.exp(-v[f"k_attach_{e}.Ea_eV"] / (KB * T_K))
        peq = p_eq(v, e, T_K)
        out.append(np.maximum(k * (feed - peq), 1e-12))
    return out


def geometry(r, v):
    """r = v_Mo/v_S -> shape class, index s, edge-length ratio L_Mo/L_S (apothem b=1)."""
    r = np.asarray(r, float)
    LM, LS = np.maximum(2 - r, 0), np.maximum(2 * r - 1, 0)  # (2b-a), (2a-b) with b=1; common factor 2/sqrt3 dropped
    s = np.where(r >= 2, -1.0, np.where(r <= 0.5, 1.0, (LM - LS) / np.maximum(LM + LS, 1e-30)))
    cls = np.where(np.abs(s) < v["s_hex"], "hexagon", np.where(np.abs(s) >= v["s_tri"], np.where(s > 0, "triangle_Mo", "triangle_S"), "truncated_triangle"))
    return cls, s, LM / np.maximum(LS, 1e-30)


def shape_at(values, feed, T_K=None, mu_S=None):
    """feed = Passport (species MoO3_g/S2_g p_Pa at substrate) or (pMoO3_Pa, pS2_Pa); T_K defaults to passport T."""
    v = P.defaults(WDEFS) | values
    if mu_S is not None:
        v["mu_S_eV"] = mu_S
    if hasattr(feed, "species"):
        pM, pS, T_K = feed.species["MoO3_g"]["p_Pa"].p50, feed.species["S2_g"]["p_Pa"].p50, T_K or feed.T_K.p50
    else:
        pM, pS = feed
    if v["edge_model"].startswith("momeni_eq"):
        from vessels.cvd_tube import momeni_edges as ME
        v2 = v["edge_model"] == "momeni_eq"
        d = ME.dmu_kT(v, pS, T_K) if v["momeni_mapping"] == "kT" else ME.dmu_bridge(pM, T_K)[0]
        cls, s, dod = ME.shape_from_dmu(float(d), v["s_hex"], v["s_tri"], v2)
        e = ME.wulff_edges(float(d), v2)
        return {"shape": cls, "shape_index": float(s), "dmu_S_eV": float(d), "dodecagon": dod, "edge_len_Mo_rel": e["L_Mo"], "edge_len_S_rel": e["L_S"], "edge_len_AC_rel": e["L_AC"]}
    vM, vS = rates(v, pM, pS, T_K)
    r = vM / vS
    cls, s, lr = geometry(r, v)
    return {"shape": str(cls), "shape_index": float(s), "edge_length_ratio_Mo_S": float(lr), "r_vMo_vS": float(r),
            "v_Mo_um_s": float(vM), "v_S_um_s": float(vS)} | growth(v, vM, vS)


def growth(v, vM, vS):
    """Flake size after `duration_min` at constant edge velocities: apothems a = vMo t, b = vS t (um). Slow edges survive, so a line
    farther than 2x the other apothem does not cut the polygon; area = 1/2 sum(L_i d_i) (tangential polygon).
    Linear in t by construction (constant feed); coalescence at ~1/sqrt(N_nuc) is only flagged, not simulated."""
    t = v["duration_min"] * 60
    a0, b0 = float(vM) * t, float(vS) * t
    a, b = min(a0, 2 * b0), min(b0, 2 * a0)
    LM, LS = 2 * (2 * b - a) / np.sqrt(3), 2 * (2 * a - b) / np.sqrt(3)
    A = 1.5 * (LM * a + LS * b)
    Lc = 1e4 / np.sqrt(v["N_nuc_cm2"])
    d_eq = float(np.sqrt(4 * A / np.pi))
    return {"apothem_Mo_um": a0, "apothem_S_um": b0, "size_um": d_eq, "edge_len_Mo_um": float(LM), "edge_len_S_um": float(LS),
            "L_coalesce_um": float(Lc), "coalesced": bool(d_eq > Lc)}


def _curve(values, xrel):
    """shape index vs x (cm downstream of MoO3 boat) from one Tier 1 march."""
    x, T, o, m = tube.march(values)
    xs = values["x_MoO3_cm"] + xrel
    pM, pS, Ts = (np.interp(xs, x * 100, a) for a in (o["pM"], o["pS"], T))
    if values["edge_model"].startswith("momeni_eq"):
        from vessels.cvd_tube import momeni_edges as ME
        return ME.shape_index(values, pM, pS, Ts, values["edge_model"] == "momeni_eq")
    r = np.divide(*rates(values, pM, pS, Ts))
    return geometry(r, values)[1]


def boundary_cm(xrel, s, level):
    """First position (cm from MoO3 boat) where |s| falls through `level` (triangle -> hexagon side); nan if none (never below `level`... returns xrel[0] if already below at the start)."""
    a = (1.0 if s[0] >= 0 else -1.0) * np.asarray(s) - level  # signed: a jump through the hexagon zone still counts
    if a[0] <= 0: return float(xrel[0])  # no triangle zone left: boundary is at/before the first sampled point (sulfur-rich)
    i = np.where((a[:-1] > 0) & (a[1:] <= 0))[0]
    return float(xrel[i[0]] + (xrel[i[0] + 1] - xrel[i[0]]) * a[i[0]] / (a[i[0]] - a[i[0] + 1])) if len(i) else float("nan")


def shape_map(values, n=40, n_mc=60, seed=0):
    """Shape class / index vs x over the substrate region with p05/p95 bands (MC over every ParamDef sigma, as core.uq)."""
    v = P.validate(DEFS, values)
    xrel = np.linspace(0.5, v["L_map_cm"], n)  # ponytail: starts 0.5 cm past the boat (pMoO3=0 in the boat cell)
    rng = np.random.default_rng(seed)
    runs = [_curve(v, xrel)]
    for _ in range(n_mc - 1):
        try:
            runs.append(_curve(uq.sample(DEFS, v, rng), xrel))
        except (ValueError, FloatingPointError):
            pass
    a = np.array(runs)
    s = a[0]
    return {"x_cm": (v["x_MoO3_cm"] + xrel).tolist(), "x_from_boat_cm": xrel.tolist(), "shape_index": s.tolist(),
            "p05": np.percentile(a, 5, 0).tolist(), "p95": np.percentile(a, 95, 0).tolist(),
            "shape": [str(c) for c in geometry(_r(s), v)[0]],
            "boundary_cm_from_boat": boundary_cm(xrel, s, v["s_boundary"]), "synthetic": True}


def _r(s):  # invert s=3(1-r)/(1+r); class only needs s
    return (3 - s) / (3 + s)


KNOBS = {"T_boat_S_C": 10.0, "T_boat_Mo_C": 10.0, "flow_sccm": 10.0, "x_S_boat_cm": 1.0}  # name -> step (flow in %)


def knob_sensitivity(values, knobs=KNOBS):
    """Finite-difference shift of the triangle-hexagon boundary (cm from MoO3 boat) per knob step, ranked by |shift|.
    If the perturbed boundary leaves the map (jumps to the first sample or vanishes: the whole substrate flips class), the step
    is halved up to 3 times; if it still leaves the map the entry is flagged valid=False and ranked last, because a jump to the
    map edge is not a sensitivity (it earlier produced a spurious -11.7 cm per 10 C for the sulfur boat)."""
    v = P.validate(DEFS, values)
    xrel = np.linspace(0.5, v["L_map_cm"], 200)
    b0 = boundary_cm(xrel, _curve(v, xrel), v["s_boundary"])
    res = []
    for k, step in knobs.items():
        rel = k == "flow_sccm"
        for f in (1.0, 0.5, 0.25, 0.125):
            st = step * f
            dv = v[k] * st / 100 if rel else st
            b1 = boundary_cm(xrel, _curve(v | {k: v[k] + dv}, xrel), v["s_boundary"])
            ok = np.isfinite(b1) and np.isfinite(b0) and b1 > xrel[0] + 1e-9 and b0 > xrel[0] + 1e-9
            if ok: break
        res.append({"knob": k, "step": f"{st:g}{'%' if rel else ''}", "shift_cm": b1 - b0, "valid": bool(ok),
                    "cm_per_unit": (b1 - b0) / (dv if not rel else st), "boundary_cm": b0})
    return sorted(res, key=lambda r: (not r["valid"], -abs(r["shift_cm"]) if np.isfinite(r["shift_cm"]) else 0))


def extras(values, n=40, n_mc=30):
    """Hook used by core.api.solve: shape vs position with bands, and the ranked knob sensitivities."""
    return {"shape_map": shape_map(values, n=n, n_mc=n_mc), "knob_sensitivity": knob_sensitivity(values)}


from contextlib import contextmanager  # noqa: E402


@contextmanager
def with_sigma(cfg, sigma=0.25):
    """Give dE_Mo_dft_eV its assumed 0.25 eV sigma while eq_model='dft_rosen' is used. A sigma on a ParamDef adds one RNG draw per MC sample for
    EVERY configuration, which changed the stored shape-benchmark MC stream, hence the scoped switch."""
    d = next(x for x in WDEFS if x.name == "dE_Mo_dft_eV")
    old, d.sigma = d.sigma, (sigma if cfg.get("eq_model") == "dft_rosen" else d.sigma)
    try:
        yield
    finally:
        d.sigma = old
