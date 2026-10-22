"""Tier 1 growth handles for the MoS2 tube (Track A, A2/A3): source inventory, vertical gap, nucleation-theory proxies.
Nucleation (A2): mean-field Venables scaling, N ~ F^chi with chi = i/(i+2) for diffusion-limited aggregation (opened source:
Pimpinelli, Tumbek & Winkler, J. Phys. Chem. Lett. 5, 995 (2014), DOI 10.1021/jz500282t; they state alpha = i/(i+2)). The temperature factor
exp(E_eff/kT), E_eff = (i E_d + E_i)/(i+2), is NOT in an opened source; E_eff is a synthetic range, used only when the substrate temperature varies.
Domain size at fixed coverage ~ N^-1/2; coverage ~ F t_eff (sticking 1); layer number ~ F t_eff / n_ML.
Inventory (A3): t_dep = m / (M * rate) from the existing Hertz-Knudsen boat rate; t_eff = min(t_growth, t_dep_Mo, t_dep_S).
Gap (A3): face-down substrate above the boat, 1D diffusion across the gap in series with Hertz-Knudsen, F = dp / (1/k_hk + gap R T / D).
ponytail: steady boat rate (no rate decay as the charge shrinks), the gap model ignores carrier flow and uses the film temperature mean of boat and
substrate, no sticking coefficient, no coalescence."""
import numpy as np
from core import props
from core.params import ParamDef as D
from vessels import cvd_tube as tube
from vessels.cvd_tube import thermo

KB = 8.617333e-5  # eV/K
A_MOS2 = 3.16e-10  # m, experimental a quoted in Rosen, Notestein & Snurr, JPCC 122, 15318 (2018) p. 15320
N_ML = 1 / (np.sqrt(3) / 2 * A_MOS2**2) / 6.02214076e23  # mol Mo per m2 of one MoS2 monolayer
M_MO3, M_S = props.M_SPECIES["MoO3"], props.M_SPECIES["S2"] / 2  # g/mol
GDEFS = [
    D("m_MoO3_mg", "MoO3 charge in the boat (inventory; huge = unlimited)", "mg", 1e6, 1e-3, 1e9, source="user input; default = unlimited", group="operation"),
    D("m_S_mg", "Sulfur charge in the boat (inventory; huge = unlimited)", "mg", 1e6, 1e-3, 1e9, source="user input; default = unlimited", group="operation"),
    D("gap_mm", "Vertical source-substrate gap (face-down substrate above the MoO3 boat; 0 = use the tube model)", "mm", 0.0, 0.0, 200.0, group="geometry"),
]
DEFS = tube.DEFS + GDEFS


def k_hk(v, T):
    """Hertz-Knudsen coefficient in MoO3-unit equivalents, mol/m2/s/Pa: alpha / sqrt(2 pi n M R T) (oligomer of n units)."""
    n = int(v["MoO3.n_oligomer"])
    return v["alpha_MoO3"] / np.sqrt(2 * np.pi * n * M_MO3 * 1e-3 * props.R * T)


def gap_flux(v, T_boat, T_sub, gap_m, pS2=0.0):
    """Flux (mol MoO3 units/m2/s) to a substrate gap_m above the boat. D = model Fuller diffusivity at the mean film temperature.
    Track M: substrate_uptake_model='reactive' replaces the condensation driving force psat(T_boat) - psat(T_sub) by psat(T_boat) - C_eq_rxn and adds
    the surface resistance R T_sub / k_rxn(T_sub, pS2) in series (proposed closure, see reactive.py); pS2 = local S2 pressure [Pa]."""
    Tf = 0.5 * (T_boat + T_sub)
    Dg = float(thermo.fuller_D(v["carrier"], "MoO3", 1000.0, v["pressure_Pa"], int(v["MoO3.n_oligomer"]))) * (Tf / 1000.0) ** 1.75 * v["D_scale"]
    if v.get("substrate_uptake_model", "condensation") == "reactive":
        from vessels.cvd_tube import reactive
        dp = max(float(thermo.psat_MoO3(v, T_boat)) - v["C_eq_rxn_Pa"], 0.0)
        return dp / (1 / k_hk(v, T_boat) + gap_m * props.R * Tf / Dg + props.R * T_sub / max(float(reactive.k_rxn(v, T_sub, pS2)), 1e-300))
    dp = max(float(thermo.psat_MoO3(v, T_boat) - thermo.psat_MoO3(v, T_sub)), 0.0)
    return dp / (1 / k_hk(v, T_boat) + gap_m * props.R * Tf / Dg)


def state(v):
    """-> F (mol/m2/s at the substrate), t_eff (s), T_sub (K), t_dep_Mo, t_dep_S (s). v = full tube value dict."""
    x, T, o, m = tube.march(v)
    Ts = float(np.interp(m["xcen"], x, m["Twe"]))
    rate_M, rate_S = float(m["NM_in"]), float(m["NS_in"])  # MoO3 units/s, S atoms/s
    if v["gap_mm"] > 0:
        F = gap_flux(v, v["T_boat_Mo_C"] + 273.15, Ts, v["gap_mm"] * 1e-3, float(np.interp(m["xcen"], x, o["pS"])))
        rate_M = F * v["boat_area_MoO3_cm2"] * 1e-4  # mol/s reaching the substrate above the boat
    else:
        F = float(np.interp(m["xcen"], x, o["flux"]))
    tM = v["m_MoO3_mg"] * 1e-3 / M_MO3 / max(rate_M, 1e-300)
    tS = v["m_S_mg"] * 1e-3 / M_S / max(rate_S, 1e-300)
    return {"F": F, "T_sub": Ts, "t_dep_Mo": tM, "t_dep_S": tS, "t_eff": min(v["duration_min"] * 60, tM, tS)}


def observables(st, i=1, E_eff=0.0):
    """ln-valued proxies from a state(): nucleation density, domain size, coverage, layer number (additive constants dropped)."""
    lF = np.log(max(st["F"], 1e-300))
    chi = i / (i + 2)
    lN = chi * lF + E_eff / (KB * st["T_sub"])
    lt = np.log(max(st["t_eff"], 1e-300))
    return {"nucleation": lN, "domain": -0.5 * lN, "coverage": lF + lt, "layers": lF + lt - np.log(N_ML)}
