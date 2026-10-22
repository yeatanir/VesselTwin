"""Equilibrium (Wulff) shape of monolayer MoS2 from the Delta-mu_S-dependent edge energies of Momeni et al., npj 2D Mater. Appl. 2, 27 (2018),
doi:10.1038/s41699-018-0072-5, Supplementary Information (41699_2018_72_MOESM1_ESM.pdf), checked against the page images:
 p.7: gamma_AC = 0.75 (S14); gamma_ZZMo = 0.2184 dmu + 1.03 (S15); gamma_ZZS = -0.2041 dmu + 0.44 (S16); gamma_ZZS2 = -0.4286 dmu + 0.2 (S17); eV/Angstrom,
      dmu = Delta mu_S in eV, 'fitted from Ref. 1' (printed 'Ref. 1' on p.7 and 'Ref. 9' on p.4-5 for the first-principles edge energies; the DFT
      level of that reference is NOT known to us).
 p.5: S6-S7 anisotropy a(theta) = gamma(theta)/|gamma|, gamma(theta) = |gamma| cos(theta + C): a mixture of armchair and zigzag segments between the
      cusps, so the Wulff shape of the cusped gamma(theta) is the intersection of the half-planes of the facet energies (done below; the smoothed
      a(theta) of S8-S13 is a phase-field regularisation, not used).
 p.5: 'Delta mu_S (in eV) = 0.8 - 12 u, valid for small supersaturations' (assumed by the authors); p.4: u = (c - c_eq) Omega (Omega = molar volume of
      MoS2, Table S3: Omega 3.2e-5 m3/mol, c_eq 0.4 mol/m3); PDF p.10 (Fig. S8 caption): critical saturation u_c = 0.251 (a nucleation trigger, not a shape rule).
 p.4: with increasing Delta mu_S the equilibrium shape goes dodecagon (Mo-rich) -> hexagon / quasi-hexagon -> triangle (S-rich).
Pre-registered choices (docs/prereg/track-i.md): facets ZZMo at normals 0/120/240 deg, ZZS-type at 60/180/300, AC at 30+60k; the S-type zigzag energy is
min(gamma_ZZS, gamma_ZZS2) (lowest-energy S-terminated edge wins; ASSUMPTION); energies floored at 0.01 eV/A (the linear fits go negative for
dmu > 0.47 (ZZS2) / 2.2 (ZZS): outside any fit validity, unknown); class from s = (L_Mo - L_S)/(L_Mo + L_S) with the repo thresholds; AC length share
> 5 % flags a dodecagon (labelled hexagon-like in the benchmark's vocabulary, which has no dodecagon).
Two maps to dmu (primary = 'kT', fixed before scoring):
 kT    : dmu = Dmu_S_std_eV + 1/2 [g_S2(T) - g_S2(1073.15 K)] + 1/2 kT ln(pS2/1 bar)   (S2 gas relative to E(S8 ring)/8 as proxy of bulk S; the
         wulff.p_eq 'kink' convention; Dmu_S_std = -0.796 eV, MACE-MP-0 + JANAF, +-0.3 eV)
 bridge: u = Omega (c_MoO3 - c_eq), c_MoO3 = pMoO3/(R T) (Mo-precursor concentration), dmu = 0.8 - 12 u (the authors' own, taken literally)."""
import numpy as np

KB = 8.617333e-5  # eV/K
R = 8.314462618
OMEGA, C_EQ, U_C = 3.2e-5, 0.4, 0.251  # m3/mol, mol/m3 (SI Table S3, p.4), critical u (SI Fig. S8 caption, PDF p.10)
FLOOR = 0.01  # eV/A
AC_FLAG = 0.05


def edge_energies(dmu):
    """(gamma_AC, gamma_ZZMo, gamma_ZZS, gamma_ZZS2) in eV/A, SI Eqs. S14-S17 as printed."""
    return 0.75, 0.2184 * dmu + 1.03, -0.2041 * dmu + 0.44, -0.4286 * dmu + 0.2


def _lengths(h):
    """Edge lengths of the polygon {x : n_i . x <= h_i}; h dict normal-angle(deg) -> support value. Line i is clipped by every other half-plane."""
    th = np.radians(list(h)); hv = np.array(list(h.values()))
    N = np.stack([np.cos(th), np.sin(th)], 1)
    out = []
    for i in range(len(hv)):
        t_hat = np.array([-N[i, 1], N[i, 0]]); x0 = hv[i] * N[i]
        lo, hi = -np.inf, np.inf
        for j in range(len(hv)):
            if j == i: continue
            a, b = N[j] @ t_hat, hv[j] - N[j] @ x0  # a t <= b
            if abs(a) < 1e-12:
                if b < 0: lo, hi = 1, 0
            elif a > 0: hi = min(hi, b / a)
            else: lo = max(lo, b / a)
        out.append(max(hi - lo, 0.0))
    return np.array(out)


def wulff_edges(dmu, v2=True):
    """-> dict L_Mo, L_S, L_AC (A per unit scale; sums over the three equivalent facets each), gammas used.
    v2 (corrected after scoring, Addendum B): Cao, Shen, Liang, Chen & Shu, J. Phys. Chem. C 119, 4294 (2015), p.4296: 'ZZ-Mo and ZZ-S2 have the same
    edge orientation' (the Mo-edge orientation, Mo- and S-terminated) and 'ZZ-S and ZZ-Mo2 have the same edge orientation' (S-edge orientation):
    Mo-orientation energy = min(ZZMo, ZZS2), S-orientation energy = ZZS. v1 (as first registered, WRONG): S-orientation = min(ZZS, ZZS2)."""
    g_ac, g_mo, g_s, g_s2 = (max(g, FLOOR) for g in edge_energies(dmu))
    gMo, gS = (min(g_mo, g_s2), g_s) if v2 else (g_mo, min(g_s, g_s2))
    h = {}
    for k in range(6):
        h[60.0 * k] = gMo if k % 2 == 0 else gS
        h[60.0 * k + 30.0] = g_ac
    L = _lengths(h)
    ang = list(h)
    sel = lambda f: float(sum(L[i] for i, a in enumerate(ang) if f(a)))
    return {"L_Mo": sel(lambda a: a % 120 == 0), "L_S": sel(lambda a: a % 120 == 60), "L_AC": sel(lambda a: a % 60 == 30),
            "gamma": {"AC": g_ac, "ZZMo": g_mo, "ZZS_eff": gS}}


def shape_from_dmu(dmu, s_hex=0.15, s_tri=0.95, v2=True):
    """-> (class, s, dodecagon_flag). class in {hexagon, truncated_triangle, triangle_Mo, triangle_S} (repo vocabulary)."""
    e = wulff_edges(dmu, v2)
    tot = e["L_Mo"] + e["L_S"]
    s = (e["L_Mo"] - e["L_S"]) / tot if tot > 1e-12 else 0.0
    cls = "hexagon" if abs(s) < s_hex else ("truncated_triangle" if abs(s) < s_tri else ("triangle_Mo" if s > 0 else "triangle_S"))
    return cls, s, bool(e["L_AC"] > AC_FLAG * (tot + e["L_AC"]))


def dmu_kT(v, pS, T_K):
    """Primary map. v needs Dmu_S_std_eV and mu_S_eV is NOT used (no extra offset)."""
    from vessels.cvd_tube import wulff
    T = np.asarray(T_K, float)
    return v["Dmu_S_std_eV"] + 0.5 * (wulff._gS2_eV(T) - wulff._gS2_eV(wulff._T_REF)) + 0.5 * KB * T * np.log(np.maximum(pS, 1e-300) / 1e5)


def dmu_bridge(pM, T_K):
    """Authors' bridge taken literally with c = p_MoO3 / (R T). -> (dmu, u)."""
    u = OMEGA * (np.asarray(pM, float) / (R * np.asarray(T_K, float)) - C_EQ)
    return 0.8 - 12 * u, u


def shape_index(v, pM, pS, T_K, v2=True):
    """Shape index s (array in, array out) for the momeni_eq edge model, using v['momeni_mapping'] in {'kT', 'bridge'}."""
    pM, pS, T = np.broadcast_arrays(np.asarray(pM, float), np.asarray(pS, float), np.asarray(T_K, float))
    dmu = dmu_kT(v, pS, T) if v["momeni_mapping"] == "kT" else dmu_bridge(pM, T)[0]
    return np.vectorize(lambda d: shape_from_dmu(d, v["s_hex"], v["s_tri"], v2)[1])(dmu)
