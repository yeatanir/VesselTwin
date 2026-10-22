"""Packed sorbent bed, Tier 1: 1D non-isothermal column for CO2 capture (zeolite 13X, CALF-20), CO2/N2/H2O.
Physics (each switchable or overridable through a ParamDef):
 - isotherms: extended dual-site Langmuir (EDSL, in-house; IAST-equivalent only for equal capacities) or the CALF-20 'modified'
   CO2/H2O scheme; numbers sourced in sorbent_data.json (Wilkins 2017 13X; Nguyen 2021 CALF-20), b(T)=b0*exp(-dU/RT).
 - total molar balance with compressible flow (adsorption changes superficial velocity) and Ergun dP fed back into P(z)
   (quasi-steady pressure, outlet pressure fixed); flow='constant' recovers the old dilute constant-u column.
 - axial dispersion D_L = 0.7 Dm + v r_p (Ruthven 1984) + second-order TVD (van Leer) convection.
 - LDF coefficient from resistances in series (film: Wakao-Funazkri; macropore: Glueckauf/Ruthven; optional micropore),
   k_ldf > 0 overrides all of them.
 - energy balance: gas + solid + adsorbed-phase heat capacity, per-component isosteric heat (from the isotherm itself),
   axial conduction, optional lumped wall (heat capacity, h_in, h_out); water heat of adsorption through the water isotherm.
 - optional second stage (regen='purge'): hot/low-pressure purge from the state at breakthrough -> cycle working capacity.
Closure contract (atomistic -> vessel, apply_closures sets '<closure.name>.<key>'): closure 'isotherm' = CO2 strong site
{qmax [mol/kg], b_ref [1/bar @298.15K], Q [kJ/mol]}; second site {qmax2, b2_ref, Q2}; closure 'isotherm_N2' and 'isotherm_H2O'
carry the same six keys for N2 and H2O (H2O also c2_ref [1/bar^2], c3_ref [1/bar^3] for the CALF-20 cubic term);
'isotherm' alpha1/alpha2 [kg/mol] are the CALF-20 water factors. K(T) = b_ref*(T0/T)*exp((Q-R*T0)/R*(1/T-1/T0)).
Prior art: RUPTURA (MIT, C++) for cross-checks only. Bounds on validity: fit.* ParamDefs; solve() reports outside_fit_range.
ponytail: P(z) quasi-steady (no dP/dt holdup), carrier viscosity/cp used for the mixture, inlet Danckwerts flux and wall
axial conduction neglected, water-in-CO2 competition is an upper bound outside ~1 bar CO2 (see sorbent_data.json),
adsorbed-phase cp = ratio x gas cp, heat Q(q) tabulated at T0 (held constant with T; (cp_gas - cp_ads)(T-T0) correction)."""
import json, pathlib
import numpy as np
import scipy.sparse as sp
from scipy.integrate import solve_ivp
from core import props
from core.dimensionless import Regime
from core.params import ParamDef as P
from core.registry import Vessel, register

R, T0 = props.R, 298.15
SYN = "synthetic"
SC_OFF = 1e-2
MAXEVAL = 40000  # ~6 s; humid CALF-20 (type-V water isotherm) needs ~12000
KCAP = 20.0  # ponytail: LDF cap [1/s] for fast species (N2): already ~equilibrium on the bed timescale, avoids a stiff mode (same breakthrough to 1e-3)
RTOL = 3e-3  # ODE tolerance; front shape is set by the TVD grid (see grid-convergence test), not by time error
DATA = json.loads((pathlib.Path(__file__).parent / "sorbent_data.json").read_text())
# ponytail: He and H2O added to the shared gas tables (values: sorbent_data.json refs BSL, FUL66); belongs in core/props.py
props.GAS.setdefault("He", (4.0026, 2.551, 10.22, 2.5)); props.GAS.setdefault("H2O", (18.015, 2.641, 809.1, 4.03))
props.FULLER.setdefault("He", 2.88); props.FULLER.setdefault("H2O", 12.7)
PRE = {"CO2": "isotherm", "N2": "isotherm_N2", "H2O": "isotherm_H2O"}
CITE = {"CO2": "Wilkins 2017 Tab 4.1 (13X Z10-02ND)", "N2": "Wilkins 2017 Tab 4.1", "H2O": "Wilkins 2017 Tab 4.1"}


def from_source(mat):
    """sorbent_data.json material -> ParamDef-basis values (b_ref 1/bar @T0, Q = -dU + R*T0 in kJ/mol)."""
    out = {}
    for sp, d in mat["species"].items():
        pre = PRE[sp]
        for i, s in enumerate(d["sites"]):
            suf = "" if i == 0 else "2"
            out[f"{pre}.qmax{suf}"] = s["qs"]
            out[f"{pre}.b{suf and '2'}_ref"] = s["b0"] * np.exp(-s["dU"] * 1e3 / (R * T0)) / (R * T0) * 1e5
            out[f"{pre}.Q{suf}"] = -s["dU"] + R * T0 / 1e3
        if "b0_2" in d:  # b_k share dU of site 1
            f = np.exp(-d["sites"][0]["dU"] * 1e3 / (R * T0))
            out[f"{pre}.c2_ref"] = d["b0_2"] * f / (R * T0) ** 2 * 1e10
            out[f"{pre}.c3_ref"] = d["b0_3"] * f / (R * T0) ** 3 * 1e15
    out["competition"] = mat["competition"]
    if "alpha1_kg_per_mol" in mat:
        out["isotherm.alpha1"], out["isotherm.alpha2"] = mat["alpha1_kg_per_mol"], mat["alpha2_kg_per_mol"]
    out |= {f"fit.{k}": v for k, v in mat["fit"].items()} | mat["bed"]
    return out


def preset(name): return from_source(DATA["materials"][name])


_D = preset("13X_Z1002ND")
_V = {"qmax": 0.0, "b_ref": 1.0, "Q": 30.0, "qmax2": 0.0, "b2_ref": 1.0, "Q2": 30.0, "c2_ref": 0.0, "c3_ref": 0.0}


def _iso_defs(sp, label):
    pre, out = PRE[sp], []
    for k, unit, lo, hi, sg, rel in [("qmax", "mol/kg", 0.0, 50, 0.1, True), ("b_ref", "1/bar", -1e12 if sp == "H2O" else 0.0, 1e12, 0.2, True),
                                     ("Q", "kJ/mol", 0.0, 400, 3.0, False), ("qmax2", "mol/kg", 0.0, 50, 0.1, True),
                                     ("b2_ref", "1/bar", 0.0, 1e12, 0.2, True), ("Q2", "kJ/mol", 0.0, 400, 3.0, False)] + \
            ([("c2_ref", "1/bar^2", -1e12, 1e12, 0.0, True), ("c3_ref", "1/bar^3", -1e12, 1e12, 0.0, True)] if sp == "H2O" else []):
        name = f"{pre}.{k}"
        if sp == "CO2" and k == "qmax": lo = 0.01
        if sp == "CO2" and k == "b_ref": lo = 1e-4
        out.append(P(name, f"{label} {k}", unit, _D.get(name, _V[k]), lo, hi, sg, rel, group="isotherm", source=CITE[sp] if name in _D else SYN,
                     help="site 1 = strong site; K(T)=b_ref*(T0/T)*exp((Q-R*T0)/R*(1/T-1/T0)); Q = -dU + R*T0 of the published fit"
                     if k == "qmax" else ""))
    return out


DEFS = [
    P("bed_length_cm", "Bed length", "cm", 10.0, 0.5, 200, group="geometry"),
    P("bed_id_cm", "Bed inner diameter", "cm", 1.0, 0.2, 50, group="geometry"),
    P("bed.epsilon", "Bed void fraction", "", 0.4, 0.2, 0.8, 0.05, group="geometry", source="Wilkins 2017 Tab 4.4; Nguyen 2021 Tab 2.2"),
    P("bed.rho_kg_m3", "Bed bulk density", "kg/m3", _D["bed.rho_kg_m3"], 100, 1500, 0.05, group="geometry", source="Wilkins 2017 Tab 4.4 (measured, 13X)"),
    P("particle_dp_mm", "Particle diameter", "mm", 1.0, 0.05, 10, group="geometry", help="Ergun, film coefficient, macropore path, dispersion"),
    P("particle.epsilon", "Particle porosity", "", 0.35, 0.1, 0.8, 0.1, group="geometry", source="assumed in Wilkins 2017 / Nguyen 2021"),
    P("tortuosity", "Particle tortuosity", "", 3.0, 1, 20, 0.2, group="geometry", source="assumed in Wilkins 2017 / Nguyen 2021"),
    P("r_macropore_nm", "Macropore radius (Knudsen; 0 = molecular diffusion only)", "nm", 0.0, 0, 1e5, group="model", source=SYN),
    P("Dc_rc2", "Micropore D_c/r_c^2 (0 = no micropore resistance)", "1/s", 0.0, 0, 10, group="model", source=SYN),
    P("T_K", "Feed and wall temperature", "K", 298.15, 200, 500, 2.0, False, group="operation"),
    P("P_kPa", "Outlet pressure", "kPa", 101.325, 1, 5000, group="operation"),
    P("flow_sccm", "Total feed flow", "sccm", 100.0, 1, 5000, 0.03, group="operation"),
    P("y_feed", "Adsorbate (CO2) mole fraction in feed", "", 0.15, 1e-4, 1.0, 0.03, group="operation"),
    P("RH_feed", "Feed relative humidity at T_K (0 = dry)", "", 0.0, 0.0, 1.0, 0.0, group="operation"),
    P("carrier", "Balance gas", "", "N2", choices=["N2", "He"], group="operation", help="He: non-adsorbing (thesis benchmarks)"),
    P("energy", "Energy balance", "", "nonisothermal", choices=["isothermal", "nonisothermal"], group="operation"),
] + _iso_defs("CO2", "CO2") + _iso_defs("N2", "N2") + _iso_defs("H2O", "H2O") + [
    P("isotherm.alpha1", "CO2 loading reduction by water (modified scheme)", "kg/mol", 0.0, 0, 10, 0.2, group="isotherm", source="Nguyen 2021 Tab 4.3 (CALF-20 preset)" if "isotherm.alpha1" in _D else SYN),
    P("isotherm.alpha2", "CO2 affinity reduction by water (modified scheme)", "kg/mol", 0.0, 0, 10, 0.2, group="isotherm", source=SYN),
    P("competition", "Competitive isotherm", "", _D["competition"], choices=["edsl", "modified"], group="isotherm",
      help="edsl: all species in every site denominator; modified: CALF-20 water scheme (needs alpha1/alpha2)"),
    P("k_ldf", "LDF coefficient override (0 = from film + macropore + micropore resistances)", "1/s", 0.0, 0, 100, 0.3, group="model"),
    P("flow", "Flow model", "", "variable", choices=["variable", "constant"], group="model", help="variable: total molar balance; constant: dilute"),
    P("ergun", "Pressure drop", "", "feedback", choices=["feedback", "off"], group="model"),
    P("dispersion", "Axial dispersion", "", "axial", choices=["axial", "off"], group="model"),
    P("n_cells", "Axial cells", "", 30, 10, 400, group="model", help="30 keeps solve ~0.35 s (dashboard/MC); thermal peak converges only at >= 100 cells (tests)"),
    P("cp_solid", "Sorbent heat capacity", "J/kg/K", _D["cp_solid"], 300, 3000, 0.1, group="model", source="assumed in Wilkins 2017 (13X)"),
    P("cp_ads_ratio", "Adsorbed-phase cp / gas cp", "", 1.0, 0, 3, 0.2, group="model", source="assumed = gas in Wilkins 2017 / Nguyen 2021"),
    P("Kz", "Effective axial thermal conductivity", "W/m/K", 0.4, 0, 50, 0.5, group="model", source="assumed/fitted in Wilkins 2017 / Nguyen 2021"),
    P("wall_model", "Wall", "", "none", choices=["none", "lumped"], group="model", help="none: overall h_wall to ambient (old model); lumped: wall heat capacity + h_in"),
    P("h_wall", "Heat-transfer coefficient to ambient", "W/m2/K", 20.0, 0.1, 1000, 0.3, source=SYN, group="model"),
    P("h_in", "Bed-to-wall coefficient (lumped wall)", "W/m2/K", 7.0, 0.1, 1000, 0.3, source=SYN, group="model",
      help="column specific; Nguyen 2021 fit 6.96 (2.82 cm column) not transferable"),
    P("wall_mm", "Wall thickness", "mm", 1.8, 0.1, 20, group="model", source="Nguyen 2021 Tab 2.2 (3.18-2.82 cm)"),
    P("rho_wall", "Wall density", "kg/m3", 7800.0, 500, 20000, group="model", source="Nguyen 2021 Tab 2.2 (steel)"),
    P("cp_wall", "Wall heat capacity", "J/kg/K", 502.0, 100, 3000, group="model", source="Nguyen 2021 Tab 2.2 (steel)"),
    P("regen", "Regeneration stage", "", "off", choices=["off", "purge"], group="regeneration", help="purge starts at 5 % breakthrough"),
    P("T_regen_K", "Purge inlet temperature", "K", 400.0, 250, 600, 5.0, False, source=SYN, group="regeneration"),
    P("P_regen_kPa", "Purge outlet pressure", "kPa", 101.325, 1, 5000, source=SYN, group="regeneration"),
    P("regen_flow_sccm", "Purge flow (balance gas)", "sccm", 100.0, 1, 5000, source=SYN, group="regeneration"),
    P("t_regen_min", "Purge duration", "min", 20.0, 0.1, 1000, source=SYN, group="regeneration"),
    P("fit.T_lo_K", "Isotherm data: lowest T", "K", _D["fit.T_lo_K"], 100, 600, group="fit range", source="sorbent_data.json"),
    P("fit.T_hi_K", "Isotherm data: highest T", "K", _D["fit.T_hi_K"], 100, 800, group="fit range", source="sorbent_data.json"),
    P("fit.p_CO2_hi_bar", "Isotherm data: highest CO2 partial pressure", "bar", _D["fit.p_CO2_hi_bar"], 0.01, 100, group="fit range", source="sorbent_data.json"),
    P("fit.RH_hi", "Water data: highest RH (22 C)", "", _D["fit.RH_hi"], 0, 1, group="fit range", source="sorbent_data.json"),
    P("fit.y_CO2_lo", "CO2/H2O competition data: lowest CO2 fraction", "", _D["fit.y_CO2_lo"], 0, 1, group="fit range", source="sorbent_data.json"),
]


def psat(T): return 610.94 * np.exp(17.625 * (T - 273.15) / (T - 273.15 + 243.04))  # Pa, Magnus (Alduchov-Eskridge), valid ~0-60 C


def _pk(p):
    """isotherm parameters in SI: qs [mol/kg] (2 sites), K0 [m3/mol] at T0, Q [J/mol]; water cubic terms c2, c3 [m3/mol]^k."""
    out = {}
    for sp, pre in PRE.items():
        g = lambda k: p[f"{pre}.{k}"]
        out[sp] = dict(qs=[g("qmax"), g("qmax2")], K0=[g("b_ref") * 1e-5 * R * T0, g("b2_ref") * 1e-5 * R * T0], Q=[g("Q") * 1e3, g("Q2") * 1e3],
                       c2=g("c2_ref") * 1e-10 * (R * T0) ** 2 if sp == "H2O" else 0.0, c3=g("c3_ref") * 1e-15 * (R * T0) ** 3 if sp == "H2O" else 0.0)
    out["K0s"] = np.array([out[sp]["K0"] for sp in SPS]); out["qss"] = np.array([out[sp]["qs"] for sp in SPS])
    out["Qs"] = np.array([[(q - R * T0) / R for q in out[sp]["Q"]] for sp in SPS])
    out["a1"], out["a2"], out["mode"] = p["isotherm.alpha1"], p["isotherm.alpha2"], p["competition"]
    return out


SPS = ["CO2", "N2", "H2O"]


def _eq(pk, C, T, qw=None):
    """Competitive loadings [mol/kg]. C: {species: gas concentration mol/m3 (array)}; T array/scalar.
    qw: actual water loading used in the CALF-20 CO2 water factors (default: the water equilibrium loading)."""
    if not (pk["mode"] == "modified" and "H2O" in C) and not ("H2O" in C and (pk["H2O"]["c2"] or pk["H2O"]["c3"])):  # fast EDSL path
        ii = [SPS.index(sp) for sp in C]
        Cs = np.atleast_2d(np.array(list(C.values()), float).reshape(len(C), -1))[:, None, :]  # (species, 1, cells)
        K = pk["K0s"][ii][:, :, None] * np.exp(pk["Qs"][ii][:, :, None] * (1 / np.asarray(T) - 1 / T0))
        qs = pk["qss"][ii][:, :, None]
        KC = K * Cs * (qs > 0)  # a site with zero capacity for a species does not host (or block) it
        q = (qs * K * Cs / (1 + KC.sum(0))).sum(1)
        sc = np.ndim(next(iter(C.values()))) == 0
        return {sp: (q[i, 0] if sc else q[i]) for i, sp in enumerate(C)}
    f = {sp: [np.exp((pk[sp]["Q"][s] - R * T0) / R * (1 / T - 1 / T0)) for s in (0, 1)] for sp in C}
    K = {sp: [pk[sp]["K0"][s] * f[sp][s] for s in (0, 1)] for sp in C}
    q, qs, mod = {}, {sp: list(pk[sp]["qs"]) for sp in C}, pk["mode"] == "modified" and "H2O" in C
    if mod:
        w, Cw = pk["H2O"], C["H2O"]
        B1, B2, B3 = K["H2O"][0], w["c2"] * f["H2O"][0], w["c3"] * f["H2O"][0]
        q["H2O"] = w["qs"][0] * (B1 * Cw + 2 * B2 * Cw**2 + 3 * B3 * Cw**3) / (1 + B1 * Cw + B2 * Cw**2 + B3 * Cw**3) \
            + w["qs"][1] * K["H2O"][1] * Cw / (1 + K["H2O"][1] * Cw)
        if "CO2" in C:  # water lowers CO2 capacity and affinity (Nguyen 2021 eq 4.19-4.21)
            qwf = q["H2O"] if qw is None else qw
            qs["CO2"] = [x / (1 + pk["a1"] * qwf) for x in qs["CO2"]]
            K["CO2"] = [x * np.exp(-pk["a2"] * qwf) for x in K["CO2"]]
    elif "H2O" in C and (pk["H2O"]["c2"] or pk["H2O"]["c3"]):
        raise ValueError("water cubic isotherm terms need competition='modified'")
    comp = [sp for sp in C if not (mod and sp == "H2O")]
    den = [1 + sum(K[sp][s] * C[sp] * (qs[sp][s] > 0) for sp in comp) for s in (0, 1)]
    for sp in comp:
        q[sp] = sum(qs[sp][s] * K[sp][s] * C[sp] / den[s] for s in (0, 1))
    return q


def _qst_table(pk, sp, T, pmax):
    """Isosteric heat of the pure-species isotherm, -R T (dq/dlnT)_p / (dq/dlnp)_T, tabulated against loading."""
    pg, d = np.geomspace(1e-2, pmax, 120), 1e-3
    qf = lambda pp, TT: _eq(pk, {sp: pp / (R * TT)}, TT)[sp]
    dT_, dp_ = (qf(pg, T * (1 + d)) - qf(pg, T * (1 - d))) / (2 * d), (qf(pg * (1 + d), T) - qf(pg * (1 - d), T)) / (2 * d)
    q, Qs = qf(pg, T), np.clip(-R * T * dT_ / np.where(np.abs(dp_) > 1e-14, dp_, np.nan), 5e3, 4e5)
    ok = np.isfinite(Qs)
    if not ok.any(): return np.array([0.0, 1.0]), np.full(2, pk[sp]["Q"][0])  # non-adsorbing species
    q, Qs = q[ok], Qs[ok]
    q, i = np.unique(q, return_index=True)
    return q, Qs[i]


def _setup(p):
    Pt, T = p["P_kPa"] * 1e3, p["T_K"]
    A = np.pi * (p["bed_id_cm"] / 200) ** 2
    Q0 = p["flow_sccm"] * 1e-6 / 60 * (T / 273.15) * (101325 / Pt)
    us = Q0 / A  # inlet superficial velocity
    Nin = us * Pt / (R * T)  # mol/m2/s
    car, hum = p["carrier"], p["RH_feed"] > 0
    yc, yw = p["y_feed"], (p["RH_feed"] * psat(T) / Pt if hum else 0.0)
    if yc + yw > 1: raise ValueError("CO2 + water fraction >= 1")
    ads = ["CO2"] + (["N2"] if car == "N2" else []) + (["H2O"] if hum else [])
    L, eps, rb, dp = p["bed_length_cm"] / 100, p["bed.epsilon"], p["bed.rho_kg_m3"], p["particle_dp_mm"] * 1e-3
    pk, cT = _pk(p), Pt / (R * T)
    feed = {"CO2": yc * cT} | ({"N2": (1 - yc - yw) * cT} if car == "N2" else {}) | ({"H2O": yw * cT} if hum else {})
    qeq = _eq(pk, feed, T)
    qs = _eq(pk, {k: v for k, v in feed.items() if k != "H2O"}, T)["CO2"]  # dry feed: CO2 shock sees a water-free bed
    c0 = yc * cT
    tst = L * (eps + rb * qs / c0) / us  # exact CO2 shock time (single front, isothermal) = old formula in the dilute limit
    # mass transfer: 1/k = r rho_p q'/(3 kf) + r^2 (eps_p + rho_p q')/(15 eps_p Dp) + 1/(15 Dc/rc^2)  (Ruthven 1984 / Glueckauf), q' = q*/C
    mu, M = props.viscosity(car, T), yc * props.mass("CO2") + yw * props.mass("H2O") + (1 - yc - yw) * props.mass(car)
    rho_g, rp, ep, rho_p = cT * M * 1e-3, dp / 2, p["particle.epsilon"], rb / (1 - eps)
    k = {}
    for sp in ads:
        Dm = props.diffusivity(sp, car if sp != "N2" else "CO2", T, Pt)  # N2 (when it is the balance gas): diffusion in CO2
        Dk = 97 * p["r_macropore_nm"] * 1e-9 * np.sqrt(T / props.mass(sp)) if p["r_macropore_nm"] > 0 else np.inf
        Dpore = 1 / (p["tortuosity"] * (1 / Dm + 1 / Dk))
        kf = (2 + 1.1 * (mu / (rho_g * Dm)) ** (1 / 3) * (rho_g * us * dp / mu) ** 0.6) * Dm / dp  # Wakao-Funazkri
        qp = qeq[sp] / feed[sp]
        res = rp * rho_p * qp / (3 * kf) + rp**2 * (ep + rho_p * qp) / (15 * ep * Dpore) + (1 / (15 * p["Dc_rc2"]) if p["Dc_rc2"] > 0 else 0)
        k[sp] = p["k_ldf"] if p["k_ldf"] > 0 else min(1 / res, KCAP)
        if sp == "CO2": Dm_c = Dm
    DL = 0.7 * Dm_c + us / eps * rp
    return dict(Pt=Pt, T0=T, A=A, us=us, Nin=Nin, c0=c0, cT=cT, qs=qs, L=L, tst=tst, yc=yc, yw=yw, hum=hum, ads=ads, k=k, DL=DL, pk=pk,
                Dm=Dm_c, feed=feed, qeq=qeq, mu=mu, rho_g=rho_g, ep=ep, rho_p=rho_p, Pe=us / eps * L / DL)


GAS = {g: (props.mass(g), props.GAS[g][3] * R) for g in ("CO2", "N2", "H2O", "He")}  # M g/mol, cp J/mol/K


def _col(p, s, bc):
    """Build rhs(t, y) and flux(y) for boundary conditions bc = dict(yin=(yc, yw), Tin, Nin, Pout).
    State per cell: [yc, (yw), q_species..., (T), (Tw), (P)]. With flow='variable' the cell pressure P is a state and the molar flux
    follows from Ergun on the cell-to-cell pressure difference (local coupling -> banded Jacobian); the total molar balance
    sets dP/dt. flow='constant' = dilute model (N = Nin, uniform P)."""
    n, L = int(p["n_cells"]), s["L"]
    dz, eps, rb, car = L / n, p["bed.epsilon"], p["bed.rho_kg_m3"], p["carrier"]
    ads, hum, noniso = s["ads"], s["hum"], p["energy"] == "nonisothermal"
    wall, var = noniso and p["wall_model"] == "lumped", p["flow"] == "variable"
    cols = ["yc"] + (["yw"] if hum else []) + ["q" + a for a in ads] + (["T"] if noniso else []) + (["Tw"] if wall else []) + (["P"] if var else [])
    ix, nv = {c: i for i, c in enumerate(cols)}, len(cols)
    pk, k, dp, Tamb = s["pk"], s["k"], p["particle_dp_mm"] * 1e-3, s["T0"]
    sc = 1.0 if p["ergun"] == "feedback" else SC_OFF  # ponytail: 'off' keeps the P state with Ergun coefficients x1e-4 (dP ~ 1e-4 of Ergun)
    a_er = sc * 150 * s["mu"] * (1 - eps) ** 2 / (eps**3 * dp**2)
    b_er = sc * 1.75 * (1 - eps) / (eps**3 * dp)
    disp = p["dispersion"] == "axial"
    D, Do = p["bed_id_cm"] / 100, p["bed_id_cm"] / 100 + 2 * p["wall_mm"] * 1e-3
    qtab = {sp: _qst_table(pk, sp, s["T0"], min(bc["Pout"] * 3, 5e6) if sp != "H2O" else psat(s["T0"] + 30)) for sp in ads}
    rp = p["particle_dp_mm"] * 5e-4
    Mg, cpg = {g: GAS[g][0] * 1e-3 for g in GAS}, {g: GAS[g][1] for g in GAS}

    def tvd(xin, x):
        a = x[:-1] - np.concatenate(([xin], x[:-2])); b = x[1:] - x[:-1]; ab = a * b
        return np.concatenate(([xin], x[:-1] + 0.5 * (ab + np.abs(ab)) / (b * b + np.abs(ab) + 1e-300) * b, x[-1:]))

    def flux(y):
        Y = y.reshape(n, nv)
        yc = Y[:, 0]; yw = Y[:, ix["yw"]] if hum else np.zeros(n)
        T = Y[:, ix["T"]] if noniso else np.full(n, s["T0"])
        P = Y[:, ix["P"]] if var else np.full(n, bc["Pout"])
        yn = np.clip(1 - yc - yw, 0, 1)
        Mm = yc * Mg["CO2"] + yw * Mg["H2O"] + yn * Mg[car]
        cpm = yc * cpg["CO2"] + yw * cpg["H2O"] + yn * cpg[car]
        cT = P / (R * T)
        C = {"CO2": yc * cT} | ({"N2": yn * cT} if car == "N2" else {}) | ({"H2O": yw * cT} if hum else {})
        qe = _eq(pk, C, T, Y[:, ix["qH2O"]] if hum else None)  # water factors use the water actually adsorbed
        dq = {a: k[a] * (qe[a] - Y[:, ix["q" + a]]) for a in ads}
        sdq = sum(dq.values())
        if var:  # Ergun on face pressure differences: G = a u + b rho u^2
            G = np.concatenate(((P[:-1] - P[1:]) / dz, [(P[-1] - bc["Pout"]) / (dz / 2)]))
            cf, Mf = np.concatenate((0.5 * (cT[1:] + cT[:-1]), cT[-1:])), np.concatenate((0.5 * (Mm[1:] + Mm[:-1]), Mm[-1:]))
            u = np.sign(G) * 2 * np.abs(G) / (a_er + np.sqrt(a_er**2 + 4 * b_er * cf * Mf * np.abs(G)))
            Nf = np.concatenate(([bc["Nin"]], cf[:-1] * u[:-1], [cf[-1] * u[-1]]))
        else:
            Nf = np.full(n + 1, bc["Nin"])
        Nc = 0.5 * (Nf[:-1] + Nf[1:])
        out = dict(P=P, cT=cT, T=T, Nf=Nf, dq=dq, sdq=sdq, yc=yc, yw=yw, yn=yn, Y=Y, Nc=Nc, cpm=cpm, Mm=Mm,
                   dcT=-((Nf[1:] - Nf[:-1]) / dz + rb * sdq) / eps if var else np.zeros(n))  # total molar balance
        if noniso:
            Tw = Y[:, ix["Tw"]] if wall else None
            Tf = tvd(bc["Tin"], T)
            cq = sum(Y[:, ix["q" + a]] * cpg[a] for a in ads) * p["cp_ads_ratio"]
            heat = sum((np.interp(Y[:, ix["q" + a]], *qtab[a]) + (1 - p["cp_ads_ratio"]) * cpg[a] * (T - s["T0"])) * dq[a] for a in ads)  # Kirchhoff; conserves energy
            Qf = p["Kz"] * (T[1:] - T[:-1]) / dz
            cond = (np.concatenate((Qf, [0.0])) - np.concatenate(([0.0], Qf))) / dz
            loss = 4 * p["h_in"] / D * (T - Tw) if wall else 4 * p["h_wall"] / D * (T - Tamb)
            out["dT"] = (-Nc * cpm * (Tf[1:] - Tf[:-1]) / dz + cond + rb * heat - loss) / (rb * (p["cp_solid"] + cq) + eps * cT * cpm)
        return out

    def rhs(t, y):
        f = flux(y); Nf, cT, Nc = f["Nf"], f["cT"], f["Nc"]
        Y = f["Y"]; dY = np.zeros_like(Y)
        DLf = 0.7 * s["Dm"] + (Nc / cT) / eps * rp if disp else None  # Ruthven: local interstitial velocity
        for col, yin in [("yc", bc["yin"][0])] + ([("yw", bc["yin"][1])] if hum else []):
            yy = Y[:, ix[col]]
            F = Nf * tvd(yin, yy)
            if disp:
                cf, Df = 0.5 * (cT[1:] + cT[:-1]), 0.5 * (DLf[1:] + DLf[:-1])
                F = F + np.concatenate(([0.0], -eps * cf * Df * (yy[1:] - yy[:-1]) / dz, [0.0]))
            dY[:, ix[col]] = (-(F[1:] - F[:-1]) / dz - rb * f["dq"]["CO2" if col == "yc" else "H2O"] - eps * yy * f["dcT"]) / (eps * cT)
        for a in ads: dY[:, ix["q" + a]] = f["dq"][a]
        if noniso: dY[:, ix["T"]] = f["dT"]
        if wall:
            dY[:, ix["Tw"]] = (4 * D * p["h_in"] * (f["T"] - Y[:, ix["Tw"]]) - 4 * Do * p["h_wall"] * (Y[:, ix["Tw"]] - Tamb)) / (p["rho_wall"] * p["cp_wall"] * (Do**2 - D**2))
        if var:  # eps*dcT/dt = P-state balance: dP/dt = R T dcT/dt + P dlnT/dt
            dY[:, ix["P"]] = R * f["T"] * f["dcT"] + (Y[:, ix["P"]] * f["dT"] / f["T"] if noniso else 0.0)
        return dY.ravel()

    return rhs, flux, ix, nv, n


def _init(p, s, ix, nv, n):
    Y = np.zeros((n, nv)); T = s["T0"]
    if "qN2" in ix: Y[:, ix["qN2"]] = _eq(s["pk"], {"N2": np.full(n, s["Pt"] / (R * T))}, T)["N2"]  # bed pre-saturated with the balance gas
    for c, v in (("T", T), ("Tw", T), ("P", s["Pt"])):
        if c in ix: Y[:, ix[c]] = v
    return Y.ravel()


_PAT = {}


def _pattern(rhs, y0, nv, n, key):
    """Jacobian sparsity (cell-block template, couplings within +-2 cells; no long-range terms because P is a state) from finite
    differences at 3 random states; cached per column layout. Lets BDF colour the Jacobian (~20 rhs calls instead of n*nv)."""
    if key in _PAT: return _PAT[key]
    rng, N, blk = np.random.default_rng(0), n * nv, np.zeros((5, nv, nv), bool)
    for _ in range(3):
        y = y0.reshape(n, nv) * (1 + 0.3 * rng.random((n, nv)))
        y[:, 0] = 0.15 * rng.random(n); y[:, 1] = 3 * rng.random(n); y = y.ravel()
        f0 = rhs(0, y)
        for i in range(N):
            yy = y.copy(); yy[i] += 1e-6 * max(1, abs(y[i]))
            col = (rhs(0, yy) - f0)
            j, b = divmod(i, nv)
            for r in np.where(np.abs(col) > 1e-18 + 1e-9 * np.abs(col).max())[0]:
                jr, a = divmod(r, nv)
                if abs(j - jr) <= 2: blk[j - jr + 2, a, b] = True
    rows, cols = [], []
    for d in range(-2, 3):
        for a, b in zip(*np.where(blk[d + 2])):
            jr = np.arange(max(0, -d), min(n, n - d)); rows += list(jr * nv + a); cols += list((jr + d) * nv + b)
    _PAT[key] = sp.csc_matrix((np.ones(len(rows)), (rows, cols)), shape=(N, N))
    return _PAT[key]


_CACHE = {}


def simulate(p, n_t=300, t_end=None):
    """Cached on the full parameter set (api.solve calls solve and profile on the same values)."""
    key = (tuple(sorted(p.items())), n_t, t_end)
    if key not in _CACHE:
        if len(_CACHE) > 8: _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = _simulate(p, n_t, t_end)
    return _CACHE[key]


def _simulate(p, n_t, t_end):
    """-> (s, t [s], c_out_over_c0 [-], Y [n_t, n_cells, n_vars], Tpeak [K]); c_out = outlet CO2 mole fraction / feed fraction.
    With regen='purge' the arrays continue through the purge stage (s['t_switch'] marks it)."""
    s = _setup(p)
    bc = dict(yin=(s["yc"], s["yw"]), Tin=s["T0"], Nin=s["Nin"], Pout=s["Pt"])
    rhs, flux, ix, nv, n = _col(p, s, bc)
    y0 = _init(p, s, ix, nv, n)
    key = (tuple(ix), n)
    ts = np.linspace(0, t_end or 3 * s["tst"], n_t)
    cnt = [0]

    def guard(rh):  # raise (-> Monte-Carlo sample dropped / nominal fails loudly) instead of stalling in a stiff corner
        def g(t, y):
            cnt[0] += 1
            if cnt[0] > MAXEVAL: raise ValueError("sorbent ODE step guard: >%d rhs evaluations (stiff corner, lower n_cells or relax parameters)" % MAXEVAL)
            return rh(t, y)
        return g
    pat = _pattern(rhs, y0, nv, n, key)
    rhs = guard(rhs)
    kw = dict(method="BDF", rtol=RTOL, atol=RTOL * 1e-3, jac_sparsity=pat)  # ponytail: front shape set by the TVD grid, not by time error
    s |= dict(ix=ix, nv=nv, n=n, bc=bc, flux=flux)
    if p["regen"] == "purge":
        ev = lambda t, y: y[(n - 1) * nv] / s["yc"] - 0.05
        ev.terminal, ev.direction = True, 1
        sol = solve_ivp(rhs, (0, ts[-1]), y0, t_eval=ts, events=ev, **kw)
        ts_a, Ya = sol.t, sol.y.T
        s["t_switch"] = float(ts_a[-1] if not len(sol.t_events[0]) else sol.t_events[0][0])
        ysw = sol.y_events[0][0] if len(sol.t_events[0]) else sol.y[:, -1]
        pc = p["carrier"]
        bc2 = dict(yin=(0.0, 0.0), Tin=p["T_regen_K"], Nin=p["regen_flow_sccm"] * 1e-6 / 60 * 101325 / (R * 273.15) / s["A"], Pout=p["P_regen_kPa"] * 1e3)
        rhs2, flux2, *_ = _col(p, s, bc2); rhs2 = guard(rhs2)
        tr = np.linspace(0, p["t_regen_min"] * 60, max(n_t // 3, 20))
        sol2 = solve_ivp(rhs2, (0, tr[-1]), ysw, t_eval=tr, **kw)
        s |= dict(ysw=ysw, yend=sol2.y[:, -1], flux2=flux2, bc2=bc2, t2=sol2.t, Y2=sol2.y.T.reshape(len(sol2.t), n, nv))
        ts_a = np.concatenate((ts_a[ts_a <= s["t_switch"]], [s["t_switch"]])) if len(sol.t_events[0]) else ts_a
        Ya = np.vstack((Ya[: len(ts_a) - 1], ysw[None])) if len(sol.t_events[0]) else Ya
        t = np.concatenate((ts_a, s["t_switch"] + sol2.t[1:])); Y = np.vstack((Ya, sol2.y.T[1:])).reshape(len(t), n, nv)
    else:
        sol = solve_ivp(rhs, (0, ts[-1]), y0, t_eval=ts, **kw)
        t, Y = sol.t, sol.y.T.reshape(len(sol.t), n, nv)
    c_out = Y[:, n - 1, 0] / s["yc"]
    Tpeak = float(Y[:, :, ix["T"]].max()) if "T" in ix else s["T0"]
    return s, t, c_out, Y, Tpeak


def _first(t, x, thr):
    i = np.argmax(x >= thr)
    if x.max() < thr:
        return float("nan")
    return float(np.interp(thr, x[i - 1:i + 1], t[i - 1:i + 1])) if i else float(t[0])


def balance(p, n_t=400):
    """Column mass balances from the stored states (not an identity): (in - out - accumulated)/in for total moles and for CO2."""
    s, t, co, Y, _ = simulate(p, n_t=n_t)
    n, nv, ix, rb, eps, dz, A = s["n"], s["nv"], s["ix"], p["bed.rho_kg_m3"], p["bed.epsilon"], s["L"] / s["n"], s["A"]
    fl = [s["flux"](y.ravel()) for y in Y]
    Nin, Nout = np.array([s["bc"]["Nin"]] * len(t)), np.array([f["Nf"][-1] for f in fl])
    ycout = np.array([f["yc"][-1] for f in fl])
    hold = lambda f: eps * f["cT"] * dz * A
    tot = lambda f: np.sum(hold(f)) + np.sum(rb * dz * A * sum(f["Y"][:, ix["q" + a]] for a in s["ads"]))
    co2 = lambda f: np.sum(hold(f) * f["yc"]) + np.sum(rb * dz * A * f["Y"][:, ix["qCO2"]])
    Ii = lambda x: np.trapezoid(x, t) * A
    r_tot = (Ii(Nin) - Ii(Nout) - (tot(fl[-1]) - tot(fl[0]))) / Ii(Nin)
    r_co2 = (Ii(Nin * s["yc"]) - Ii(Nout * ycout) - (co2(fl[-1]) - co2(fl[0]))) / Ii(Nin * s["yc"])
    return {"total": float(r_tot), "CO2": float(r_co2), "Nout_min_over_Nin": float((Nout / Nin).min())}


def solve(p):
    s, t, co, Y, Tpk = simulate(p)
    n, ix = s["n"], s["ix"]
    f = s["flux"](Y[len(t) - 1 if p["regen"] == "off" else int(np.searchsorted(t, s["t_switch"]))].ravel())
    mass = p["bed.rho_kg_m3"] * s["A"] * s["L"]
    kq = ix["qCO2"]
    ia = len(t) - 1 if p["regen"] == "off" else int(np.searchsorted(t, s["t_switch"]))
    qa = float(Y[ia, :, kq].mean())
    ta = t[: ia + 1] if p["regen"] != "off" else t
    pCO2 = max(s["feed"]["CO2"] * R * s["T0"] / 1e5, 0)
    bad = int(s["T0"] < p["fit.T_lo_K"] or Tpk > p["fit.T_hi_K"] or pCO2 > p["fit.p_CO2_hi_bar"]
              or (s["hum"] and (p["RH_feed"] > p["fit.RH_hi"] or p["y_feed"] < p["fit.y_CO2_lo"] - 1e-9)))
    out = {"T_K": Tpk, "t_break5_min": _first(ta, co[: len(ta)], 0.05) / 60, "t_break50_min": _first(ta, co[: len(ta)], 0.5) / 60,
           "t_stoich_min": s["tst"] / 60, "capacity_mol_kg": qa, "dT_peak_K": float(Tpk - s["T0"]), "dP_Pa": float(f["P"][0] - s["Pt"]),
           "species.CO2_g.y_feed": p["y_feed"], "outside_fit_range": float(bad)}
    if s["hum"]: out["capacity_H2O_mol_kg"] = float(Y[ia, :, ix["qH2O"]].mean())
    if p["regen"] == "purge":
        qe = float(s["Y2"][-1, :, kq].mean())
        out |= {"cycle_capacity_mol_kg": qa - qe, "regen_fraction": (qa - qe) / qa if qa > 0 else float("nan"), "t_switch_min": s["t_switch"] / 60}
    return out


def profile(p):
    s, t, co, Y, Tpk = simulate(p)
    ix = s["ix"]
    return {"t_min": (t / 60).tolist(), "c_out_over_c0": co.tolist(), "T_out_K": (Y[:, -1, ix["T"]] if "T" in ix else np.full(len(t), s["T0"])).tolist()}


def tier0(p):
    s = _setup(p)
    kc = s["k"]["CO2"]
    ntu = kc * s["L"] * p["bed.epsilon"] / s["us"]  # LDF transfer units across the bed (gas residence)
    Qc = p["isotherm.Q"] * 1e3
    dTad = Qc * s["qs"] / p["cp_solid"] if p["energy"] == "nonisothermal" else 0.0
    tau_cool = p["bed.rho_kg_m3"] * p["cp_solid"] * (p["bed_id_cm"] / 100) / (4 * p["h_wall"])
    nums = {"NTU_ldf": ntu, "u_superficial_m_s": s["us"], "dT_adiabatic_K": dTad, "tau_cool_s": tau_cool, "t_stoich_s": s["tst"],
            "k_ldf_CO2_1_s": kc, "Pe_axial": s["Pe"]}
    if dTad > 5 and tau_cool > s["tst"]:
        return Regime.heat_limited, tau_cool / s["tst"], nums
    return (Regime.transport_limited if ntu < 1 else Regime.reaction_limited), max(ntu, 1 / ntu) / 3, nums


register(Vessel("sorbent", "Packed sorbent bed", DEFS, tier0, solve, {
    "t_break5_min": "min", "t_break50_min": "min", "t_stoich_min": "min", "capacity_mol_kg": "mol/kg", "dT_peak_K": "K",
    "dP_Pa": "Pa", "species.CO2_g.y_feed": "", "capacity_H2O_mol_kg": "mol/kg", "cycle_capacity_mol_kg": "mol/kg",
    "regen_fraction": "", "t_switch_min": "min", "outside_fit_range": ""},
    lambda p: f"bed_outlet,{p['T_K']:.0f}K", "tier1:EDSL-LDF-column-compressible",
    ["Wilkins 2017 13X breakthrough", "Nguyen 2021 CALF-20 breakthrough", "ruptura cross-check"], profile))
