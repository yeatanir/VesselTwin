"""Stirred flask, Tier 1: stir bar -> power -> macro (Grenville-Nienow theta95), micro (engulfment, Baldyga-Bourne) and meso
(inertial-convective plume breakup) mixing times for a semi-batch feed, Damkohler regime call, Villermaux-Dushman segregation index and
a competitive-consecutive/parallel selectivity from the incorporation model, wall heat removal with a hotspot flag, validity flags
(vortex, bar torque, bar fit), volume scaling, and a 'mixing-sensitive?' verdict with the knob that matters.
Sources: see vd.py (Villermaux-Dushman) and solvents.py (rho, mu, cp(T)). Time-scale forms: Torbacke thesis (KTH 2004, diva2:8967)
Eq 2.12-2.18 citing Baldyga & Bourne 1999 / Baldyga, Bourne & Yang 1993: tau_M = C sqrt(nu/eps) with C 3.5-17.3 (17.3 = 1/E,
E = 0.058 sqrt(eps/nu)); tau_IC = A (Lambda^2/eps)^(1/3), A 1-2; plume area Q_feed/u_b = pi dD^2/4 (Eq 5.1); meso controls when tau_meso/tau_M >> 1.
Not found in the literature (searched Oct 2026): a power number or mixing time for magnetic stir bars in round-bottom flasks. Np(Re),
the Grenville constant (baffled impeller tanks) and the stir-bar slip/torque numbers are therefore flagged synthetic.
Context for the verdict: Noel et al., 'Stirring the Debate', ACS Cent Sci 2025 argue mixing matters for scale-up, fast, multiphase and
exothermic reactions; the 329-reaction stirred-vs-standing study they rebut (Liu/Huang et al., Synlett 2024, doi 10.1055/a-2384-7220)
found little average effect.
ponytail: spherical flask of diameter T, bar length = impeller diameter, single scalar local-eps ratio at the feed point, meso time
replaces the engulfment time when larger, heat generation is feed-controlled (upper bound), U from three series resistances."""
import numpy as np
from scipy.optimize import brentq
from core.dimensionless import Regime, classify
from core.params import ParamDef as P
from core.registry import Vessel, register
from vessels.flask import solvents
from vessels.flask.vd import VD_SETS, incorporation, segregation_index  # noqa: F401  (segregation_index re-exported)

SYN = "synthetic"
G = 9.81
# solvent: (rho kg/m3, mu Pa s) at 25 C; mu from CRC Handbook 85th ed. (Lide 2004) as tabulated at accudynetest.com/visc_table.html
# (rho: handbook-level; the temperature-dependent values in solvents.props are fits to the published tables listed there)
SOLVENTS = {"water": (997, 0.89e-3), "ethanol": (785, 1.07e-3), "DMF": (944, 0.80e-3), "ethylene_glycol": (1110, 16.1e-3),
            "THF": (880, 0.46e-3), "toluene": (862, 0.56e-3), "acetonitrile": (777, 0.34e-3), "DMSO": (1096, 1.99e-3),
            "glycerol": (1260, 0.934)}

DEFS = [
    P("volume_mL", "Flask nominal volume", "mL", 100.0, 5, 5000, group="geometry"),
    P("fill_frac", "Fill fraction", "", 0.5, 0.05, 0.9, group="geometry"),
    P("bar_mm", "Stir bar length", "mm", 25.0, 3, 100, group="geometry"),
    P("solvent", "Solvent", "", "water", choices=list(SOLVENTS), group="operation"),
    P("stir_rpm", "Stir rate", "rpm", 400.0, 10, 2000, 0.05, group="operation"),
    P("T_C", "Temperature (sets solvent rho, mu, cp from published fits; VD k2 stays at 25 C)", "C", 25.0, -20, 150, group="operation"),
    P("mu_factor", "Viscosity multiplier on the solvent (emulates sucrose/glycerol-water, or dilution)", "", 1.0, 0.05, 1e4, group="operation"),
    P("k2_M_s", "Desired reaction rate constant (2nd order, A + B -> R)", "1/M/s", 10.0, 1e-6, 1e12, 0.3, source=SYN, group="reaction"),
    P("C0_M", "Bulk concentration of reagent A", "M", 0.1, 1e-4, 10, group="reaction"),
    P("sel.scheme", "Selectivity scheme: consecutive (R + B -> S) or parallel (C + B -> S)", "", "consecutive",
      choices=["consecutive", "parallel"], group="reaction"),
    P("sel.k_side_M_s", "Undesired reaction rate constant k_side", "1/M/s", 1.0, 1e-6, 1e12, 0.3, source=SYN, group="reaction"),
    P("sel.c_comp_M", "Bulk competitor C (parallel scheme only)", "M", 0.1, 1e-4, 10, group="reaction"),
    P("feed.time_s", "Semi-batch addition time of the feed", "s", 600.0, 1, 86400, 0.1, group="addition"),
    P("feed.vol_frac", "Feed volume as fraction of the liquid charge", "", 0.05, 0.001, 1.0, group="addition"),
    P("feed.c_M", "Feed concentration of reagent B", "M", 1.0, 1e-4, 20, group="addition"),
    P("feed.eps_ratio", "Local/mean energy dissipation at the feed point (<1 surface feed, >1 near the bar)", "", 1.0, 0.05, 20, 0.3,
      source=SYN, group="addition", help="Baldyga & Bourne: feed-point eps differs from the mean; no stir-bar data found"),
    P("heat.dH_kJ_mol", "Reaction enthalpy of the desired reaction (negative = exothermic)", "kJ/mol", -50.0, -500, 200, 0.1, source=SYN, group="heat"),
    P("heat.h_in_W_m2K", "Inside film coefficient (liquid to glass)", "W/m2/K", 500.0, 20, 5000, 0.3, source=SYN, group="heat"),
    P("heat.h_out_W_m2K", "Outside film coefficient (glass to bath/air)", "W/m2/K", 300.0, 5, 3000, 0.3, source=SYN, group="heat",
      help="stirred bath ~300, still air ~10"),
    P("heat.t_glass_mm", "Glass wall thickness", "mm", 2.0, 0.5, 6, group="heat"),
    P("heat.k_glass", "Glass conductivity", "W/m/K", 1.2, 0.5, 2, source="borosilicate 3.3 datasheet value, recalled not fetched", group="heat"),
    P("heat.dT_allow_K", "Allowed liquid-to-bath temperature difference", "K", 10.0, 0.5, 100, group="heat"),
    P("heat.dT_hot_K", "Local plume temperature rise that counts as a hotspot", "K", 5.0, 0.5, 100, source=SYN, group="heat"),
    P("bar.slip", "Fluid angular speed / bar angular speed (vortex estimate)", "", 0.5, 0.1, 1.0, source=SYN, group="model"),
    P("bar.torque_max_mN_m", "Magnetic coupling torque before the bar decouples", "mN m", 10.0, 0.5, 200, source=SYN, group="model"),
    P("Np_inf", "Power number, turbulent limit", "", 0.5, 0.05, 3, 0.3, source=SYN, group="model"),
    P("Kp", "Laminar power constant (Np += Kp/Re)", "", 70.0, 1, 500, 0.3, source=SYN, group="model"),
    P("Re_c", "Re scale below which macromixing slows (1+Re_c/Re)", "", 2000.0, 100, 1e5, 0.3, source=SYN, group="model"),
    P("K_theta", "Grenville-Nienow constant in N theta95 = K Np^-1/3 (T/d)^2 (baffled impeller tanks)", "", 5.3, 3, 8, 0.1,
      source="Grenville & Nienow, Handbook of Industrial Mixing 2004 (recalled, not verified; not stir-bar data)", group="model"),
    P("C_micro", "Micromixing time constant, t_M = C sqrt(nu/eps)", "", 17.3, 3.5, 20, 0.2,
      source="Baldyga & Bourne 1999; literature range 3.5-17.3 (Torbacke 2004 Eq 2.15)", group="model"),
    P("A_meso", "Inertial-convective mesomixing constant, t = A (Lambda^2/eps)^1/3", "", 1.5, 1, 2, 0.2,
      source="Baldyga & Bourne 1999, A = 1-2 (Torbacke 2004 Eq 2.17)", group="model"),
    P("ub_factor", "Bulk velocity at the feed point / bar tip speed (pi N d)", "", 0.5, 0.05, 1.5, 0.3, source=SYN, group="model"),
    P("Da_crit", "Mixing-time/reaction-time ratio above which the product distribution is mixing-sensitive", "", 0.1, 0.01, 1, source=SYN,
      group="verdict", help="rule of thumb: mixing matters when t_mix is within ~10x of t_reaction"),
    P("feed_macro_factor", "Feed time must exceed this multiple of theta95", "", 3.0, 1, 50, source=SYN, group="verdict"),
    P("vd.c_H_M", "VD: acid concentration (as H+)", "M", 0.03, 1e-3, 5, group="villermaux-dushman",
      source="tmixer_lowRe set, arXiv:1909.11868 SI Tab S1 (see vd.VD_SETS)"),
    P("vd.c_B_M", "VD: borate H2BO3- in bulk", "M", 0.09, 1e-3, 1, group="villermaux-dushman", source="same, PMC9866573 Table 1"),
    P("vd.c_I_M", "VD: iodide in bulk", "M", 0.032, 1e-3, 1, group="villermaux-dushman", source="arXiv:1909.11868 SI Tab S1"),
    P("vd.c_IO3_M", "VD: iodate in bulk", "M", 0.006, 1e-4, 0.1, group="villermaux-dushman", source="arXiv:1909.11868 SI Tab S1"),
]


def _cap(V, Vl):
    """Spherical flask: diameter T, liquid depth h, free-surface radius, wetted wall area."""
    R = (3 * V / (4 * np.pi)) ** (1 / 3)
    h = brentq(lambda h: np.pi * h * h * (3 * R - h) / 3 - Vl, 0, 2 * R)
    return 2 * R, h, np.sqrt(max(h * (2 * R - h), 0.0)), 2 * np.pi * R * h


def _mix(p):
    pr = solvents.props(p["solvent"], p["T_C"], p["mu_factor"])
    rho, mu = pr["rho"], pr["mu"]
    nu = mu / rho
    V = p["volume_mL"] * 1e-6
    Vl = V * p["fill_frac"]
    T, h, r_s, A_wet = _cap(V, Vl)
    d, N = p["bar_mm"] / 1000, p["stir_rpm"] / 60
    if d > 0.9 * T:
        raise ValueError(f"stir bar {d*1e3:.0f} mm does not fit a {T*1e3:.0f} mm flask")
    Re = N * d * d / nu
    Np = p["Np_inf"] + p["Kp"] / Re
    eps = Np * N**3 * d**5 / Vl  # W/kg
    theta95 = p["K_theta"] * Np ** (-1 / 3) * (T / d) ** 2 / N * (1 + p["Re_c"] / Re)
    t_micro = p["C_micro"] * np.sqrt(nu / eps)
    eps_f = eps * p["feed.eps_ratio"]
    t_micro_f = p["C_micro"] * np.sqrt(nu / eps_f)
    Vf = p["feed.vol_frac"] * Vl
    Qf = Vf / p["feed.time_s"]
    u_b = p["ub_factor"] * np.pi * N * d
    Lam2 = 4 * Qf / (np.pi * u_b)  # plume cross-section area / (pi/4), Torbacke Eq 5.1
    t_meso = p["A_meso"] * (Lam2 / eps_f) ** (1 / 3)
    return dict(nu=nu, rho=rho, mu=mu, cp=pr["cp"], in_range=pr["in_range"], Re=Re, Np=Np, eps=eps, theta95=theta95, t_micro=t_micro,
                t_micro_f=t_micro_f, t_meso=t_meso, T_flask=T, depth=h, r_s=r_s, A_wet=A_wet, Vl=Vl, Vf=Vf, Qf=Qf, u_b=u_b,
                eps_f=eps_f, d=d, N=N)


def _sens(p, m=None):
    """Mixing-sensitivity index S (>1 = mixing-sensitive) from time-scale ratios; cheap, no ODE."""
    m = m or _mix(p)
    t_rxn = 1 / (p["k2_M_s"] * p["C0_M"])
    s_mm = max(m["t_micro_f"], m["t_meso"]) / (t_rxn * p["Da_crit"])
    s_macro = p["feed_macro_factor"] * m["theta95"] / p["feed.time_s"]
    return max(s_mm, s_macro), s_mm, s_macro, t_rxn


def _knobs(p, S):
    """Re-evaluate S with one knob changed; returns {name: (code, S_new)}. Viscosity = warmer/dilute solvent (mu x0.5)."""
    out = {}
    for code, name, kw in ((1, "stir_rpm x1.5", {"stir_rpm": p["stir_rpm"] * 1.5}), (2, "bar_mm x1.25", {"bar_mm": p["bar_mm"] * 1.25}),
                           (3, "feed.time_s x2", {"feed.time_s": p["feed.time_s"] * 2}), (4, "viscosity x0.5", {"mu_factor": p["mu_factor"] * 0.5})):
        try:
            out[name] = (code, _sens(p | kw)[0])
        except ValueError:  # bar no longer fits
            pass
    return out


def _heat(p, m):
    """Adiabatic rise, local plume rise, wall cooling. Conc in M -> mol/m3 x1e3."""
    rc = m["rho"] * m["cp"]
    q_per_mol = max(-p["heat.dH_kJ_mol"], 0.0) * 1e3
    A0, B0 = p["C0_M"], p["feed.c_M"]
    n_lim = min(B0 * m["Vf"], A0 * m["Vl"]) * 1e3  # mol
    dT_ad = q_per_mol * n_lim / (rc * (m["Vl"] + m["Vf"]))
    dT_mix = q_per_mol * (A0 * B0 / (A0 + B0)) * 1e3 / rc  # feed + stoichiometric bulk, adiabatic
    t_rxn = 1 / (p["k2_M_s"] * p["C0_M"])
    dT_plume = dT_mix * (1 - np.exp(-max(m["t_micro_f"], m["t_meso"]) / t_rxn))
    U = 1 / (1 / p["heat.h_in_W_m2K"] + p["heat.t_glass_mm"] * 1e-3 / p["heat.k_glass"] + 1 / p["heat.h_out_W_m2K"])
    q_gen = q_per_mol * B0 * m["Vf"] * 1e3 / p["feed.time_s"]  # W, feed-controlled upper bound
    UA = U * m["A_wet"]
    return dict(dT_ad=dT_ad, dT_mix=dT_mix, dT_plume=dT_plume, U=U, q_gen=q_gen, dT_bulk=q_gen / UA,
                cooling_ratio=q_gen / (UA * p["heat.dT_allow_K"]), Bi_glass=U * p["heat.t_glass_mm"] * 1e-3 / p["heat.k_glass"])


def _flags(p, m):
    omega = p["bar.slip"] * 2 * np.pi * m["N"]
    vortex = (omega * m["r_s"]) ** 2 / (2 * G) / m["depth"]  # solid-body paraboloid depth at the wall / liquid depth
    torque = m["eps"] * m["rho"] * m["Vl"] / (2 * np.pi * m["N"]) * 1e3  # mN m
    return dict(vortex=vortex, torque=torque, decouple=torque / p["bar.torque_max_mN_m"], Fr=m["N"] ** 2 * m["d"] / G,
                bar_over_surface=m["d"] / (2 * m["r_s"]))


def critical_feed(p, m=None):
    """Largest addition rate (m3/s) before the feed becomes mixing-sensitive, and the controlling scale. 0 = sensitive at any rate."""
    m = m or _mix(p)
    t_rxn = 1 / (p["k2_M_s"] * p["C0_M"])
    t_crit = p["Da_crit"] * t_rxn
    if m["t_micro_f"] > t_crit:
        return 0.0, "micromixing"
    Lam2 = m["eps_f"] * (t_crit / p["A_meso"]) ** 3
    q_meso = np.pi / 4 * m["u_b"] * Lam2
    q_macro = m["Vf"] / (p["feed_macro_factor"] * m["theta95"])
    return (q_meso, "mesomixing") if q_meso < q_macro else (q_macro, "macromixing")


def scale_up(p, V_mL, mode="eps"):
    """Same geometry scaled to V_mL (bar and flask scale with V^1/3): mode 'rpm' = constant stir rate, 'eps' = constant power per mass."""
    f = (V_mL / p["volume_mL"]) ** (1 / 3)
    q = p | {"volume_mL": V_mL, "bar_mm": p["bar_mm"] * f}
    if mode == "eps":
        e0 = _mix(p)["eps"]
        q["stir_rpm"] = brentq(lambda N: _mix(q | {"stir_rpm": N})["eps"] - e0, 1e-3, p["stir_rpm"] * 10)
    m = _mix(q)
    return dict(volume_mL=V_mL, bar_mm=q["bar_mm"], stir_rpm=q["stir_rpm"], eps=m["eps"], t_micro=m["t_micro"], theta95=m["theta95"],
                A_over_V=m["A_wet"] / m["Vl"])


def verdict(p):
    """Human-readable 'mixing-sensitive?' answer with margin and the knob that helps most."""
    m = _mix(p)
    S, s_mm, s_macro, _ = _sens(p, m)
    q_c, why = critical_feed(p, m)
    kn = _knobs(p, S)
    best = min(kn, key=lambda k: kn[k][1]) if kn else None
    head = f"mixing-sensitive (margin {1/S:.2f})" if S > 1 else f"not mixing-sensitive (margin {1/S:.1f}x)"
    rate = f"above {q_c*6e7:.3g} mL/min" if q_c > 0 else "at any addition rate"
    return {"sensitive": S > 1, "margin": 1 / S, "text": f"{head}; limited by {why}, sensitive {rate} (now {m['Qf']*6e7:.3g} mL/min); "
            f"bar {p['bar_mm']:.0f} mm at {p['stir_rpm']:.0f} rpm" + (f"; best knob {best} (S {S:.2f} -> {kn[best][1]:.2f})" if best else ""),
            "knob": best, "critical_feed_mL_min": q_c * 6e7, "limit": why}


def solve(p):
    m = _mix(p)
    T = p["T_C"] + 273.15
    Xs, Y = segregation_index(p, m["t_micro"], T)
    S, s_mm, s_macro, t_rxn = _sens(p, m)
    q_c, _ = critical_feed(p, m)
    kn = _knobs(p, S)
    best = min(kn.values(), key=lambda v: v[1]) if kn else (0, S)
    t_eff = max(m["t_micro_f"], m["t_meso"])
    k1, k2s, A0, B0 = p["k2_M_s"], p["sel.k_side_M_s"], p["C0_M"], p["feed.c_M"]
    kw = dict(scheme=p["sel.scheme"], C0=p["sel.c_comp_M"] if p["sel.scheme"] == "parallel" else 0.0)
    X = incorporation(k1, k2s, A0, B0, 1 / t_eff, **kw)
    Xp = incorporation(k1, k2s, A0, B0, 1e4 * max(k1, k2s) * max(A0, B0), **kw)  # perfect micromixing reference
    h, f = _heat(p, m), _flags(p, m)
    return {"T_K": T, "Re": m["Re"], "Np": m["Np"], "epsilon_W_kg": m["eps"], "t_mix95_s": m["theta95"], "t_micro_s": m["t_micro"],
            "Da_macro": m["theta95"] / t_rxn, "Da_micro": m["t_micro"] / t_rxn, "Xs_villermaux_dushman": Xs,
            "c_local_over_feed": float(np.exp(-t_rxn / m["t_micro"])),
            "t_micro_feed_s": m["t_micro_f"], "t_meso_s": m["t_meso"], "Q_meso_over_micro": m["t_meso"] / m["t_micro_f"],
            "Da_mix_eff": t_eff / t_rxn, "feed_mL_min": m["Qf"] * 6e7, "feed_crit_mL_min": q_c * 6e7,
            "mixing_sensitive": float(S > 1), "sensitivity_index": S, "sensitivity_margin": 1 / S, "knob_code": float(best[0]),
            "knob_new_index": best[1], "sel_X": X, "sel_X_perfect": Xp, "sel_loss": X - Xp,
            "dT_adiabatic_K": h["dT_ad"], "dT_plume_K": h["dT_plume"], "dT_bulk_K": h["dT_bulk"], "cooling_ratio": h["cooling_ratio"],
            "hotspot": float(h["dT_plume"] > p["heat.dT_hot_K"]), "cooling_limited": float(h["cooling_ratio"] > 1),
            "vortex_ratio": f["vortex"], "torque_mN_m": f["torque"], "decouple_ratio": f["decouple"],
            "valid": float(f["vortex"] < 1 and f["decouple"] < 1 and m["in_range"] == 1.0)}


def tier0(p):
    m = _mix(p)
    t_rxn = 1 / (p["k2_M_s"] * p["C0_M"])
    Da = m["theta95"] / t_rxn
    r, mg = classify(Da)
    S, _, _, _ = _sens(p, m)
    q_c, _ = critical_feed(p, m)
    h, f = _heat(p, m), _flags(p, m)
    big = scale_up(p, 1000.0, "rpm")
    return r, mg, {"Re": m["Re"], "t_mix95_s": m["theta95"], "t_micro_s": m["t_micro"], "t_reaction_s": t_rxn, "Da_macro": Da,
                   "Da_micro": m["t_micro"] / t_rxn, "epsilon_W_kg": m["eps"], "t_meso_s": m["t_meso"],
                   "mixing_sensitive": float(S > 1), "sensitivity_margin": 1 / S, "feed_crit_mL_min": q_c * 6e7,
                   "feed_mL_min": m["Qf"] * 6e7, "dT_plume_K": h["dT_plume"], "cooling_ratio": h["cooling_ratio"],
                   "vortex_ratio": f["vortex"], "decouple_ratio": f["decouple"], "eps_1L_same_rpm_W_kg": big["eps"],
                   "t_micro_1L_same_rpm_s": big["t_micro"]}


register(Vessel("flask", "Stirred flask", DEFS, tier0, solve, {
    "Re": "", "Np": "", "epsilon_W_kg": "W/kg", "t_mix95_s": "s", "t_micro_s": "s", "Da_macro": "", "Da_micro": "",
    "Xs_villermaux_dushman": "", "c_local_over_feed": "", "t_micro_feed_s": "s", "t_meso_s": "s", "Q_meso_over_micro": "",
    "Da_mix_eff": "", "feed_mL_min": "mL/min", "feed_crit_mL_min": "mL/min", "mixing_sensitive": "", "sensitivity_index": "",
    "sensitivity_margin": "", "knob_code": "", "knob_new_index": "", "sel_X": "",  # knob_code: 1 stir rate, 2 bar size, 3 feed time, 4 viscosity
   
    "sel_X_perfect": "", "sel_loss": "", "dT_adiabatic_K": "K", "dT_plume_K": "K", "dT_bulk_K": "K", "cooling_ratio": "",
    "hotspot": "", "cooling_limited": "", "vortex_ratio": "", "torque_mN_m": "mN m", "decouple_ratio": "", "valid": ""},
    lambda p: f"addition_point,{p['stir_rpm']:.0f}rpm", "tier1:grenville+engulfment+meso+incorporation",
    ["Villermaux-Dushman segregation index", "Bourne competitive-consecutive selectivity"]))
