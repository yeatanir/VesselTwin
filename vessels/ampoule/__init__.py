"""Sealed-ampoule chemical vapour transport, Tier 1.
Reaction family: A(s) + b B(g) <-> C(g) + e E(g)   (B = agent, C = A-carrying gas, E = optional co-product, e.g. Hg, S2),
optionally a 2nd carrier A + b2 B <-> C2 (AI2 + AI3 style) and agent dissociation B <-> x X (I2 <-> 2 I).
Speciation: constant-dH/dS equilibrium constants at source and sink, closed by one agent-atom budget (1-D root in p_B).
Flux: pseudo-binary film model per species (Fick + Stefan flow, exact for constant D c, Bird-Stewart-Lightfoot), bulk flow N
fixed by 'inert Ar stagnant' if Ar is present, else 'zero net agent-atom flux' (closed ampoule); transport of A = sum of C fluxes.
Closed forms kept for validation: `schafer_closed_form` (Schafer 1964 eq., prefactor 1.8e-4 original / 0.6e-4 corrected per
Schmidt et al. 2013, DOI 10.5772/55547 eq. 45); with equal D, no inert, the film model reduces EXACTLY to J = D dp/(R T L).
Convection (conv_model="buoyancy"): horizontal part = Taylor dispersion of the buoyant counterflow in a slot, D_eff/D = 1 + (Ra_s H/L)^2/362880
(constant derived here, 362880 = 1/int F^2, the Cormack-Leal-Imberger/Bejan shallow-cavity form), g -> g cos(tilt); vertical unstable part =
Nu-1 with Globe & Dropkin 1959 Nu = 0.069 Ra^(1/3) Pr^0.074 (Pr -> Sc by heat-mass analogy) above Ra_c; stable -> no enhancement.
conv_model="placeholder" is the old (Ra/Ra_c)^m scaling; "calibrated" (default) saturates both terms with a fit to the OpenFOAM scan (laminar, L=15 cm, square duct for tilt, CFD mesh sensitivity 4-16%). Ra_s uses the TOTAL (thermal + composition) density difference source/sink.
Prior art checked: no open implementation of Schafer's flux (TRAGMIN/CVTRANS are closed). Sources and what is NOT sourced: PLAN.md.
ponytail: constant dH/dS (van 't Hoff, no Cp), shared co-product species not coupled across reactions, slot not tube constant,
tilt = superposition of horizontal + vertical parts (no coupled maximum at intermediate tilt), Tm-based property evaluation,
radiation only through the imposed wall T profile (gas is optically thin for these halides; wall radiation sets T_source/T_sink)."""
import numpy as np
from scipy.optimize import brentq
from core import props
from core.dimensionless import Regime
from core.params import ParamDef as P
from core.registry import Vessel, register

R, G = props.R, 9.81
SYN = "synthetic"
JANAF = "NIST-JANAF I2(g), I(g) tables, 1000 K (janaf.nist.gov I-027, I-001)"

DEFS = [
    P("L_cm", "Ampoule length (diffusion path)", "cm", 15.0, 1, 100, group="geometry"),
    P("D_mm", "Ampoule inner diameter", "mm", 15.0, 3, 60, group="geometry"),
    P("tilt_deg", "Tilt from horizontal (+ = source end lower)", "deg", 0.0, -90, 90, group="geometry"),
    P("T_source_C", "Source zone temperature T2", "C", 900.0, 200, 1400, 5.0, False, group="operation"),
    P("T_sink_C", "Sink zone temperature T1", "C", 800.0, 150, 1400, 5.0, False, group="operation"),
    P("agent_mg_per_cm3", "Transport agent loading (agent B, default I2)", "mg/cm3", 3.0, 0.01, 30, 0.05, group="operation"),
    P("inert_Ar_mbar", "Non-transporting Ar backfill, pressure at 293 K", "mbar", 0.0, 0, 5000, 0.1, group="operation"),
    P("T_profile", "Wall temperature profile", "", "linear", choices=["linear", "two_zone"], group="operation",
      help="two_zone: isothermal source/sink zones joined by a linear ramp (two-zone furnace); changes the diffusion resistance"),
    P("zone_frac", "Isothermal length fraction at each end (two_zone)", "", 0.25, 0, 0.45, group="operation"),
    P("gas", "Gas for viscosity/conductivity (proxy for the mixture)", "", "I2", choices=["I2", "Ar", "N2"], group="operation"),
    P("n_I_per_C", "Agent atoms per transported carrier C (n in AI_n)", "", 2.0, 1, 6, group="thermo"),
    P("agent_x_atoms", "Agent atoms per agent molecule B (I2: 2)", "", 2.0, 1, 4, group="thermo"),
    P("agent_M_gmol", "Agent molar mass", "g/mol", 253.81, 20, 800, group="thermo", source="NIST-JANAF I2"),
    P("M_X_gmol", "Molar mass of the agent atom X", "g/mol", 126.904, 1, 300, group="thermo", source="IUPAC atomic weight (I)"),
    P("M_A_gmol", "Molar mass of transported solid A", "g/mol", 100.0, 10, 800, source=SYN, group="thermo"),
    P("nu_E", "Co-product moles E per C (A+bB=C+eE)", "", 0.0, 0, 3, group="thermo"),
    P("E_M_gmol", "Co-product molar mass", "g/mol", 64.13, 1, 400, group="thermo", help="default S2; used by binary diffusion and buoyancy"),
    P("dH_kJmol", "Reaction enthalpy dH (A(s)+b B -> C + e E)", "kJ/mol", 100.0, -300, 500, 5.0, False, source=SYN, group="thermo",
      help="from Materials Project/JARVIS solids + NIST-JANAF gases; placeholder here. Sourced values: presets ampoule__WO2_*"),
    P("dS_JmolK", "Reaction entropy dS", "J/mol/K", 60.0, -300, 400, 5.0, False, source=SYN, group="thermo"),
    P("dissociation", "Agent dissociation B <-> x X", "", "on", choices=["off", "on"], group="thermo",
      help="I2 <-> 2I matters for iodine above ~800 C; switch off for HgX2 agents"),
    P("dH_diss_kJmol", "Dissociation dH (I2 -> 2I, 1000 K)", "kJ/mol", 153.874, 0, 600, 3.0, False, source=JANAF, group="thermo"),
    P("dS_diss_JmolK", "Dissociation dS (I2 -> 2I, 1000 K)", "J/mol/K", 105.796, 0, 300, 3.0, False, source=JANAF, group="thermo"),
    P("n2_I_per_C", "Agent atoms in 2nd carrier AI_n2 (0 = off)", "", 0.0, 0, 6, group="thermo"),
    P("dH2_kJmol", "2nd carrier dH (A + n2/x B -> C2)", "kJ/mol", 150.0, -300, 500, 5.0, False, source=SYN, group="thermo"),
    P("dS2_JmolK", "2nd carrier dS", "J/mol/K", 80.0, -300, 400, 5.0, False, source=SYN, group="thermo"),
    P("diff_model", "Diffusivity model", "", "schafer", choices=["schafer", "binary"], group="model",
      help="schafer: one D = D0 (T/273)^T_exp (1 atm/P) for all species; binary: Fuller pair D + Blanc mixing"),
    P("D0_cm2s", "Diffusion coefficient at 273 K, 1 atm", "cm2/s", 0.1, 0.005, 2.0, 0.3, source="Schafer 1964 convention (0.1 cm2/s)",
      group="model", help="Schafer convention D = D0 (T/273)^1.75 (1 atm/P)"),
    P("T_exp", "Temperature exponent of D", "", 1.75, 1.5, 2.0, group="model", source="Schafer"),
    P("agent_V_fuller", "Fuller diffusion volume of agent B", "", 59.6, 5, 200, group="model", source="Fuller 1966 (I2 = 2 x 29.8)"),
    P("V_C_fuller", "Fuller volume of carrier C (binary model)", "", 80.0, 5, 300, source=SYN, group="model"),
    P("E_V_fuller", "Fuller volume of co-product E (binary model)", "", 45.8, 2, 200, source=SYN, group="model", help="default S2 = 2 x 22.9"),
    P("stefan", "Non-dilute treatment", "", "stefan", choices=["dilute", "stefan"], group="model",
      help="dilute: J = D dp/(RTL) (Schafer); stefan: film model with bulk flow (P/(P-pC)-type correction)"),
    P("conv_model", "Convection model", "", "calibrated", choices=["placeholder", "buoyancy", "calibrated"], group="model",
      help="calibrated: saturating, CFD-fitted (laminar OpenFOAM scan, docs/ampoule_convection_scan.json); buoyancy: uncalibrated Taylor+Globe-Dropkin (overshoots); placeholder: old (Ra/Ra_c)^m"),
    P("conv_c", "[calibrated] Taylor-term scale", "", 0.445, 0.01, 10, source="fit to OpenFOAM tilt-0 diameter scan D 10-60 mm (5 points, 3 params: weak constraint)", group="model"),
    P("conv_fmax", "[calibrated] saturation of f-1 (laminar, L=15 cm)", "", 7.05, 0.5, 50, source="fit to OpenFOAM tilt-0 diameter scan", group="model"),
    P("conv_n", "[calibrated] saturation sharpness", "", 0.632, 0.2, 5, source="fit to OpenFOAM tilt-0 diameter scan", group="model"),
    P("Ra_crit", "[placeholder model] Ra above which convection enhances transport", "", 1000.0, 10, 1e5, source=SYN, group="model"),
    P("conv_exp", "[placeholder model] enhancement exponent m in (Ra/Ra_c)^m", "", 0.25, 0.1, 0.5, source=SYN, group="model",
      help="laminar boundary-layer scaling Nu~Ra^1/4"),
    P("Ra_c_vertical", "Critical Ra, vertical heated-from-below layer", "", 1708.0, 100, 1e5, group="model",
      source="Chandrasekhar 1961 (infinite plates, rigid-rigid); a confined tube is higher"),
    P("conv_threshold", "Enhancement above which regime is 'convection_assisted'", "", 1.1, 1.001, 10, group="model", source=SYN),
    P("crystal_density_gcm3", "Crystal density of A (growth thickness)", "g/cm3", 5.0, 0.5, 25, 0.05, source=SYN, group="growth"),
    P("sink_area_frac", "Deposit area / tube cross-section", "", 1.0, 0.05, 20, group="growth"),
    P("schafer_prefactor", "Schafer closed-form prefactor (validation only)", "mol/h/(K^0.75 cm)", 1.8e-4, 1e-5, 1e-3, group="model",
      source="Schafer 1964 (1.8e-4); 0.6e-4 per Schmidt et al. 2013 eq. 45 note"),
]

# CFD scan (docs/ampoule_convection_scan.json): L = 15 cm, D 10-60 mm (A = D/L 0.067-0.4), laminar, Ra_s up to 1.64e6 (tilt 90, D 40)
SCAN_RA_MAX, SCAN_A = 1.64e6, (0.066, 0.41)
_FUL_I = 29.8  # Fuller 1966 atomic diffusion volume of I
_AR = (props.mass("Ar"), props.FULLER["Ar"])


def _K(dH, dS, T):
    return np.exp(-(dH * 1e3 - T * dS) / (R * T))


def _spec(p, T, P0):
    """Gas speciation (Pa) at T for agent budget P0 (Pa, in agent molecules): keys B, X, C1, E1, C2."""
    xb, n1, n2, e = p["agent_x_atoms"], p["n_I_per_C"], p["n2_I_per_C"], p["nu_E"]
    b1, K1 = n1 / xb, _K(p["dH_kJmol"], p["dS_JmolK"], T)  # K1 = pC pE^e / pB^b1 in bar^(1+e-b1)
    K2 = _K(p["dH2_kJmol"], p["dS2_JmolK"], T) if n2 else 0.0
    Kd = _K(p["dH_diss_kJmol"], p["dS_diss_JmolK"], T) if p["dissociation"] == "on" else 0.0  # pX^xb / pB

    def parts(pb):
        pX = (Kd * pb) ** (1 / xb) if Kd else 0.0
        c1 = (K1 * pb**b1 / e**e) ** (1 / (1 + e))  # e=0 -> K1 pb^b1
        c2 = K2 * pb ** (n2 / xb) if n2 else 0.0
        return pX, c1, c2

    def g(pb):
        pX, c1, c2 = parts(pb)
        return xb * pb + pX + n1 * c1 + n2 * c2 - xb * P0 / 1e5

    pb = brentq(g, 0.0, P0 / 1e5, xtol=1e-14, rtol=1e-13) if g(P0 / 1e5) > 0 else P0 / 1e5
    pX, c1, c2 = parts(pb)
    return {"B": pb * 1e5, "X": pX * 1e5, "C1": c1 * 1e5, "E1": e * c1 * 1e5, "C2": c2 * 1e5}


def _pC(p, T, P_I0):
    """Equilibrium p(carrier) in Pa at T for agent budget P_I0 (Pa, as agent molecules). Name kept for tier2."""
    return _spec(p, T, P_I0)["C1"]


def _phi(t):
    t = np.asarray(t, float)
    small = np.abs(t) < 1e-6
    return np.where(small, 1 + t / 2, t / -np.expm1(-np.where(small, 1.0, t)))


def _root(F, s):
    """Root of monotone F near 0 by bracket doubling from scale s."""
    f0 = F(0.0)
    if f0 == 0:
        return 0.0
    lo, hi = -s, s
    for _ in range(80):
        if F(lo) * F(hi) < 0:
            return brentq(F, lo, hi, xtol=1e-16, rtol=1e-12)
        lo, hi = lo * 2, hi * 2
    raise ValueError("no bulk-flow root")


def _fuller(Mi, Vi, Mj, Vj, T, Pa, texp):  # props.diffusivity form with explicit volumes, m2/s
    return 1e-7 * T**texp * np.sqrt(1 / Mi + 1 / Mj) / ((Pa / 101325.0) * (Vi ** (1 / 3) + Vj ** (1 / 3)) ** 2)


def _ra_legacy(p, Tm, Pm, dT):
    g = p["gas"]
    rho, mu, k, cp = props.density(g, Tm, Pm), props.viscosity(g, Tm), props.conductivity(g, Tm), props.cp_mass(g)
    nu, al, beta = mu / rho, k / (rho * cp), 1 / Tm
    L, D = p["L_cm"] / 100, p["D_mm"] / 1000
    ra_h = G * beta * (abs(dT) / L) * D**4 / (nu * al)  # horizontal tube with axial gradient (Rosenberger)
    th = np.radians(p["tilt_deg"])
    unstable = np.sin(th) * dT > 0  # heated from below
    ra_v = G * beta * abs(dT) * L**3 / (nu * al) if unstable else 0.0
    return ra_h * abs(np.cos(th)) + ra_v * abs(np.sin(th))


def _convection(p, Tm, Ptot, rho_src, rho_snk, D_C):
    """Flux enhancement f, effective Ra, validity flag. Ra_s = g |drho/rho| H^3/(nu D): solutal-thermal Rayleigh number."""
    rho = 0.5 * (rho_src + rho_snk)
    dr = (rho_snk - rho_src) / rho  # >0: sink end denser
    nu = props.viscosity(p["gas"], Tm) / rho
    Sc = nu / D_C
    L, H = p["L_cm"] / 100, p["D_mm"] / 1000
    th = np.radians(p["tilt_deg"])
    unstable = np.sin(th) * dr > 0  # lighter fluid below
    ra_h = G * abs(dr) * H**3 / (nu * D_C)
    A = H / L
    q = ra_h * A**2 * abs(np.cos(th))  # Taylor premise: Pe*A << 1 with Pe = Ra_s A
    f_h = 1 + (ra_h * A * abs(np.cos(th))) ** 2 / 362880.0
    ra_v = G * abs(dr) * L**3 / (nu * D_C) * abs(np.sin(th)) if unstable else 0.0
    nu_v = max(1.0, 0.069 * ra_v ** (1 / 3) * Sc**0.074) if ra_v > p["Ra_c_vertical"] else 1.0
    if p["conv_model"] == "calibrated":
        sat = lambda T: T / (1 + (T / p["conv_fmax"]) ** p["conv_n"]) ** (1 / p["conv_n"])
        stab = 1.0 if (unstable or np.sin(th) == 0) else 1 / (1 + ra_h * A * abs(np.sin(th)) / p["Ra_c_vertical"])  # stable axial gradient damps the counterflow: stratification number g dr H^4 sin/(L nu D) on the DUCT-HEIGHT scale (was L^3, which zeroed it at tilt -0.4 deg)
        f = 1 + sat(p["conv_c"] * (f_h - 1)) * stab + sat(nu_v - 1)
        ra = ra_h * abs(np.cos(th)) + ra_v
        ok = ra <= SCAN_RA_MAX and SCAN_A[0] <= A <= SCAN_A[1] or (f - 1 < 0.01 and A <= SCAN_A[1])  # f -> 1 is safe below the scan
        return f, ra, float(ok), dr, Sc
    ok = q <= 1.0 and (ra_v <= p["Ra_c_vertical"] or (1.5e5 <= ra_v <= 6.8e8 and 0.02 <= Sc <= 8750))  # Globe-Dropkin range
    return f_h + nu_v - 1, ra_h * abs(np.cos(th)) + ra_v, float(ok), dr, Sc


def _core(p):
    T2, T1 = p["T_source_C"] + 273.15, p["T_sink_C"] + 273.15
    Tm = 0.5 * (T1 + T2)
    P0 = p["agent_mg_per_cm3"] * 1e3 / p["agent_M_gmol"] * R * Tm  # Pa, agent molecules at the mean temperature
    pAr = p["inert_Ar_mbar"] * 100 * Tm / 293.15
    n1, n2, xb = p["n_I_per_C"], p["n2_I_per_C"], p["agent_x_atoms"]
    names = ["B", "X", "C1", "E1", "C2"]
    M = np.array([p["agent_M_gmol"], p["M_X_gmol"], p["M_A_gmol"] + n1 * p["M_X_gmol"], p["E_M_gmol"], p["M_A_gmol"] + n2 * p["M_X_gmol"]])
    V = np.array([p["agent_V_fuller"], _FUL_I, p["V_C_fuller"], p["E_V_fuller"], p["V_C_fuller"]])
    x = np.array([xb, 1.0, n1, 0.0, n2])
    if pAr > 0:
        names, M, V, x = names + ["Ar"], np.append(M, _AR[0]), np.append(V, _AR[1]), np.append(x, 0.0)
    L, area = p["L_cm"] / 100, np.pi * (p["D_mm"] / 2000) ** 2
    if p["T_profile"] == "two_zone":  # resistance integral of dx/T^(T_exp-1) over isothermal ends + linear ramp, vs Schafer's Tm convention
        zf = p["zone_frac"]; xs = np.linspace(0, 1, 401)
        Tx = np.interp(xs, [0, zf, 1 - zf, 1], [T2, T2, T1, T1])
        a = p["T_exp"] - 1
        Leff = L * Tm**a * np.trapezoid(Tx**-a, xs)
    else:
        Leff = L  # ponytail: linear profile evaluated at Tm (Schafer convention)

    def state(lam):
        """Ends at agent budgets P0 (1 +- lam/2) (lam = steady-state source/sink agent imbalance), Stefan film flux with bulk flow N."""
        s2, s1 = _spec(p, T2, P0 * (1 + lam / 2)), _spec(p, T1, P0 * (1 - lam / 2))
        Ptot = 0.5 * (sum(s2.values()) + sum(s1.values())) + pAr
        ps2, ps1 = np.array([s2[k] for k in names[:5]]), np.array([s1[k] for k in names[:5]])
        if pAr > 0:
            ps2, ps1 = np.append(ps2, Ptot - ps2.sum()), np.append(ps1, Ptot - ps1.sum())
        y2, y1 = ps2 / Ptot, ps1 / Ptot
        ym = 0.5 * (y2 + y1)
        if p["diff_model"] == "schafer":
            Di = np.full(len(names), p["D0_cm2s"] * 1e-4 * (Tm / 273.15) ** p["T_exp"] * (101325.0 / Ptot))
        else:  # Fuller pair diffusivities mixed by Blanc's law
            Di, idx = np.zeros(len(names)), np.arange(len(names))
            for i in range(len(names)):
                w = ym.copy(); w[i] = 0
                w = w / max(w.sum(), 1e-30)
                Dij = _fuller(M[i], V[i], M, V, Tm, Ptot, p["T_exp"])
                Di[i] = 1.0 / np.sum(np.where(idx == i, 0.0, w / Dij))
        k = Di * Ptot / (R * Tm) / Leff  # film coefficients D_i c / L
        Nv = lambda N: k * (_phi(N / k) * y2 - _phi(-N / k) * y1)
        if p["stefan"] == "dilute":
            Nsp = k * (y2 - y1)
        else:
            F = (lambda N: Nv(N)[-1]) if pAr > 0 else (lambda N: float(x @ Nv(N)))  # inert stagnant, else zero net agent-atom flux
            Nsp = Nv(_root(F, max(abs(F(0.0)), 1e-12 * k.max()) / max(ym[-1] if pAr > 0 else float(x @ ym), 1e-9) * 2 + 1e-18))
        return dict(s2=s2, s1=s1, ps2=ps2, ps1=ps1, Ptot=Ptot, Di=Di, Nsp=Nsp)

    st = state(0.0)
    if pAr > 0 and p["stefan"] == "stefan":  # with inert present both closure laws must hold: solve the agent imbalance lam
        G_ = lambda lam: float(x @ state(lam)["Nsp"])
        for s_ in (0.02, 0.2, 0.8, 1.6):
            if G_(-s_) * G_(s_) < 0:
                st = state(brentq(G_, -s_, s_, xtol=1e-12))
                break
        else:
            raise ValueError("no steady agent imbalance")
    Ptot, ps2, ps1, Nsp, Di = st["Ptot"], st["ps2"], st["ps1"], st["Nsp"], st["Di"]
    D = Di[2]  # carrier
    dp = ps2[2] - ps1[2]
    J = D * dp / (R * Tm * Leff)  # dilute Fick flux of the carrier, mol/m2/s (Schafer form)
    Jnet = Nsp[2] + Nsp[4]  # mol A / m2 / s (each carrier holds one A)
    bal = abs(float(x @ Nsp)) / max(float(np.sum(np.abs(x * Nsp))), 1e-300)
    rho2, rho1 = (ps2 @ M) * 1e-3 / (R * T2), (ps1 @ M) * 1e-3 / (R * T1)
    if p["conv_model"] == "placeholder":
        Ra = _ra_legacy(p, Tm, Ptot, T2 - T1)
        f, ok, dr, Sc = max(1.0, (Ra / p["Ra_crit"]) ** p["conv_exp"]), 1.0, np.nan, np.nan
    else:
        f, Ra, ok, dr, Sc = _convection(p, Tm, Ptot, rho2, rho1, D)
    return dict(T=Tm, p2=ps2[2], p1=ps1[2], dp=dp, J=J, area=area, Ra=Ra, f=f, Ptot=Ptot, D=D, Jnet=Jnet, stefan=Jnet / J if J else 1.0,
                bal=bal, ok=ok, drho=dr, Sc=Sc, Leff=Leff, s2=st["s2"], s1=st["s1"], pAr=pAr, Nsp=dict(zip(names, Nsp)))


def schafer_closed_form(p):
    """Schafer's transport equation (Schmidt et al. 2013 eq. 45), mol A / h, for the single carrier C1 (j/i = 1)."""
    c = _core(p)
    q, s = c["area"] * 1e4, p["L_cm"]
    return p["schafer_prefactor"] * (c["dp"] / c["Ptot"]) * c["T"] ** 0.75 * q / s


def solve(p):
    c = _core(p)
    rate = c["Jnet"] * c["f"] * c["area"]  # mol A / s
    dens = p["crystal_density_gcm3"] * 1e6  # g/m3
    return {"T_K": c["T"], "species.AIn_g.p_source_Pa": c["p2"], "species.AIn_g.p_sink_Pa": c["p1"], "dp_Pa": c["dp"],
            "flux_diffusion_mol_m2_s": c["J"], "Ra": float(c["Ra"]), "convection_enhancement": float(c["f"]),
            "transport_rate_mmol_h": rate * 3.6e6, "P_total_Pa": c["Ptot"], "stefan_factor": c["stefan"],
            "mass_rate_mg_h": rate * p["M_A_gmol"] * 3.6e6, "growth_rate_mm_day": rate * p["M_A_gmol"] / dens / (c["area"] * p["sink_area_frac"]) * 86400e3,
            "agent_balance_err": c["bal"], "convection_in_range": c["ok"], "Sc": float(c["Sc"])}


def tier0(p):
    c = _core(p)
    if p["conv_model"] == "placeholder":
        r = c["Ra"] / p["Ra_crit"]
        nums = {"Ra": c["Ra"], "Ra_crit": p["Ra_crit"], "enhancement": c["f"], "dp_Pa": c["dp"], "P_total_Pa": c["Ptot"]}
        return (Regime.convection_assisted, r, nums) if r >= 1 else (Regime.transport_limited, 1 / max(r, 1e-12), nums)
    nums = {"Ra_s": float(c["Ra"]), "enhancement": float(c["f"]), "dp_Pa": c["dp"], "P_total_Pa": c["Ptot"], "convection_in_range": c["ok"]}
    r = (c["f"] - 1) / (p["conv_threshold"] - 1)
    return (Regime.convection_assisted, r, nums) if r >= 1 else (Regime.transport_limited, 1 / max(r, 1e-12), nums)


register(Vessel("ampoule", "Sealed ampoule CVT", DEFS, tier0, solve, {
    "species.AIn_g.p_source_Pa": "Pa", "species.AIn_g.p_sink_Pa": "Pa", "dp_Pa": "Pa", "flux_diffusion_mol_m2_s": "mol/m2/s",
    "Ra": "", "convection_enhancement": "", "transport_rate_mmol_h": "mmol/h", "P_total_Pa": "Pa", "stefan_factor": "",
    "mass_rate_mg_h": "mg/h", "growth_rate_mm_day": "mm/day", "agent_balance_err": "", "convection_in_range": "", "Sc": ""},
    lambda p: f"sink_T={p['T_sink_C']:.0f}C", "tier1:schafer-multispecies-stefan+buoyancy",
    ["Schafer diffusion-limited flux", "Schmidt et al. 2013 WO2/HgX2 rates", "Globe-Dropkin 1959", "NASA convection studies"]))
