"""Photoreactor (batch / flow-cell slab), Tier 1 reduced model.
Track E (Oct 2026) status: the optical chain (wall T, Beer-Lambert, phi x absorbed photons) is compared with published ferrioxalate actinometry
(Saenz et al. 2024, doi 10.1016/j.heliyon.2024.e31309; phi from Hatchard & Parker 1956 Table 5) in bench/photoreactor/ (pre-registered, docs/prereg/track-e.md).
Not validated: lamp power -> irradiance (use lamp_geom = "measured" to bypass), the mixing cap (UNSOURCED heuristic), dT_K (UPPER BOUND, adiabatic-style, synthetic h_cool).
illum = "diffuse": cosine-weighted hemispherical incidence (exact unpolarised Fresnel + Snell, path 1/cos in the liquid); thin-limit absorbed fraction = A ln10 <1/cos(theta_liquid)> (< 2 A ln10 because refraction narrows the cone).
Chain: lamp radiant power -> irradiance at the vessel window (point or finite-line source, inverse-square / 1/d limits) -> wall losses
(2 Fresnel reflections at normal incidence + exponential wall absorption) -> photons entering -> Beer-Lambert absorption by reactant A
and product P (inner-filter: P absorbs, A is depleted) -> rate = quantum_yield x absorbed photon flux -> conversion X(t) by ODE, with the
rate capped by mixing (renewal of the irradiated skin once per mixing time). Lamp + absorbed-light heating gives a temperature rise.
Geometry assumptions (ponytail, each has a known ceiling):
  * monochromatic lamp (single wavelength; no spectrum, no filters); radiant power is the in-band power into 4pi for a point source.
  * point source: E = P/(4 pi d^2).  Line source of length L (uniform, every element radiates isotropically), receiver on the
    perpendicular bisector facing the axis: E = P / (4 pi d sqrt(d^2 + L^2/4)); this -> point formula for L << d and P/(2 pi d L) for L >> d.
    The same E is applied over the whole window (no 1/r^2 variation across the window, normal incidence, no reflector, no lamp shadowing).
  * vessel = flat slab: window area A x path length l; volume = A l (cuvette, flat flow cell, thin-film plate).
  * wall: Fresnel R = ((n1-n2)/(n1+n2))^2 on air->wall and wall->liquid, no multiple reflections; absorption alpha(lambda) is an
    exponential cutoff edge per material. All wall numbers are recalled textbook-level values, not fetched (flagged synthetic).
Regime: Da = r_photon / r_mix where r_photon = Phi N_abs (mol/s) and r_mix = reactant in the irradiated skin / t_mix. Skin depth
delta = min(l, 1/(ln10 sum eps c)). Optically thin: Da = t_mix / t_reaction. Da < 1 photon (light) limited, Da > 1 mass-transfer (mixing) limited.
Sourced values (opened and read, see presets/photoreactor__ferrioxalate_313nm_cuvette.json): ferrioxalate Phi range 1.25-0.9 over 250-500 nm,
0.006-0.20 M solutions, total absorption needed (IUPAC Tech Report, Kuhn/Braslavsky/Schmidt 2004, doi 10.1351/pac200476122105, via a PDF copy);
Phi = 1.24 at 313 nm and 6 mM absorbing >99% in 1 cm below 390 nm (Beilstein J Org Chem 2013, 9, 217, SI); Fe(phen)3 eps510 = 11100 M-1cm-1
(Goldstein & Rabani, doi 10.1016/j.jphotochem.2007.06.006, as quoted in a Copernicus BG 2026 SI)."""
import numpy as np
from scipy.integrate import solve_ivp
from core.dimensionless import classify
from core.params import ParamDef as P
from core.registry import Vessel, register

SYN = "synthetic"
H, C_LIGHT, NA, R_GAS = 6.62607015e-34, 2.99792458e8, 6.02214076e23, 8.314462618
LN10 = float(np.log(10))
# wall material: (refractive index, cutoff wavelength nm where alpha = 2.3/cm, edge width nm). Recalled, not fetched.
# quartz n = 1.485 (manufacturer value for a fused-quartz tube, Open Research Europe 2024, 4, 18, Table 1, doi 10.12688/openreseurope.16812.2); the
# cutoff and edge width of every row and all other n are still recalled, not fetched. Override n per run with the n_wall parameter.
WALLS = {"quartz": (1.485, 195.0, 10.0), "borosilicate": (1.47, 280.0, 12.0), "soda_lime": (1.52, 320.0, 15.0), "FEP": (1.34, 200.0, 20.0)}

DEFS = [
    P("P_rad_W", "Lamp radiant power in band (into 4pi)", "W", 1.0, 1e-3, 1e3, 0.1, source=SYN, group="lamp"),
    P("lambda_nm", "Emission wavelength (monochromatic)", "nm", 365.0, 200, 800, 0.005, group="lamp"),
    P("lamp_geom", "Lamp geometry: point, finite line (tube/strip) or measured irradiance", "", "point", choices=["point", "line", "measured"], group="lamp",
      help="point: P/(4 pi d^2); line: P/(4 pi d sqrt(d^2+L^2/4)); measured: use E_meas_mW_cm2 at the window (P_rad_W, dist_cm ignored)"),
    P("E_meas_mW_cm2", "Measured irradiance at the window (used if geometry = measured)", "mW/cm2", 0.5, 1e-4, 1e4, 0.05, group="lamp"),
    P("illum", "Illumination angular distribution at the window", "", "collimated", choices=["collimated", "diffuse"], group="lamp",
      help="collimated: normal incidence; diffuse: cosine-weighted hemispherical (isotropic field, e.g. integrating sphere), exact unpolarised Fresnel + Snell"),
    P("lamp_len_cm", "Line lamp length (used if geometry = line)", "cm", 10.0, 0.1, 200, 0.05, group="lamp"),
    P("dist_cm", "Lamp-to-vessel distance (axis/centre to outer wall)", "cm", 5.0, 0.5, 100, 0.2, sigma_rel=False, group="lamp"),
    P("eta_elec", "Radiant / electrical efficiency of the lamp", "", 0.3, 0.01, 1.0, 0.2, source=SYN, group="lamp"),
    P("f_heat", "Fraction of lamp waste heat reaching the vessel", "", 0.02, 0.0, 1.0, 0.5, source=SYN, group="lamp"),
    P("wall_mat", "Vessel wall material", "", "borosilicate", choices=list(WALLS), group="vessel",
      source="n and UV cutoff recalled, not fetched (module docstring)"),
    P("wall_mm", "Wall thickness (light path through the wall)", "mm", 2.0, 0.1, 10, 0.1, sigma_rel=False, group="vessel"),
    P("A_irr_cm2", "Illuminated window area (= liquid cross-section)", "cm2", 10.0, 0.1, 1000, 0.02, group="vessel"),
    P("path_cm", "Optical path length in the liquid", "cm", 1.0, 0.05, 20, 0.02, group="vessel"),
    P("n_liq", "Refractive index of the liquid", "", 1.33, 1.3, 1.6, 0.01, group="vessel"),
    P("n_wall", "Wall refractive index override (0 = use the material table)", "", 0.0, 0.0, 2.5, 0.0, group="vessel"),
    P("V_total_cm3", "Total liquid volume that the conversion is referred to (0 = window area x path)", "cm3", 0.0, 0.0, 1e5, 0.0, group="vessel"),
    P("c0_M", "Absorber / reactant A concentration", "M", 5e-4, 1e-6, 5, 0.03, group="chemistry"),
    P("eps_A", "Molar absorptivity of A at the lamp wavelength (decadic)", "1/M/cm", 5000.0, 1, 1e6, 0.05, source=SYN, group="chemistry"),
    P("eps_P", "Molar absorptivity of product P at the lamp wavelength (inner filter)", "1/M/cm", 500.0, 0, 1e6, 0.1, source=SYN, group="chemistry"),
    P("phi", "Quantum yield of A consumption", "", 0.5, 1e-3, 5, 0.1, source=SYN, group="chemistry"),
    P("Ea_phi_kJ_mol", "Apparent activation energy of the quantum yield (0 = athermal, 25 C reference)", "kJ/mol", 0.0, 0, 60, source=SYN, group="chemistry"),
    P("t_irr_s", "Irradiation time at which conversion is reported", "s", 600.0, 1, 1e6, group="operation"),
    P("stir_rpm", "Stir / circulation rate", "rpm", 500.0, 5, 3000, 0.05, group="operation"),
    P("mix_revs", "Mixing time in impeller revolutions (t_mix = mix_revs / N); UNSOURCED heuristic", "", 30.0, 5, 300, 0.3, source=SYN, group="operation",
      help="No literature source: the mixing cap (skin renewed once per t_mix) is an unsourced heuristic, not a validated correlation"),
    P("T_amb_C", "Ambient / coolant temperature", "C", 25.0, -20, 150, group="operation"),
    P("h_cool", "Heat-transfer coefficient to ambient", "W/m2/K", 20.0, 2, 500, 0.3, source=SYN, group="operation"),
]


def _wall(p):
    n, lc, w = WALLS[p["wall_mat"]]
    return (p["n_wall"] or n), max(2.3 * np.exp(-(p["lambda_nm"] - lc) / w), 0.01)  # n, alpha 1/cm


def _fresnel(n1, c1, n2, c2):
    """Unpolarised Fresnel reflectance for incidence cosines c1 (medium 1) and c2 (medium 2)."""
    rs = ((n1 * c1 - n2 * c2) / (n1 * c1 + n2 * c2)) ** 2
    rp = ((n1 * c2 - n2 * c1) / (n1 * c2 + n2 * c1)) ** 2
    return 0.5 * (rs + rp)


_GL = np.polynomial.legendre.leggauss(32)


def _diffuse(p):
    """Cosine-weighted hemispherical quadrature: (weights w_i summing to 1, wall transmittance T_i, cos of the refraction angle in the liquid)."""
    n, alpha = _wall(p)
    mu = 0.5 * (_GL[0] + 1)  # cos(theta_air) in (0,1)
    w = 2 * mu * 0.5 * _GL[1]  # int_0^1 2 mu dmu = 1
    s = np.sqrt(1 - mu ** 2)
    cw, cl = np.sqrt(1 - (s / n) ** 2), np.sqrt(1 - (s / p["n_liq"]) ** 2)
    T = (1 - _fresnel(1.0, mu, n, cw)) * (1 - _fresnel(n, cw, p["n_liq"], cl)) * np.exp(-alpha * p["wall_mm"] / 10 / cw)
    return w, T, cl


def wall_T(p):
    """Fraction of light transmitted air -> wall -> liquid (2 Fresnel losses x wall absorption, no multiple reflections).
    collimated: normal incidence. diffuse: cosine-weighted average over the incidence hemisphere."""
    if p["illum"] == "diffuse":
        w, T, _ = _diffuse(p)
        return float(np.sum(w * T))
    n, alpha = _wall(p)
    R1 = ((n - 1) / (n + 1)) ** 2
    R2 = ((n - p["n_liq"]) / (n + p["n_liq"])) ** 2
    return (1 - R1) * (1 - R2) * np.exp(-alpha * p["wall_mm"] / 10)


def _fabs(p, A):
    """Fraction of the photons entering the liquid that are absorbed at normal absorbance A (decadic, along the window normal).
    Diffuse: each direction travels A / cos(theta_liquid); weights = flux entering the liquid. Thin limit: A ln10 <1/cos(theta_liquid)>."""
    if p["illum"] == "diffuse":
        w, T, cl = _diffuse(p)
        return float(np.sum(w * T * (1 - 10 ** (-A / cl))) / np.sum(w * T))
    return 1 - 10 ** (-A)


def volume_cm3(p):
    return p["V_total_cm3"] or p["A_irr_cm2"] * p["path_cm"]


def irradiance(p):
    """W/cm2 at the window (before the wall)."""
    if p["lamp_geom"] == "measured":
        return p["E_meas_mW_cm2"] * 1e-3
    L = p["lamp_len_cm"] if p["lamp_geom"] == "line" else 0.0
    d = p["dist_cm"]
    return p["P_rad_W"] / (4 * np.pi * d * np.sqrt(d * d + L * L / 4))


def photons_in(p):
    """mol photons / s entering the liquid."""
    e_mol = H * C_LIGHT / (p["lambda_nm"] * 1e-9) * NA  # J per mol photons
    return irradiance(p) * p["A_irr_cm2"] * wall_T(p) / e_mol


def _state(p, X, Nin, t_mix):
    """Absorbed photons, photon-driven rate, mixing cap at conversion X. All mol, s."""
    cA, cP = p["c0_M"] * (1 - X), p["c0_M"] * X
    kA, kP = p["eps_A"] * cA, p["eps_P"] * cP  # 1/cm
    A = (kA + kP) * p["path_cm"]
    f = _fabs(p, A)
    Nabs = Nin * f * (kA / (kA + kP)) if kA + kP > 0 else 0.0  # photons absorbed by A only
    T = p["T_amb_C"] + 273.15 + _dT(p, Nin * f)
    phi = p["phi"] * np.exp(-p["Ea_phi_kJ_mol"] * 1e3 / R_GAS * (1 / T - 1 / 298.15))
    r_ph = phi * Nabs
    delta = min(p["path_cm"], 1 / (LN10 * (kA + kP))) if kA + kP > 0 else p["path_cm"]
    r_mix = cA * p["A_irr_cm2"] * delta / 1000 / t_mix
    return dict(A=A, f=f, Nabs=Nabs, r_ph=r_ph, r_mix=r_mix, T=T, phi=phi)


def _dT(p, Nabs_tot):
    e_mol = H * C_LIGHT / (p["lambda_nm"] * 1e-9) * NA
    Q = p["f_heat"] * p["P_rad_W"] * (1 / p["eta_elec"] - 1) + Nabs_tot * e_mol  # W; absorbed light fully thermalised = upper bound
    return Q / (p["h_cool"] * 2 * p["A_irr_cm2"] * 1e-4)


def _rate(s):
    return 1 / (1 / s["r_ph"] + 1 / s["r_mix"]) if s["r_ph"] > 0 else 0.0


def core(p):
    Nin = photons_in(p)
    t_mix = p["mix_revs"] / (p["stir_rpm"] / 60)
    n0 = p["c0_M"] * volume_cm3(p) / 1000
    s0 = _state(p, 0.0, Nin, t_mix)
    r0 = _rate(s0)
    f = lambda t, y: [_rate(_state(p, min(max(y[0], 0.0), 1.0), Nin, t_mix)) / n0]
    half = lambda t, y: y[0] - 0.5
    half.direction = 1
    sol = solve_ivp(f, (0, p["t_irr_s"]), [0.0], events=half, rtol=1e-7, atol=1e-10)
    X = float(sol.y[0, -1])
    if len(sol.t_events[0]):
        t_half = float(sol.t_events[0][0])
    else:  # not yet half converted at t_irr: keep integrating until it is (rate stays > 0)
        half.terminal = True
        s2 = solve_ivp(f, (p["t_irr_s"], p["t_irr_s"] + 1e4 * n0 / r0), [X], events=half, rtol=1e-7, atol=1e-10)
        t_half = float(s2.t_events[0][0]) if len(s2.t_events[0]) else float("inf")
    return dict(Nin=Nin, s0=s0, r0=r0, t_mix=t_mix, n0=n0, X=min(max(X, 0.0), 1.0), t_half=t_half)


def tier0(p):
    c = core(p)
    s = c["s0"]
    Da = s["r_ph"] / s["r_mix"]
    r, mg = classify(Da)
    return r, mg, {"Da_mix": Da, "A_total": s["A"], "f_abs_total": s["f"], "t_mix_s": c["t_mix"], "t_reaction_s": c["n0"] / s["r_ph"],
                   "photon_in_umol_s": c["Nin"] * 1e6, "light_limited": float(Da < 1)}


def solve(p):
    c = core(p)
    s = c["s0"]
    V = volume_cm3(p) / 1000
    Da = s["r_ph"] / s["r_mix"]
    return {"T_K": s["T"], "photon_flux_in_umol_s": c["Nin"] * 1e6, "photon_flux_absorbed_umol_s": s["Nabs"] * 1e6,
            "fraction_absorbed": s["f"], "absorbance_total": s["A"], "wall_transmission": wall_T(p),
            "irradiance_mW_cm2": irradiance(p) * 1e3, "rate_M_s": c["r0"] / V, "rate_photon_limit_M_s": s["r_ph"] / V,
            "rate_mixing_cap_M_s": s["r_mix"] / V, "conversion_t_irr": c["X"], "t_half_s": c["t_half"], "t_mix_s": c["t_mix"],
            "Da_mix": Da, "light_limited": float(Da < 1), "mass_limited": float(Da >= 1), "dT_K": s["T"] - p["T_amb_C"] - 273.15}


KNOBS = ("dist_cm", "wall_mm", "P_rad_W", "c0_M")


def flux_density(p, z_cm):
    """Photon flux density (umol s-1 cm-2, along the window normal) at depth z in the liquid at X = 0 (Beer-Lambert, A-only absorber)."""
    k = p["eps_A"] * p["c0_M"]  # 1/cm
    q0 = photons_in(p) / p["A_irr_cm2"] * 1e6
    z = np.asarray(z_cm, float)
    if p["illum"] == "diffuse":
        w, T, cl = _diffuse(p)
        return q0 * np.sum(w[:, None] * T[:, None] * 10 ** (-k * z[None, :] / cl[:, None]), axis=0) / np.sum(w * T)
    return q0 * 10 ** (-k * z)


def _band(p, n=200, seed=0):
    """Photon-flux-vs-depth curve with p05/p50/p95 over the ParamDef sigmas (same sampler as the Monte-Carlo passport)."""
    from core import uq
    rng = np.random.default_rng(seed)
    z = np.linspace(0, p["path_cm"], 41)
    runs = [flux_density(p, z)] + [flux_density(uq.sample(DEFS, p, rng), z) for _ in range(n - 1)]
    a = np.array(runs)
    return {"x": z.tolist(), "x_label": "Depth in liquid from the window", "x_unit": "cm", "y_label": "Photon flux density", "y_unit": "umol s-1 cm-2",
            "p05": np.percentile(a, 5, axis=0).tolist(), "p50": np.percentile(a, 50, axis=0).tolist(), "p95": np.percentile(a, 95, axis=0).tolist(),
            "n_mc": n, "note": "initial state (no conversion); band = 1-sigma ParamDef uncertainties incl. synthetic ones; Beer-Lambert with the A-only absorber"}


def extras(p):
    """Which knob matters most. Local elasticity d ln(rate)/d ln(x) (+-5%) and the change in ln(rate) for a 1-sigma move of that knob."""
    d = {x.name: x for x in DEFS}
    r0 = solve(p)["rate_M_s"]
    out = {}
    for k in KNOBS:
        up, dn = 1.05, 1 / 1.05
        el = (np.log(solve(p | {k: p[k] * up})["rate_M_s"]) - np.log(solve(p | {k: p[k] * dn})["rate_M_s"])) / (np.log(up) - np.log(dn))
        sg = d[k].sigma * (abs(p[k]) if d[k].sigma_rel else 1.0)
        hi = np.log(solve(p | {k: min(p[k] + sg, d[k].hi)})["rate_M_s"] / r0)
        lo = np.log(solve(p | {k: max(p[k] - sg, d[k].lo)})["rate_M_s"] / r0)
        out[k] = {"elasticity": float(el), "sigma": float(sg), "dln_rate_per_sigma": float(max(abs(hi), abs(lo)))}
    best = max(out, key=lambda k: out[k]["dln_rate_per_sigma"])
    return {"sensitivity": out, "photon_flux_vs_depth": _band(p), "most_important_per_sigma": best,
            "notes": ["mixing cap: UNSOURCED heuristic (skin renewed once per mix_revs/N); no literature source found",
                      "dT_K: upper bound (all absorbed light thermalised, lamp waste heat fraction f_heat synthetic, synthetic h_cool); not validated",
                      "validated only for the optical chain (wall T, Beer-Lambert, phi x absorbed photons) against Saenz 2024 actinometry, see bench/photoreactor/results.json"],
            "most_important_elasticity": max(out, key=lambda k: abs(out[k]["elasticity"])),
            "text": f"largest effect for a 1-sigma move: {best} (dln rate {out[best]['dln_rate_per_sigma']:.3f}); "
                    "elasticity = local power-law exponent of rate vs the knob"}


UNITS = {"photon_flux_in_umol_s": "umol/s", "photon_flux_absorbed_umol_s": "umol/s", "fraction_absorbed": "", "absorbance_total": "",
         "wall_transmission": "", "irradiance_mW_cm2": "mW/cm2", "rate_M_s": "M/s", "rate_photon_limit_M_s": "M/s",
         "rate_mixing_cap_M_s": "M/s", "conversion_t_irr": "", "t_half_s": "s", "t_mix_s": "s", "Da_mix": "", "light_limited": "",
         "mass_limited": "", "dT_K": "K"}

register(Vessel("photoreactor", "Photoreactor (batch / flow cell)", DEFS, tier0, solve, UNITS,
                lambda p: f"{p['lamp_geom']}_lamp,{p['dist_cm']:.3g}cm,{p['wall_mat']}", "tier1:lamp-geometry+beer-lambert+mixing-cap",
                ["optically thin rate linear in power", "inverse-square point source", "Beer-Lambert limit",
                 "ferrioxalate actinometry (Phi, total absorption)"], extras=extras))
