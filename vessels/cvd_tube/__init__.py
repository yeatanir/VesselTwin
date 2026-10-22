"""MoS2 CVD tube, Tier 1: 1D laminar plug flow with Hertz-Knudsen boat sources and mass-transfer-limited wall/substrate
condensation. Outputs Mo:S ratio and MoO3 supersaturation at the substrate as distributions (passport).
Constants, species basis and their citations: see thermo.py and edge_data.json. Prior art checked: laminarSMOKE (flames, gas kinetics
only), ALD/ALE OpenFOAM solvers (surface coverage); no released CVD-tube solver exists, so Tier 2 is a case built around the PG solver.
Physics (each switchable by a ParamDef): gas-temperature lag (thermal Graetz, Nu), Stefan flow at boats/walls, finite-size boat
(disk) mass transfer, buoyancy criterion Gr/Re^2 (+ optional Sherwood enhancement), S8=4S2 speciation, substrate length/offset.
ponytail: dilute radial profile (1D bulk, no axial diffusion: Pe_axial is only ~3 at 100 sccm in 1 in, so axial diffusion and the
centreline-vs-bulk gap are NOT resolved), no re-evaporation from walls, vapour-phase Mo3O9 + S2 -> MoOxSy intermediates (Lei, Xie &
Yakobson, ACS Nano 15, 10525 (2021); rate-limiting chain-breaking step) are assumed instantaneous (supply = Mo-unit flux, barrier not
retrieved), H2 carrier does not reduce MoO3, no surface reaction (atomistic closures come in as edge/attachment laws).
Track M (optional, default off): substrate_uptake_model='reactive' replaces the substrate condensation driving force by an irreversible sulfurization
sink, wall_uptake_model in {condensation, reflecting, sticking, reactive}; see vessels/cvd_tube/reactive.py. PROPOSED reduced-order closure, NOT a validated
MoS2 kinetic law; all its constants are synthetic."""
import math
import numpy as np
from core import props
from core.dimensionless import Regime, classify, grashof
from core.params import ParamDef as P
from core.registry import Vessel, register
from vessels.cvd_tube import thermo, reactive, furnace

R = props.R
IN = 0.0254
P_STD, T_STD = 101325.0, 273.15
SYN = "synthetic"
LIT = "Simnad&Spilners Trans.AIME 1956 (OCR'd, unverified origin)"
ONOFF = ["on", "off"]
P1000 = 53.3  # Pa at 1000 K, Smolik et al. 2000 (doi:10.2172/752007), total (MoO3)n over solid MoO3

DEFS = [
    P("tube_id_in", "Tube inner diameter", "in", 1.0, 0.2, 4.0, group="geometry"),
    P("L_tube_cm", "Tube length", "cm", 100.0, 20, 300, group="geometry"),
    P("x_furnace_center_cm", "Furnace centre (from inlet)", "cm", 50.0, 0, 300, group="geometry"),
    P("L_hot_cm", "Furnace plateau length", "cm", 30.0, 1, 200, group="geometry"),
    P("ramp_cm", "Furnace ramp length (plateau to ambient)", "cm", 12.0, 0.5, 60, group="geometry"),
    P("x_S_boat_cm", "Sulfur boat position (from inlet)", "cm", 10.0, 0, 300, group="geometry"),
    P("x_MoO3_cm", "MoO3 boat position (from inlet)", "cm", 50.0, 0, 300, group="geometry"),
    P("x_substrate_cm", "Substrate leading edge downstream of MoO3 boat", "cm", 12.0, 0, 200, group="geometry"),
    P("substrate_length_cm", "Substrate length along the tube", "cm", 1.0, 0.1, 20, group="geometry"),
    P("substrate_width_cm", "Substrate width (extra deposition area across the tube)", "cm", 1.0, 0, 5, group="geometry"),
    P("T_substrate_offset_K", "Substrate temperature minus tube-wall temperature", "K", 0.0, -100, 100, 3.0, False, group="operation",
      help="0 = substrate at the furnace-profile wall temperature at its position; set for susceptors/ stages. T_boat_Mo_C, the wall profile (T_furnace_C) "
           "and this offset are independent inputs, so a substrate cooler than the source can be stated; where a paper does not state it the offset is an uncertain "
           "input (Track M scopes sigma 30 K via reactive.with_structural_sigma; the ParamDef sigma stays 3 K so stored default MC streams are unchanged)"),
    P("boat_area_MoO3_cm2", "MoO3 boat open area", "cm2", 2.0, 0.1, 50, group="geometry"),
    P("boat_area_S_cm2", "Sulfur boat open area", "cm2", 2.0, 0.1, 50, group="geometry"),
    P("T_furnace_C", "Furnace plateau temperature", "C", 750.0, 200, 1100, 10.0, False, group="operation"),
    P("T_ends_C", "Ambient (tube ends)", "C", 25.0, 0, 60, group="operation"),
    P("T_boat_Mo_C", "MoO3 boat temperature (below ~300 C the vapour-pressure law is an unverified extrapolation)", "C", 700.0, 200, 1100, 5.0, False, group="operation"),
    P("T_boat_S_C", "Sulfur boat temperature", "C", 180.0, 90, 400, 3.0, False, group="operation"),
    P("flow_sccm", "Carrier flow", "sccm", 100.0, 1, 2000, 0.03, group="operation"),
    P("carrier", "Carrier gas", "", "Ar", choices=["Ar", "N2", "H2"], group="operation",
      help="H2: only transport properties change; MoO3 reduction by H2 is not modelled"),
    P("pressure_Pa", "Total pressure", "Pa", 101325.0, 100, 2e5, group="operation"),
    # --- thermodynamics: literature basis (thermo.py) + legacy synthetic placeholders
    P("thermo_basis", "Vapour-pressure basis", "", "literature", choices=["literature", "legacy_synthetic"], group="thermo",
      help="legacy_synthetic = the old Clapeyron placeholders (MoO3.P_ref_Pa/dH, S.dH), kept to compare with the first OpenFOAM run"),
    P("MoO3.psat_model", "MoO3 vapour-pressure temperature law", "", "smolik_hsc", choices=["smolik_hsc", "simnad_ocr", "smolik_liquid_cc"], group="thermo",
      source="Smolik et al. 2000, doi:10.2172/752007 (Eq. 6, HSC-derived total (MoO3)n over solid MoO3, ~53 Pa at 1000 K); found by the Edison Literature agent; simnad_ocr = the earlier OCR'd fit, ~30x lower, likely misread"),
    P("MoO3.Tb_K", "MoO3 normal boiling point (pin of the liquid branch, psat_model=smolik_liquid_cc)", "K", 1428.0, 1100, 1700, 0.0, False,
      source="CRC Handbook (Haynes, 92nd ed., p. 4.77) as printed on https://en.wikipedia.org/wiki/Molybdenum_trioxide: '1,155 C ... 1,428 K (sublimes)'; "
             "cross-check: NIST WebBook C1313275 Antoine (Stull 1947, 1007-1424 K) gives 1 atm at 1430 K; secondary page for CRC, so flagged", group="thermo"),
    P("MoO3.liq_Bfac", "Factor on the Clausius-Clapeyron slope above the melting point (MC only)", "", 1.0, 0.1, 3.0, 0.0, True,
      source="ASSUMPTION: sigma 0.384 (set by thermo.with_liq_sigma) so p05-p95 of B spans the slopes of Fieser 1931 (via Blackburn 1954 Eq. 43) and Blackburn Eq. 14; both unopened, mutually inconsistent", group="thermo"),
    P("MoO3.logP_A", "log10 p[mmHg] = A/T + B log10 T + C : A", "K", -16140.0, -3e4, 0, source=LIT, group="thermo"),
    P("MoO3.logP_B", "... B", "", -5.53, -20, 5, source=LIT, group="thermo"),
    P("MoO3.logP_C", "... C", "", 30.69, 0, 60, source=LIT, group="thermo"),
    P("MoO3.P_ref_Pa", "MoO3 vapour pressure at 1000 K (scales the fit above; legacy basis: absolute)", "Pa", P1000, 1e-3, 1e5, 0.7,
      source="default = Smolik et al. 2000 HSC fit at 1000 K (doi:10.2172/752007); sigma 70 % since Berkowitz 1957 points are ~2x higher", group="thermo",
      help="literature basis: p = fit(T) * P_ref / fit(1000 K). legacy_synthetic basis: set 30 Pa to reproduce the first OpenFOAM run"),
    P("MoO3.n_oligomer", "Mo atoms per dominant vapour molecule (transport/Hertz-Knudsen)", "", 3, 1, 5, group="thermo",
      source="Berkowitz, Inghram & Chupka, J. Chem. Phys. 26, 842 (1957): (MoO3)3 dominant"),
    P("S.antoine_A", "Sulfur Antoine A (log10 p[Torr], t[C])", "", 6.69535, 3, 10, source="Antoine fit, cross-checked 423-823 K against West/Moses & Nash 1991 (within 3%) and Rau et al. 1973, doi:10.1016/S0021-9614(73)80089-8 (within ~5% for T>=600 K; Rau is out of range below 590 K)", group="thermo"),
    P("S.antoine_B", "Sulfur Antoine B", "C", 2285.37, 1000, 4000, source="Antoine fit, cross-checked 423-823 K against West/Moses & Nash 1991 (within 3%) and Rau et al. 1973, doi:10.1016/S0021-9614(73)80089-8 (within ~5% for T>=600 K; Rau is out of range below 590 K)", group="thermo"),
    P("S.antoine_C", "Sulfur Antoine C", "C", 155.0, 50, 300, source="Antoine fit, cross-checked 423-823 K against West/Moses & Nash 1991 (within 3%) and Rau et al. 1973, doi:10.1016/S0021-9614(73)80089-8 (within ~5% for T>=600 K; Rau is out of range below 590 K)", group="thermo"),
    P("S.P_scale", "Multiplier on the sulfur vapour pressure", "", 1.0, 0.1, 10.0, 0.3, source="uncertainty knob (the fit itself is cross-checked)", group="thermo"),
    P("S.dHf_S8_kJ", "Formation enthalpy of S8(g) from alpha-S", "kJ/mol", 100.416, 80, 120, 1.0, False,
      source="Jackson, Tiana & Walsh, Chem. Sci. 7, 1082 (2016) (experimental sublimation enthalpy)", group="thermo"),
    P("S.speciation", "Sulfur vapour speciation", "", "equilibrium", choices=["equilibrium", "S2"], group="thermo",
      help="equilibrium: S8 at the boat, S8 = 4 S2 (JANAF) in the hot zone; S2: all vapour is S2 (old assumption)"),
    P("MoO3.dH_kJmol", "[legacy_synthetic only] MoO3 sublimation enthalpy", "kJ/mol", 150.0, 50, 400, 5.0, False, source=SYN, group="thermo"),
    P("S.dH_kJmol", "[legacy_synthetic] S vaporisation enthalpy (anchored at 717.8 K)", "kJ/mol", 55.0, 20, 100, 3.0, False,
      source=SYN, group="thermo"),
    P("alpha_MoO3", "MoO3 evaporation coefficient", "", 0.1, 1e-3, 1.0, 0.5, source=SYN, group="model",
      help="no published value found; boats are gas-side limited anyway (alpha only matters below ~1e-3)"),
    P("alpha_S", "Sulfur evaporation coefficient", "", 1.0, 1e-3, 1.0, 0.3, source=SYN, group="model"),
    # --- transport
    P("Sh", "Sherwood number (laminar tube, const. wall T)", "", 3.66, 1, 10, 0.2, group="model", source="Incropera: fully developed laminar flow"),
    P("Nu", "Nusselt number for gas heating (laminar tube, const. wall T)", "", 3.66, 1, 10, 0.2, group="model",
      source="Incropera: fully developed laminar flow"),
    P("D_scale", "Multiplier on Fuller gas diffusivities", "", 1.0, 0.3, 3.0, 0.25, source=SYN, group="model",
      help="Fuller 1966 is good to ~5-10 % for known pairs; the MoO3 oligomer volume is estimated, hence 25 %"),
    P("gas_T_lag", "Gas temperature lags the wall (Graetz heating)", "", "on", choices=ONOFF, group="model"),
    P("stefan", "Stefan-flow (non-dilute) correction at boats and walls", "", "on", choices=ONOFF, group="model"),
    P("boat_Sh_model", "Boat gas-side transfer", "", "disk", choices=["disk", "tube"], group="model",
      help="disk: k = 4D/(pi a) for a disk of the boat's area into half-space (Carslaw & Jaeger); tube: Sh D/d_tube (old)"),
    P("buoyancy", "Buoyancy (horizontal-tube secondary flow)", "", "flag", choices=["off", "flag", "enhance"], group="model",
      help="flag: report Gr/Re^2 and Ra only; enhance: Sh *= (1 + max(Ri - Ri_c, 0))^buoy_exp"),
    P("Ri_c", "Gr/Re^2 above which natural convection competes with forced", "", 1.0, 0.01, 100, group="model", source="convention (Incropera)"),
    P("buoy_exp", "Sherwood enhancement exponent in buoyant regime", "", 0.25, 0, 1, 0.3, source=SYN, group="model",
      help="placeholder: no correlation verified for mass transfer in horizontal heated tubes at Re~3"),
]

DEFS = DEFS + reactive.RDEFS  # Track M switches (defaults reproduce the previous model exactly)
# Track N: thermal_model switch + furnace/quartz/gas/boat parameters (vessels/cvd_tube/furnace.py). Copies carry sigma 0 so the default Monte Carlo streams are
# unchanged; furnace.profile() uses the real sigmas. thermal_model = "legacy" (default) leaves every result bit-for-bit as before.
DEFS = DEFS + [P("thermal_model", "Thermal model", "", "legacy", choices=["legacy", "furnace"], group="model",
                 help="legacy: assumed tanh wall profile, wall-temperature boat/substrate (+ offset input); furnace: Track N zone/table profile, quartz network, "
                      "computed boat/substrate temperatures, see vessels/cvd_tube/furnace.py")] + furnace.tube_copies()


def twall(p, x):  # x in m -> K. Flat-top furnace; downstream of the S boat the wall is never colder than the S boat (heat belt)
    xc, Lh, w = p["x_furnace_center_cm"] / 100, p["L_hot_cm"] / 100, p["ramp_cm"] / 100 / 3
    if p.get("thermal_model", "legacy") == "furnace": return furnace.twall(p, x)
    Te, Tf = p["T_ends_C"] + 273.15, p["T_furnace_C"] + 273.15
    prof = Te + (Tf - Te) * 0.5 * (np.tanh((x - (xc - Lh / 2)) / w) - np.tanh((x - (xc + Lh / 2)) / w))
    return np.where(x >= p["x_S_boat_cm"] / 100, np.maximum(prof, p["T_boat_S_C"] + 273.15), prof)


def psat_MoO3(p, T): return thermo.psat_MoO3(p, T)
def psat_S(p, T): return thermo.psat_S(p, T)


_TG = np.linspace(250.0, 1600.0, 28)


def _kcarrier(car, T):  # carrier conductivity, tabulated (props are scalar math)
    return np.interp(T, _TG, [props.conductivity(car, t) for t in _TG])


def _stefan(yb, yw):
    """Film-theory factor F = ln((1-yb)/(1-yw))/(yw-yb) (>=1 for evaporation or suction; ->1 dilute). Mole fractions (scalars)."""
    yb, yw = min(yb, 0.999), min(yw, 0.999)
    d = yw - yb
    return math.log((1 - yb) / (1 - yw)) / d if abs(d) > 1e-12 else 1 / (1 - yw)


def _boat(p, sp, ps_mol, Tb, area, alpha, Nc, M, Dg, d):
    """Vapour molecules/s leaving a boat: plug flow of the carrier over a source, Hertz-Knudsen in series with gas-side transfer.
    ps_mol = saturation pressure of the vapour MOLECULE [Pa]."""
    Pt = p["pressure_Pa"]
    k_hk = alpha / np.sqrt(2 * np.pi * M * R * Tb)  # mol/m2/s/Pa
    a_eq = np.sqrt(area / np.pi)
    kg = (4 * Dg / (np.pi * a_eq) if p["boat_Sh_model"] == "disk" else p["Sh"] * Dg / d) / (R * Tb)
    ys = min(ps_mol / Pt, 0.999)
    if p["stefan"] == "off":
        k = 1 / (1 / k_hk + 1 / kg)
        return Nc * ys * (1 - np.exp(-k * area * Pt / Nc))
    n, y = 40, 0.0
    for _ in range(n):  # exponential sub-steps in mole fraction with the local Stefan factor
        k = 1 / (1 / k_hk + 1 / (kg * _stefan(y, ys)))
        y = ys + (y - ys) * np.exp(-k * Pt * (area / n) / (Nc / (1 - y)))
    return Nc * y / (1 - y)


def _buoyancy(p, Tw, Tg, Nc, i0, i1):
    """Gr, Re, Ri = Gr/Re^2, Ra at the worst wall-gas temperature difference between boat and substrate centre."""
    d, car, Pt = IN * p["tube_id_in"], p["carrier"], p["pressure_Pa"]
    dT = np.abs(Tw[i0:i1 + 1] - Tg[i0:i1 + 1])
    k = int(np.argmax(dT))
    Tm, dTm = float(0.5 * (Tw[i0 + k] + Tg[i0 + k])), float(dT[k])
    rho, mu = props.density(car, Tm, Pt), props.viscosity(car, Tm)
    u = Nc * R * Tm / Pt / (np.pi * d**2 / 4)
    Re = rho * u * d / mu
    Gr = grashof(1 / Tm, dTm, d, mu / rho)
    return {"dT_K": dTm, "Gr": Gr, "Re": Re, "Ri": Gr / Re**2, "Ra": Gr * props.prandtl(car, Tm)}


def march(p, n=400, condense=True):
    if p.get("thermal_model", "legacy") == "furnace": p = furnace.apply(p)
    d, car, Pt = IN * p["tube_id_in"], p["carrier"], p["pressure_Pa"]
    Nc = P_STD * p["flow_sccm"] * 1e-6 / 60 / (R * T_STD)
    nol, s2 = int(p["MoO3.n_oligomer"]), p["S.speciation"] == "S2" or p["thermo_basis"] == "legacy_synthetic"
    xs, xe = max(p["x_S_boat_cm"], 0) / 100, p["L_tube_cm"] / 100
    xM = p["x_MoO3_cm"] / 100
    dx = (xe - xs) / (n - 1)
    x0 = xM - np.floor((xM - xs) / dx) * dx  # grid node on the MoO3 boat; cell i spans [x0 + i dx, x0 + (i+1) dx]
    xin = x0 + dx * np.arange(n)
    xo, xm = xin + dx, xin + dx / 2  # cell exit (reported) and midpoint (where wall properties are taken: 2nd order in dx)
    Tout, Tw = twall(p, xo), twall(p, xm)
    xsub0 = (p["x_MoO3_cm"] + p["x_substrate_cm"]) / 100
    Ls = p["substrate_length_cm"] / 100
    xcen = xsub0 + Ls / 2
    fsub = np.clip(np.minimum(xin + dx, xsub0 + Ls) - np.maximum(xin, xsub0), 0, None) / dx  # fraction of each cell under the substrate
    insub = fsub > 0
    Twe = Tw + fsub * p["T_substrate_offset_K"]  # temperature the deposit sees
    Twe_out = Tout + ((xo >= xsub0) & (xo <= xsub0 + Ls)) * p["T_substrate_offset_K"]
    # gas bulk temperature: dTg/dx = Nu pi k (Tw-Tg)/(Nc cp_molar)  (Graetz, d cancels)
    ntuT = p["Nu"] * np.pi * _kcarrier(car, Tw) * dx / (Nc * props.GAS[car][3] * R)
    Tgl = np.empty(n)  # exit gas temperature of each cell; exact for a wall T linear across the cell: T_g = T_w - s L + (T_g0 - T_w0 + s L) e^-ntu
    Tin = twall(p, xin)
    sL = (Tout - Tin) / dx * dx / ntuT  # slope * relaxation length
    prev = float(Tin[0])
    ex_ = np.exp(-ntuT)
    for i in range(n):
        prev = Tgl[i] = Tout[i] - sL[i] + (prev - Tin[i] + sL[i]) * ex_[i]
    Tgx = Tgl if p["gas_T_lag"] == "on" else Tout
    Tg = 0.5 * (np.r_[Tgx[0], Tgx[:-1]] + Tgx)  # cell-mean gas T
    iM = int(round((xM - x0) / dx))
    icen = min(int(np.searchsorted(xo, xcen)), n - 1)
    bz = _buoyancy(p, Tout, Tgl, Nc, min(iM, icen), icen)
    Sh = p["Sh"] * ((1 + max(bz["Ri"] - p["Ri_c"], 0.0)) ** p["buoy_exp"] if p["buoyancy"] == "enhance" else 1.0)
    Tf = 0.5 * (Tg + Twe)
    DM = thermo.fuller_D(car, "MoO3", 1000.0, Pt, nol) * (Tf / 1000.0) ** 1.75 * p["D_scale"]
    DS = thermo.fuller_D(car, "S2", 1000.0, Pt) * (Tf / 1000.0) ** 1.75 * p["D_scale"]
    kmM, kmS = Sh * DM / d, Sh * DS / d
    psM, psS = psat_MoO3(p, Twe), psat_S(p, Twe)  # at the deposit's temperature
    # sulfur boat (S8 molecules, or S2 in the old basis)
    TbS, TbM = p["T_boat_S_C"] + 273.15, p["T_boat_Mo_C"] + 273.15
    nS = 2 if s2 else 8
    DbS = thermo.fuller_D(car, "S2" if s2 else "S8", TbS, Pt) * p["D_scale"]
    NS = nS * _boat(p, "S", float(psat_S(p, TbS)), TbS, p["boat_area_S_cm2"] * 1e-4, p["alpha_S"], Nc, (64.13 if s2 else 256.52) * 1e-3, DbS, d)
    NM = 0.0  # MoO3 formula units/s
    mpa = 0.5 if s2 else 0.125  # S-gas molecules per S atom (updated by speciation below)
    st = p["stefan"] == "on"
    sub_m, wall_m = p.get("substrate_uptake_model", "condensation"), p.get("wall_uptake_model", "condensation")
    legacy = sub_m == "condensation" and wall_m == "condensation"
    psW = psat_MoO3(p, Tw)  # at the bare wall (general path only)
    near = np.convolve(insub.astype(float), [1, 1, 1], "same") > 0
    need_S = np.ones(n, bool) if wall_m == "reactive" else (near if sub_m == "reactive" else np.zeros(n, bool))
    o = {k: np.zeros(n) for k in ("pM", "pS", "ss", "ssg", "flux", "NM", "NS", "Nt", "dM", "dMsub")}
    dep = {"M": 0.0, "S": 0.0, "Msub": 0.0}
    inlet = {"S": NS, "M": 0.0}
    wsub = p["substrate_width_cm"] / 100
    for i in range(n):
        if i == iM:
            DbM = thermo.fuller_D(car, "MoO3", TbM, Pt, nol) * p["D_scale"]
            NM = nol * _boat(p, "MoO3", float(psat_MoO3(p, TbM)) / nol, TbM, p["boat_area_MoO3_cm2"] * 1e-4, p["alpha_MoO3"], Nc,
                             nol * props.M_SPECIES["MoO3"] * 1e-3, DbM, d)
            inlet["M"] = NM
        Nt = Nc + NM / nol + NS * mpa
        Q = Nt * R * Tg[i] / Pt
        ex = wsub * fsub[i]
        A = (np.pi * d + ex) * dx
        pM = Pt * NM / Nt
        fM = _stefan(NM / nol / Nt, psM[i] / nol / Pt) if st else 1.0
        Nsat = psM[i] * Nt / Pt
        if legacy:
            o["flux"][i] = max(kmM[i] * fM * (pM - psM[i]) / (R * Tf[i]), 0.0)
            if condense and NM > Nsat:
                Nn = Nsat + (NM - Nsat) * np.exp(-kmM[i] * fM * A / Q)
                o["dM"][i] = NM - Nn
                o["dMsub"][i] = (NM - Nn) * ex / (np.pi * d + ex)
                NM = Nn
        else:  # Track M general path: wall and substrate sinks in parallel, each with its own closure (reactive.py)
            kmf = kmM[i] * fM
            pS2 = 0.0
            if need_S[i]:
                xs_ = 1.0 if s2 else float(thermo.s2_fraction(NS / Nt, Tg[i], Pt, p["S.dHf_S8_kJ"]))
                pS2 = Pt * NS * xs_ / 2 / Nt
            Ceq = p["C_eq_rxn_Pa"] * Nt / Pt
            Kw = Ks = Nweq = Nseq = 0.0
            if wall_m != "reflecting":
                if wall_m == "condensation": kw, Nweq = kmf, psW[i] * Nt / Pt
                elif wall_m == "sticking":
                    vk = p["wall_sticking"] * np.sqrt(R * Tw[i] / (2 * np.pi * nol * props.M_SPECIES["MoO3"] * 1e-3))
                    kw, Nweq = kmf * vk / (kmf + vk), psW[i] * Nt / Pt
                else: kw, Nweq = float(reactive.series(kmf, reactive.k_rxn(p, Tw[i], pS2))), Ceq
                Kw = kw * np.pi * d * dx / Q
            if ex > 0:
                if sub_m == "condensation": ks, Nseq = kmf, Nsat
                else: ks, Nseq = float(reactive.series(kmf, reactive.k_rxn(p, Twe[i], pS2))), Ceq
                Ks = ks * ex * dx / Q
            if sub_m == "reactive":  # flux a substrate at this cell would see (only evaluated near the substrate)
                o["flux"][i] = max(float(reactive.series(kmf, reactive.k_rxn(p, Twe[i], pS2))) * (pM - p["C_eq_rxn_Pa"]) / (R * Tf[i]), 0.0) if need_S[i] else 0.0
            else:
                o["flux"][i] = max(kmf * (pM - psM[i]) / (R * Tf[i]), 0.0)
            gw, gs = Kw * max(NM - Nweq, 0.0), Ks * max(NM - Nseq, 0.0)  # uptake rates only where the gas is above that sink's equilibrium
            if condense and gw + gs > 0:
                aw, as_ = Kw * (NM > Nweq), Ks * (NM > Nseq)
                Neq = (aw * Nweq + as_ * Nseq) / (aw + as_)
                Nn = Neq + (NM - Neq) * np.exp(-(aw + as_))
                o["dM"][i] = NM - Nn
                o["dMsub"][i] = (NM - Nn) * gs / (gw + gs)
                NM = Nn
        Nsat_S = nS * psS[i] * Nt / Pt  # S atoms; condenses when S8-equivalent pressure exceeds the liquid's
        if condense and NS > Nsat_S:
            Nn = Nsat_S + (NS - Nsat_S) * np.exp(-kmS[i] * A / Q)
            dep["S"] += NS - Nn
            NS = Nn
        o["NM"][i], o["NS"][i] = NM, NS
        Nt = Nc + NM / nol + NS * mpa
        o["Nt"][i] = Nt
    dep["M"], dep["Msub"] = o["dM"].sum(), o["dMsub"].sum()
    # speciation of the S atoms at the local gas T (vectorised post pass; two sweeps settle the mole count)
    xS = np.ones(n) if s2 else np.zeros(n)
    Nt = o["Nt"]
    for _ in range(0 if s2 else 2):
        xS = thermo.s2_fraction(np.maximum(o["NS"], 1e-30) / Nt, Tgx, Pt, p["S.dHf_S8_kJ"])
        Nt = Nc + o["NM"] / nol + o["NS"] * (xS / 2 + (1 - xS) / 8)
    o["Nt"], o["xS2"] = Nt, xS
    o["pM"] = Pt * o["NM"] / Nt
    o["pS"] = Pt * o["NS"] * xS / 2 / Nt  # S2 partial pressure
    o["pSat"] = Pt * o["NS"] / Nt  # S atoms as pressure-equivalent
    o["ss"] = o["pM"] / psat_MoO3(p, Twe_out)  # against the deposit's (wall/substrate) temperature
    o["ssg"] = o["pM"] / psat_MoO3(p, Tgx)  # against the gas temperature (what a gas-probe CFD reports)
    o["Tg"] = Tgx
    err = abs(inlet["M"] - NM - dep["M"]) / max(inlet["M"], 1e-30) + abs(inlet["S"] - NS - dep["S"]) / max(inlet["S"], 1e-30)
    return xo, Tout, o, dict(NM_in=inlet["M"], NS_in=inlet["S"], NM_out=NM, NS_out=NS, dep=dep, err=err, isub=int(np.searchsorted(xo, xsub0)),
                          xcen=xcen, buoy=bz, Twe=Twe_out, dx=dx, d=d, flow=Nc)


def _at(x, a, xq): return float(np.interp(xq, x, a))


def solve(p):
    x, T, o, m = march(p)
    xc, g = m["xcen"], lambda k: _at(x, o[k], m["xcen"])
    Ts = _at(x, m["Twe"], xc)
    pM, pS = g("pM"), g("pS")
    return {"T_K": Ts, "species.MoO3_g.p_Pa": pM, "species.S2_g.p_Pa": pS, "ratio_Mo_S": pM / max(pS, 1e-30),
            "supersaturation_MoO3": pM / float(psat_MoO3(p, Ts)), "flux_MoO3_mol_m2_s": g("flux"), "balance_err": float(m["err"]),
            "supersaturation_MoO3_gasT": pM / float(psat_MoO3(p, g("Tg"))), "T_gas_K": g("Tg"), "ratio_Mo_Satoms": pM / max(g("pSat"), 1e-30),
            "S2_fraction_of_S": g("xS2"), "Ri_buoyancy": m["buoy"]["Ri"], "Ra_buoyancy": m["buoy"]["Ra"],
            "MoO3_supply_mol_s": float(m["NM_in"]), "MoO3_to_substrate_frac": float(m["dep"]["Msub"] / max(m["NM_in"], 1e-30))}


FLAGS = ["Mo3O9+S2 -> MoOxSy intermediates (Lei, Xie, Yakobson ACS Nano 2021) assumed instantaneous: supply = Mo-unit flux",
         "radial profile unresolved: 1D bulk values (CFD axis differs from bulk, see PLAN.md)",
         "H2 carrier: MoO3 reduction not modelled", "S3-S7 vapour species neglected (S8 = 4 S2 only)"]


def profile(p):
    x, T, o, m = march(p)
    return {"x_cm": (x * 100).tolist(), "T_C": (T - 273.15).tolist(), "T_gas_C": (o["Tg"] - 273.15).tolist(),
            "p_MoO3_Pa": o["pM"].tolist(), "p_S2_Pa": o["pS"].tolist(),
            "ratio_Mo_S": (o["pM"] / np.maximum(o["pS"], 1e-30)).tolist(), "supersaturation_MoO3": o["ss"].tolist(),
            "supersaturation_MoO3_gasT": o["ssg"].tolist(), "x_substrate_cm": p["x_MoO3_cm"] + p["x_substrate_cm"],
            "x_substrate_center_cm": m["xcen"] * 100, "buoyancy": m["buoy"], "flags": FLAGS}


def tier0(p):
    if p.get("thermal_model", "legacy") == "furnace": p = furnace.apply(p)
    d, car, Pt = IN * p["tube_id_in"], p["carrier"], p["pressure_Pa"]
    Tf = p["T_furnace_C"] + 273.15
    Q0 = p["flow_sccm"] * 1e-6 / 60
    Qf = Q0 * Tf / T_STD * P_STD / Pt
    u = Qf / (np.pi * d**2 / 4)
    Re = props.density(car, Tf, Pt) * u * d / props.viscosity(car, Tf)
    Pr = props.prandtl(car, Tf)
    Lth = 0.05 * Re * Pr * d  # thermal entrance length
    avail = max((p["x_MoO3_cm"] + p["x_substrate_cm"] - (p["x_furnace_center_cm"] - p["L_hot_cm"] / 2)) / 100, 1e-3)
    dx = p["x_substrate_cm"] / 100 or 1e-3
    DM = float(thermo.fuller_D(car, "MoO3", Tf, Pt, int(p["MoO3.n_oligomer"]))) * p["D_scale"]
    x = np.linspace(p["x_MoO3_cm"] / 100, (p["x_MoO3_cm"] + p["x_substrate_cm"] + p["substrate_length_cm"] / 2) / 100, 400)
    s = np.clip(1 - psat_MoO3(p, twall(p, x)) / float(psat_MoO3(p, p["T_boat_Mo_C"] + 273.15)), 0, None)  # wall takes up only where colder than the boat
    Da = p["Sh"] * DM / d * np.pi * d / Qf * np.trapezoid(s, x)  # Da_eff, wall-uptake NTU with driving force (Track B R1)
    nums = {"Re": Re, "Pr": Pr, "L_thermal_cm": Lth * 100, "heated_length_cm": avail * 100, "Da_wall": Da, "Pe": u * d / DM}
    Nc = P_STD * Q0 / (R * T_STD)
    x = np.linspace(p["x_S_boat_cm"] / 100, p["L_tube_cm"] / 100, 200)
    Tw = twall(p, x)
    ntuT = p["Nu"] * np.pi * _kcarrier(car, Tw) * (x[1] - x[0]) / (Nc * props.GAS[car][3] * R)
    Tg = [Tw[0]]
    for i in range(1, len(x)): Tg.append(Tw[i] + (Tg[-1] - Tw[i]) * np.exp(-ntuT[i]))
    i1 = min(int(np.searchsorted(x, (p["x_MoO3_cm"] + p["x_substrate_cm"]) / 100)), len(x) - 1)
    b = _buoyancy(p, Tw, np.array(Tg), Nc, min(int(np.searchsorted(x, p["x_MoO3_cm"] / 100)), i1), i1)
    nums |= {"Gr_Re2": b["Ri"], "Ra": b["Ra"], "dT_wall_gas_K": b["dT_K"], "buoyancy_competes": float(b["Ri"] > p["Ri_c"])}
    if Lth > avail:
        return Regime.heat_limited, Lth / avail, nums
    r, m = classify(Da)  # Da>1: gas stays near wall saturation (transport/T-set); Da<1: supply (boat) limited
    return r, m, nums


_V = register(Vessel("cvd_tube", "MoS2 CVD tube", DEFS, tier0, solve, {
    "species.MoO3_g.p_Pa": "Pa", "species.S2_g.p_Pa": "Pa", "ratio_Mo_S": "", "supersaturation_MoO3": "",
    "flux_MoO3_mol_m2_s": "mol/m2/s", "balance_err": "", "T_gas_K": "K", "MoO3_supply_mol_s": "mol/s"},
    lambda p: f"substrate_x={p['x_substrate_cm']:.1f}cm", "tier1:plug-flow-wall-condensation",
    ["Wang 2014 shape vs position", "Govind Rajan kinetic phase diagram"], profile))


from vessels.cvd_tube import wulff  # noqa: E402  (after register: wulff imports this module)
_V.defs, _V.extras = wulff.DEFS, wulff.extras  # shape-model knobs join the same editable set
