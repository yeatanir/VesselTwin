"""MoS2 CVD tube, Track N: reduced-order FURNACE and FLOW description (thermal_model = "furnace"; the default "legacy" is untouched).

What it adds to the legacy model (one assumed tanh wall profile, gas heated by a constant-Nu Graetz lag, boat/substrate at the wall temperature):
 N1  axial furnace profile T_wall(x): 1-3 zones, heated length (L_hot_cm), erf end ramps (ramp_cm = 10-90 % distance), erf zone blends, an optional
     measured table "x_cm:T_C;x_cm:T_C;..." (wall_profile_table), a profile offset; boats/substrate may be placed relative to the tube centre.
     T_wall is the FURNACE BORE / heating-element temperature a user reads (or measures with a thermocouple on the outside of the tube).
 N2  quartz tube: radial resistance network element -> quartz outer surface (radiation across the gap, effective emissivity, plus a gap
     conduction term) -> conduction through the wall -> inner surface -> gas. Quartz is treated as TWO-BAND: transparent below a cutoff wavelength
     (default 4 um, fraction quartz_nir_transmit) and opaque above it; the transparent band lets the element radiate DIRECTLY onto the boat and
     substrate (Planck band fractions). Axial conduction along the quartz is not solved; its fin length sqrt(k A R') is reported and checked
     against the ramp length. quartz_coupling = "off" takes T_wall as the inner-wall temperature (used for the CFD comparison).
 N3  gas: ideal-gas expansion of the sccm flow, u(x), Re, thermal and mass Peclet, hydrodynamic and thermal entrance lengths, gas heating by one of
     two models: gas_model = "energy_2d" (default: steady axisymmetric energy equation with a PRESCRIBED Poiseuille mass-flux profile, axial and radial
     conduction, T-dependent conductivity, hybrid upwind scheme; gives centreline and mixing-cup temperature) or "graetz_1d" (bulk march with the
     Hausen developing-flow Nusselt number, Nu_inf = the `Nu` ParamDef = 3.66; no radial information, no axial conduction). Gr, Ri = Gr/Re^2,
     Ra with a buoyancy flag; boat->substrate residence time (plug and centreline bounds), axial transport via Taylor-Aris dispersion.
 N4  boat and substrate: steady two-band radiative + convective + contact balance with the local quartz, gas and element -> T_boat, T_substrate
     (outputs), and a lumped time constant giving the lag behind a furnace ramp. boat_temperature = "input" keeps the legacy T_boat_Mo_C input.
 N5  profile(values, n=200) -> the dict documented below, with p05/p95 over the model's Monte Carlo sigmas.

ponytail / limits (also repeated in profile()["notes"]): prescribed velocity profile (no momentum equation, no radial velocity, no radial T-dependence of
the velocity shape), constant cp, no gas radiation (Ar, N2, H2 are transparent), no axial radiation (light-pipe) in the quartz, no evaporation
heat sink at the boat (about mW), no flow through the annulus, no natural-convection correction to the heat transfer (Ri is only FLAGGED),
laminar only (Re < 2300 flag). Boat/substrate properties and the element-quartz coupling are SYNTHETIC unless a source is printed in the ParamDef.

profile() dict schema ("cvd_tube.furnace.profile/1"); every array has length n; units in ["units"]:
  schema, thermal_model, gas_model, n
  x_cm                       axial position from the inlet [cm]
  T_wall_K                   furnace bore / element temperature (the input profile) [K]
  T_quartz_K                 inner quartz surface temperature seen by the gas [K]
  T_gas_centre_K             gas temperature on the axis (energy_2d; = mean for graetz_1d) [K]
  T_gas_mean_K               mixing-cup (bulk) gas temperature [K]
  T_boat_K, T_substrate_K    steady temperature a boat-type / substrate-type body would have at x [K]
  u_mean_m_s                 area-mean axial velocity [m/s] (energy_2d: from the prescribed mass-flux profile at the local density; graetz_1d: m_dot/(rho(T_mean) A))
  u_centre_m_s               axis velocity [m/s] (graetz_1d: 2 u_mean)
  Re, Pe_thermal, Pe_mass    Reynolds, Re*Pr, u d / D_MoO3 (D from thermo.fuller_D at the local gas T)
  Gr, Ri, Ra                 Grashof (dT = |T_quartz - T_gas_mean|), Gr/Re^2, Gr*Pr
  tau_cum_s                  cumulative plug-flow residence time from the inlet [s]
  flags                      {laminar, buoyancy_matters, axial_conduction_matters, thermally_developed}: arrays of 0/1
  p05, p95                   {name: array} for the temperature, u, Re and Ri arrays over the Monte Carlo (empty if n_mc = 0)
  stations                   {boat_MoO3, boat_S, substrate}: dict of scalars at each station (x_cm, T_*, u, Re, Ri, flags, T_body_p05/p95,
                             tau_body_s, boat_lag_K for the ramp rate furnace_ramp_K_min)
  scalars                    entrance lengths, x_heat_start_cm, residence boat->substrate (plug, centreline), axial diffusion/dispersion
                             times, Pe_transport, carried_by, energy_balance_residual, quartz fin length, ...
  units, notes (assumptions, list of str), constants (name -> value, unit, source, p of every furnace ParamDef used)
"""
from dataclasses import replace
import math
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from core import props
from core.params import ParamDef as P

R = props.R
SB = 5.670374419e-8  # W/m2/K4 (CODATA exact-derived)
C2 = 14387.77  # um K, second radiation constant (CODATA)
IN = 0.0254
SYN = "synthetic"
GE124 = ("GE 124 fused quartz datasheet, SPI Supplies, https://www.2spi.com/catalog/documents/QuartzTechnicalData.pdf (opened; values READ FROM THE FIGURES, "
         "reading uncertainty stated)")

# NIST WebBook fluid data, argon, 0.101325 MPa isobar, https://webbook.nist.gov/cgi/fluid.cgi?ID=C7440371 (opened): T[K], cp[kJ/kg/K], mu[uPa s], k[W/m/K]
NIST_AR = np.array([[300, 0.52154, 22.741, 0.017837], [400, 0.52094, 28.704, 0.022516], [500, 0.52069, 34.078, 0.026726], [600, 0.52057, 38.997, 0.030573],
                    [700, 0.52050, 43.556, 0.034134], [800, 0.52046, 47.825, 0.037463], [900, 0.52043, 51.855, 0.040601], [1000, 0.52041, 55.686, 0.043581],
                    [1100, 0.52039, 59.349, 0.046428], [1200, 0.52038, 62.869, 0.049161], [1300, 0.52037, 66.266, 0.051796], [1400, 0.52037, 69.557, 0.054347]])
ZONES = ["1", "2", "3"]
_TAG = "furnace model (Track N); "
FDEFS = [
    # N1 furnace profile
    P("furnace_zones", "Number of heating zones (1-3; T_furnace_C is zone 1, T_zone2_C/T_zone3_C the others)", "", 1, 1, 3, group="furnace", source=SYN,
      help=_TAG + "zones are equal length, together L_hot_cm, centred on x_furnace_center_cm"),
    P("T_zone2_C", "Zone 2 setpoint", "C", 750.0, 25, 1200, 10.0, False, group="furnace", source=SYN, help=_TAG + "used if furnace_zones >= 2"),
    P("T_zone3_C", "Zone 3 setpoint", "C", 750.0, 25, 1200, 10.0, False, group="furnace", source=SYN, help=_TAG + "used if furnace_zones = 3"),
    P("zone_blend_cm", "Zone-to-zone transition length (10-90 %)", "cm", 4.0, 0.5, 30, 0.3, True, group="furnace", source=SYN,
      help=_TAG + "erf blend between adjacent zone setpoints"),
    P("S_heat_belt", "Sulfur heat belt keeps the wall at least at T_boat_S_C downstream of the S boat (legacy rule)", "", "on", choices=["on", "off"], group="furnace",
      help=_TAG + "off for a measured profile that already includes any belt"),
    P("T_wall_offset_K", "Offset added to the whole furnace profile", "K", 0.0, -150, 150, 5.0, False, group="furnace", source=SYN,
      help=_TAG + "reading/thermocouple uncertainty of the profile (sigma 5 K is an assumption)"),
    P("positions_from_centre", "Interpret boat positions relative to the tube centre", "", "off", choices=["off", "on"], group="geometry",
      help=_TAG + "on: x_MoO3 = L_tube/2 + dx_MoO3_from_centre_cm, x_S_boat = L_tube/2 + dx_S_from_centre_cm (the substrate stays relative to the MoO3 boat)"),
    P("dx_MoO3_from_centre_cm", "MoO3 boat position relative to the tube centre", "cm", 0.0, -150, 150, group="geometry", source="user input"),
    P("dx_S_from_centre_cm", "Sulfur boat position relative to the tube centre", "cm", -40.0, -150, 150, group="geometry", source="user input"),
    # N2 quartz tube
    P("quartz_wall_mm", "Quartz tube wall thickness", "mm", 2.0, 0.5, 8.0, 0.2, False, group="furnace", source=SYN,
      help=_TAG + "typical supplier value, no datasheet opened; outer diameter = inner + 2 wall"),
    P("quartz_k_W_mK", "Fused quartz thermal conductivity, 800-1300 K", "W/m/K", 1.9, 1.0, 3.2, 0.1, True, group="furnace",
      source=GE124 + ": 'Thermal conductivity: 1.4 W/m C' printed (room T); figure 'Thermal Conductivity' read 1.9 at 500-800 C (estimated, dashed), 2.0 at 1000 C, 2.3 at 1300 C; +-0.15"),
    P("quartz_emis_LW", "Quartz emissivity beyond the cutoff wavelength (opaque band)", "", 0.85, 0.4, 1.0, 0.07, False, group="furnace", source=SYN,
      help=_TAG + "no emissivity source could be opened (Petrov & Reznik 1972 closed); sweep 0.5-0.95 in the benchmark"),
    P("quartz_nir_transmit", "Quartz transmission below the cutoff wavelength (incl. reflection losses)", "", 0.9, 0.3, 1.0, 0.04, False, group="furnace",
      source=GE124 + ": 'Fused Quartz Average Transmittance Curves (includes surface reflection losses)', type 124, 1 and 10 mm: about 90-93 % from 0.3 to about 3.5 um; read from the figure, +-0.04"),
    P("quartz_cutoff_um", "Quartz cutoff wavelength (transparent below, opaque above)", "um", 4.0, 2.0, 6.0, 0.3, False, group="furnace",
      source=GE124 + ": the 124 curves fall steeply between about 3.5 and 4.5 um (10 mm sample falls first); task statement 'opaque beyond about 4 um'"),
    P("element_emis", "Heating-element / furnace bore emissivity", "", 0.8, 0.3, 1.0, 0.1, False, group="furnace", source=SYN),
    P("gap_conduction_W_m2K", "Conduction+convection across the element-quartz gap (per outer quartz area)", "W/m2/K", 5.0, 0.0, 40.0, 3.0, False, group="furnace", source=SYN,
      help=_TAG + "radiation across the gap is computed separately"),
    P("quartz_coupling", "Radial element-quartz network", "", "on", choices=["on", "off"], group="furnace",
      help=_TAG + "off: T_wall is taken as the inner quartz wall temperature (what a CFD with a wall-temperature condition assumes)"),
    # N3 gas
    P("gas_model", "Gas heating model", "", "energy_2d", choices=["energy_2d", "graetz_1d"], group="model",
      help=_TAG + "energy_2d: axisymmetric energy equation, prescribed Poiseuille mass flux, axial conduction (centreline + mixing-cup T); graetz_1d: Hausen Nu bulk march"),
    P("gas_props", "Carrier gas property source in the furnace model", "", "auto", choices=["auto", "kinetic", "nist_ar", "cfd_const"], group="model",
      help=_TAG + "auto: NIST argon table (opened, 300-1400 K) for Ar else kinetic theory (core.props); cfd_const: the stored CFD's constant mu, Pr, cp (at T_furnace)"),
    # N4 boat and substrate
    P("boat_temperature", "MoO3 boat and substrate temperatures", "", "computed", choices=["computed", "input"], group="model",
      help=_TAG + "computed: from the radiative+convective+contact balance (outputs); input: T_boat_Mo_C and T_substrate_offset_K as given (legacy override)"),
    P("boat_emis", "Boat emissivity (both bands)", "", 0.7, 0.2, 1.0, 0.1, False, group="furnace", source=SYN),
    P("boat_nir_abs", "Boat absorptivity/emissivity below the cutoff wavelength", "", 0.5, 0.05, 1.0, 0.15, False, group="furnace", source=SYN,
      help=_TAG + "white alumina low, quartz boats ~0 (transparent)"),
    P("boat_mass_g", "Boat plus charge mass", "g", 5.0, 0.5, 100, 0.3, True, group="furnace", source=SYN),
    P("boat_cp_J_kgK", "Boat plus charge specific heat", "J/kg/K", 900.0, 400, 1500, 0.15, True, group="furnace", source=SYN),
    P("boat_contact_W_m2K", "Boat-to-tube-floor contact conductance (per open boat area)", "W/m2/K", 30.0, 0.0, 300, 0.7, True, group="furnace", source=SYN),
    P("boat_area_factor", "Radiating/convecting area over the open boat area", "", 3.0, 1.0, 10.0, 0.2, True, group="furnace", source=SYN),
    P("sub_emis", "Substrate emissivity (both bands)", "", 0.7, 0.2, 1.0, 0.1, False, group="furnace", source=SYN),
    P("sub_nir_abs", "Substrate absorptivity below the cutoff wavelength", "", 0.5, 0.05, 1.0, 0.15, False, group="furnace", source=SYN),
    P("sub_mass_g", "Substrate mass", "g", 0.12, 0.01, 10, 0.2, True, group="furnace", source=SYN, help="1 cm2 x 0.525 mm Si, density 2.33 g/cm3 (assumed, not opened)"),
    P("sub_cp_J_kgK", "Substrate specific heat", "J/kg/K", 800.0, 400, 1200, 0.1, True, group="furnace", source=SYN),
    P("sub_contact_W_m2K", "Substrate-to-boat/tube contact conductance", "W/m2/K", 30.0, 0.0, 300, 0.7, True, group="furnace", source=SYN),
    P("body_Nu", "Nusselt number of a small body in the gas (conduction limit)", "", 2.0, 0.5, 10.0, 0.3, True, group="furnace",
      source="convention: Nu = 2 is the conduction limit of a sphere in a quiescent medium; convective enhancement at Re ~ 1 is a few tens of percent, absorbed in sigma"),
    P("furnace_ramp_K_min", "Furnace ramp rate (for the boat/substrate lag)", "K/min", 20.0, 0.0, 100, 0.0, False, group="operation",
      source="arXiv:1811.06119 Methods (opened): 'raise the temperature to 750-850 C at the rate of 20C/min'; a user setting, not a model constant"),
]
FNAMES = [d.name for d in FDEFS]
# wall_profile_table is deliberately NOT a ParamDef: the dashboard builds a number_input for every non-choice ParamDef and a string default breaks it (app/ is not ours).
# It is an optional extra key of the values dict, "x_cm:T_C;x_cm:T_C;..." (or a list of [x_cm, T_C] pairs), read by element_T and furnace.profile; x from the inlet.
TABLE_KEY = "wall_profile_table"
# Monte Carlo draws for profile(): FDEFS sigmas (they are copied with sigma 0 into the tube DEFS so the legacy MC streams stay bit-for-bit) + these tube inputs
BELT_EDGE_M = 0.01  # synthetic smoothing scale of the sulfur heat-belt edge [m]
TUBE_SIGMA = ("T_furnace_C", "flow_sccm", "Nu", "D_scale", "T_ends_C")


def tube_copies():
    """FDEFS with sigma = 0 (appended to the tube DEFS; scoped sigmas come back in profile() via FDEFS)."""
    return [replace(d, sigma=0.0) for d in FDEFS]


# ----------------------------------------------------------------------------------------------------------------- gas properties
def gas_props(p):
    """-> (k(T), mu(T), cp [J/kg/K], M [kg/mol]) for the furnace model; T arrays or scalars [K]."""
    car, mode = p["carrier"], p.get("gas_props", "auto")
    M, cp0 = props.mass(car) * 1e-3, props.cp_mass(car)
    if mode == "auto":
        mode = "nist_ar" if car == "Ar" else "kinetic"
    if mode == "nist_ar":
        if car != "Ar":
            raise ValueError("gas_props = nist_ar is for argon only")
        T, cp, mu, k = NIST_AR[:, 0], NIST_AR[:, 1] * 1e3, NIST_AR[:, 2] * 1e-6, NIST_AR[:, 3]
        # outside 300-1400 K: kinetic-theory shape scaled to the table end (flagged in notes)
        def ext(f, tab, g):
            return lambda t: np.where((np.asarray(t) >= T[0]) & (np.asarray(t) <= T[-1]), np.interp(t, T, tab),
                                      np.vectorize(lambda x: g(car, float(np.clip(x, 100, 3000))) * tab[0 if x < T[0] else -1] / g(car, T[0] if x < T[0] else T[-1]))(t))
        return ext(None, k, props.conductivity), ext(None, mu, props.viscosity), float(cp.mean()), M
    if mode == "cfd_const":
        Tf = p["T_furnace_C"] + 273.15
        mu = props.viscosity(car, Tf)
        k = mu * cp0 / props.prandtl(car, Tf)
        return (lambda t: np.full_like(np.asarray(t, float), k)), (lambda t: np.full_like(np.asarray(t, float), mu)), cp0, M
    return (lambda t: np.vectorize(lambda x: props.conductivity(car, float(x)))(np.asarray(t, float))), \
           (lambda t: np.vectorize(lambda x: props.viscosity(car, float(x)))(np.asarray(t, float))), cp0, M


def mdot_kg_s(p):
    """Mass flow of the sccm setting (standard T 273.15 K, 101325 Pa as in the legacy model)."""
    return 101325.0 * p["flow_sccm"] * 1e-6 / 60 / (R * 273.15) * props.mass(p["carrier"]) * 1e-3


def expansion_factor(T):
    """Actual/standard volumetric flow at T (ideal gas, same pressure as the standard condition when P = 101325 Pa): T/273.15."""
    return np.asarray(T, float) / 273.15


# ----------------------------------------------------------------------------------------------------------------- N1 profile
def parse_table(s):
    if isinstance(s, (list, tuple)):
        a = np.array(s, float).reshape(-1, 2)
    else:
        a = np.array([[float(v) for v in pr.split(":")] for pr in str(s).replace("\n", ";").split(";") if pr.strip()], float)
    a = a[np.argsort(a[:, 0])]
    return a[:, 0] / 100.0, a[:, 1] + 273.15  # m, K


def _erf(z):
    from scipy.special import erf
    return erf(z)


def element_T(p, x):
    """Furnace bore / element temperature profile [K] at x [m from the inlet] (before the S heat belt)."""
    x = np.asarray(x, float)
    off = p.get("T_wall_offset_K", 0.0)
    tab = p.get(TABLE_KEY, "")
    if isinstance(tab, (list, tuple)) or str(tab).strip():
        xt, Tt = parse_table(tab)
        return np.interp(x, xt, Tt) + off
    xc, Lh = p["x_furnace_center_cm"] / 100, p["L_hot_cm"] / 100
    Te = p["T_ends_C"] + 273.15
    nz = int(p.get("furnace_zones", 1))
    Ts = [p["T_furnace_C"], p.get("T_zone2_C", p["T_furnace_C"]), p.get("T_zone3_C", p["T_furnace_C"])][:nz]
    we = p["ramp_cm"] / 100 / 1.8124  # erf(z): 10-90 % at z = +-0.9062 -> ramp = 1.8124 w
    wb = p.get("zone_blend_cm", 4.0) / 100 / 1.8124
    edges = xc - Lh / 2 + Lh * np.arange(nz + 1) / nz
    T = np.full_like(x, Te)
    for k in range(nz):
        a, b = edges[k], edges[k + 1]
        wa, wbb = (we if k == 0 else wb), (we if k == nz - 1 else wb)
        T = T + (Ts[k] + 273.15 - Te) * 0.5 * (_erf((x - a) / wa) - _erf((x - b) / wbb))
    return T + off


def twall(p, x):
    """Gas-facing wall temperature [K] used by the legacy march when thermal_model = 'furnace': element profile (no quartz load; the loaded value is in
    profile()), with the same sulfur heat belt as the legacy model (downstream of the S boat the wall is never colder than the S boat)."""
    x = np.asarray(x, float)
    prof = element_T(p, x)
    # ponytail: the legacy step at the S boat is smoothed over BELT_EDGE_M (erf, synthetic 1 cm scale): a wall-temperature step makes the gas heat flux singular
    if p.get("S_heat_belt", "on") == "off":
        return prof
    return prof + np.maximum(p["T_boat_S_C"] + 273.15 - prof, 0.0) * 0.5 * (1 + _erf((x - p["x_S_boat_cm"] / 100) / BELT_EDGE_M))


def resolve_positions(p):
    q = dict(p)
    if p.get("positions_from_centre", "off") == "on":
        c = p["L_tube_cm"] / 2
        q["x_MoO3_cm"] = float(min(max(c + p["dx_MoO3_from_centre_cm"], 0.0), p["L_tube_cm"]))
        q["x_S_boat_cm"] = float(min(max(c + p["dx_S_from_centre_cm"], 0.0), p["L_tube_cm"]))
    return q


# ----------------------------------------------------------------------------------------------------------------- N2 radiation helpers
def band_fraction(lam_um, T):
    """Blackbody fraction emitted below wavelength lam_um at T [K]: Planck integral with xi = C2/(lam T); series in exp(-n xi) for xi >= 2, power series of the
    complement for xi < 2 (standard textbook expansions; checked against numerical quadrature of Planck's law in tests/test_track_n.py)."""
    xi = np.atleast_1d(C2 / (lam_um * np.maximum(np.asarray(T, float), 1.0)))
    big = xi >= 2.0
    xb = np.where(big, xi, 3.0)
    s = 0.0
    for n in range(1, 400):
        s = s + np.exp(-n * xb) / n * (xb**3 + 3 * xb**2 / n + 6 * xb / n**2 + 6 / n**3)
        if n > 6 and np.all(np.exp(-n * xb) < 1e-14):
            break
    hi = 15 / math.pi**4 * s
    xs = np.where(big, 1.0, xi)
    lo = 1 - 15 / math.pi**4 * xs**3 * (1 / 3 - xs / 8 + xs**2 / 60 - xs**4 / 5040 + xs**6 / 272160 - xs**8 / 13305600)
    out = np.where(big, hi, lo)
    return out if np.ndim(T) or np.ndim(lam_um) else float(out[0])


def quartz_geometry(p):
    di = IN * p["tube_id_in"]
    do = di + 2 * p["quartz_wall_mm"] * 1e-3
    return di, do


def r_prime(p, Tel, Tq):
    """Radial thermal resistance per unit length element -> inner quartz surface [K m/W] and its pieces."""
    di, do = quartz_geometry(p)
    ee = 1.0 / (1.0 / p["element_emis"] + 1.0 / p["quartz_emis_LW"] - 1.0)  # parallel plates (bore ~ close to the tube)
    Tm = 0.5 * (Tel + Tq)
    h_rad = ee * SB * 4 * Tm**3  # linearised
    h_o = h_rad + p["gap_conduction_W_m2K"]
    R_out = 1.0 / (h_o * math.pi * do)
    R_wall = math.log(do / di) / (2 * math.pi * p["quartz_k_W_mK"])
    return R_out + R_wall, R_out, R_wall


# ----------------------------------------------------------------------------------------------------------------- N3 gas heating
def graetz_1d(p, x, Tq):
    """Bulk gas temperature by a march with the Hausen mean Nusselt number turned into a local one: Nu_m(x') = Nu + 0.0668 Gz/(1 + 0.04 Gz^(2/3)),
    Gz = (d/x') Re Pr, x' from the start of heating; local Nu = d(x' Nu_m)/dx'. Hausen, Z. Ver. dtsch. Ing. Beih. Verfahrenstech. 4, 91 (1943), as printed in
    https://ht.readthedocs.io/en/latest/_modules/ht/conv_internal.html (laminar_entry_thermal_Hausen; 'Nu = 3.66' constant-T fully developed). Validity: laminar,
    uniform wall temperature (here applied locally to a non-uniform wall: approximation), Gz of order 1-1000, no axial conduction (Pe >~ 100). x in m."""
    kf, muf, cp, M = gas_props(p)
    d, md = quartz_geometry(p)[0], mdot_kg_s(p)
    Tin = p["T_ends_C"] + 273.15
    Nuinf = p["Nu"]
    hot = np.where(Tq - Tin > 5.0)[0]
    x0 = x[hot[0]] if len(hot) else x[-1]
    Tm = np.empty_like(x)
    prev = Tin
    xm_prev = x[0]
    for i in range(len(x)):
        dxi = x[i] - xm_prev if i else 0.0
        if i == 0:
            Tm[0] = Tin
            xm_prev = x[0]
            continue
        k = float(kf(0.5 * (prev + Tq[i])))
        RePr = 4 * md * cp / (math.pi * d * k)
        xs = max(0.5 * (x[i] + xm_prev) - x0, 1e-3 * d)  # distance from the heating start (centre of the step)
        h = 1e-3 * d
        nm = lambda xp: Nuinf + 0.0668 * (d / xp * RePr) / (1 + 0.04 * (d / xp * RePr) ** (2 / 3))
        Nu_loc = (( (xs + h) * nm(xs + h) - max(xs - h, 1e-6) * nm(max(xs - h, 1e-6))) / (xs + h - max(xs - h, 1e-6))) if x[i] > x0 else Nuinf
        ntu = Nu_loc * math.pi * k * dxi / (md * cp)
        Tw_i = 0.5 * (Tq[i] + Tq[i - 1])
        prev = Tw_i + (prev - Tw_i) * math.exp(-ntu)
        Tm[i] = prev
        xm_prev = x[i]
    return Tm, Tm.copy(), x0


def energy_2d(p, Tq_fun, L, nx=400, nr=28, picard=4, Tinit=None):
    """Steady axisymmetric energy equation, finite volumes, prescribed Poiseuille mass flux G(r) = 2 m''(1 - r^2/R^2), axial + radial conduction with
    k(T) (Picard), hybrid (Patankar) axial scheme, inlet Dirichlet at T_ends, outlet zero gradient, wall Dirichlet Tq(x). Returns dict of arrays on the nx cell
    centres: x, Tc (axis cell), Tm (mixing cup), Ta (area mean), q_w (W/m heat to gas), plus energy-balance residual."""
    kf, muf, cp, M = gas_props(p)
    Rr = quartz_geometry(p)[0] / 2
    md = mdot_kg_s(p)
    Tin = p["T_ends_C"] + 273.15
    xf = np.linspace(0, L, nx + 1)
    xc = 0.5 * (xf[1:] + xf[:-1])
    dx = L / nx
    s = np.linspace(0, 1, nr + 1)
    rf = Rr * (1 - (1 - s) ** 1.5)
    rc = 0.5 * (rf[1:] + rf[:-1])
    A = math.pi * (rf[1:] ** 2 - rf[:-1] ** 2)
    G = (1 - (rc / Rr) ** 2)
    F = G * A
    F = F / F.sum() * md * cp  # W/K per ring (sums to m_dot cp exactly)
    Tw = np.asarray(Tq_fun(xc), float)
    T = np.tile(Tw[:, None], (1, nr)) if Tinit is None else Tinit.copy()
    N = nx * nr
    idx = np.arange(N).reshape(nx, nr)
    for it in range(picard):
        k = kf(T)  # (nx, nr)
        kN = 0.5 * (k[:, 1:] + k[:, :-1])  # radial faces j|j+1
        DrN = kN * 2 * math.pi * rf[1:-1][None, :] * dx / (rc[1:] - rc[:-1])[None, :]  # (nx, nr-1)
        Dw = k[:, -1] * 2 * math.pi * Rr * dx / (Rr - rc[-1])  # wall
        kE = 0.5 * (k[1:, :] + k[:-1, :])  # axial faces i|i+1
        DxE = kE * A[None, :] / dx  # (nx-1, nr)
        Dxin = k[0, :] * A / (dx / 2)  # inlet half cell
        hyb = lambda D: D * np.maximum(0.0, 1 - 0.5 * F[None, :] / D)
        aE = np.zeros((nx, nr)); aW = np.zeros((nx, nr))
        aE[:-1, :] = hyb(DxE)
        aW[1:, :] = hyb(DxE) + F[None, :]
        aW[0, :] = hyb(Dxin[None, :])[0] + F
        aN = np.zeros((nx, nr)); aS = np.zeros((nx, nr))
        aN[:, :-1] = DrN
        aS[:, 1:] = DrN
        b = np.zeros((nx, nr))
        b[0, :] += aW[0, :] * Tin
        b[:, -1] += Dw * Tw
        aP = aE + aW + aN + aS
        aP[:, -1] += Dw
        rows, cols, vals = [idx.ravel()], [idx.ravel()], [aP.ravel()]
        rows += [idx[:-1, :].ravel()]; cols += [idx[1:, :].ravel()]; vals += [-aE[:-1, :].ravel()]
        rows += [idx[1:, :].ravel()]; cols += [idx[:-1, :].ravel()]; vals += [-aW[1:, :].ravel()]
        rows += [idx[:, :-1].ravel()]; cols += [idx[:, 1:].ravel()]; vals += [-aN[:, :-1].ravel()]
        rows += [idx[:, 1:].ravel()]; cols += [idx[:, :-1].ravel()]; vals += [-aS[:, 1:].ravel()]
        Mx = sparse.csc_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(N, N))
        Tn = spsolve(Mx, b.ravel()).reshape(nx, nr)
        dT = float(np.max(np.abs(Tn - T)))
        T = Tn
        if dT < 0.02 and it > 0:
            break
    qw = (Dw * (Tw - T[:, -1])) / dx  # W/m into the gas
    Tm = (T * F[None, :]).sum(1) / F.sum()
    Ta = (T * A[None, :]).sum(1) / A.sum()
    Qw = float((Dw * (Tw - T[:, -1])).sum())
    Fin = float((F * Tin).sum() + (hyb(Dxin[None, :])[0] * (Tin - T[0, :])).sum())  # inlet enthalpy flux incl. diffusion at the inlet face
    dH = float((F * T[-1, :]).sum()) - Fin
    mj = F / cp  # kg/s per ring
    rho = p["pressure_Pa"] * M / (R * T)
    ubar = (mj[None, :] / rho).sum(1) / A.sum()  # area-mean axial velocity of the prescribed mass-flux profile at the local density
    uc = mj[0] / (rho[:, 0] * A[0])
    return {"x": xc, "Tc": T[:, 0], "Tm": Tm, "Ta": Ta, "q_w": qw, "Tw": Tw, "T": T, "rc": rc, "res": abs(Qw - dH) / max(abs(dH), 1e-12), "Qw": Qw, "dH": dH,
            "u_mean": ubar, "u_centre": uc}


# ----------------------------------------------------------------------------------------------------------------- N4 bodies
def body_balance(p, kind, Tel, Tq, Tg, h_gas_k=None):
    """Steady temperature of a boat or substrate body [K] (arrays) and its linearised conductance UA [W/K].
    0 = h A (Tg - T) + hc A_c (Tq - T) + A_r [ e_n tau sigma (f(Tel) Tel^4 - f(T) T^4) + e_l sigma ((1-f(Tq)) Tq^4 - (1-f(T)) T^4) ], f = Planck band fraction below the cutoff."""
    kf = gas_props(p)[0]
    if kind == "boat":
        area, eps, enir, hc = p["boat_area_MoO3_cm2"] * 1e-4, p["boat_emis"], p["boat_nir_abs"], p["boat_contact_W_m2K"]
        Ar = area * p["boat_area_factor"]
    else:
        area = max(p["substrate_length_cm"] * max(p["substrate_width_cm"], 0.1), 1e-2) * 1e-4
        eps, enir, hc = p["sub_emis"], p["sub_nir_abs"], p["sub_contact_W_m2K"]
        Ar = 2 * area  # both faces
    Lb = math.sqrt(area)
    lam, tau = p["quartz_cutoff_um"], p["quartz_nir_transmit"]
    Tel, Tq, Tg = np.broadcast_arrays(np.asarray(Tel, float), np.asarray(Tq, float), np.asarray(Tg, float))
    hg = p["body_Nu"] * kf(Tg) / Lb
    fel, fq = band_fraction(lam, Tel), band_fraction(lam, Tq)

    def f(T):
        fb = band_fraction(lam, T)
        return (hg * Ar * (Tg - T) + hc * area * (Tq - T)
                + Ar * (enir * tau * SB * (fel * Tel**4 - fb * T**4) + eps * SB * ((1 - fq) * Tq**4 - (1 - fb) * T**4)))
    lo, hi = np.minimum(np.minimum(Tel, Tq), Tg) - 100.0, np.maximum(np.maximum(Tel, Tq), Tg) + 100.0
    for _ in range(60):  # f decreasing in T -> bisection (vectorised)
        mid = 0.5 * (lo + hi)
        pos = f(mid) > 0
        lo, hi = np.where(pos, mid, lo), np.where(pos, hi, mid)
    T = 0.5 * (lo + hi)
    UA = -(f(T + 0.5) - f(T - 0.5))
    return T, UA


# ----------------------------------------------------------------------------------------------------------------- apply (legacy march hook)
def apply(p):
    """Copy of the tube values with centre-relative positions resolved and, if boat_temperature = 'computed', T_boat_Mo_C and T_substrate_offset_K set from the
    body balance (1D Hausen gas model for the local gas T, unloaded quartz = element profile). Called by cvd_tube.march/tier0 when thermal_model = 'furnace'."""
    q = resolve_positions(p)
    if q.get("boat_temperature", "computed") == "input":
        return q
    L = q["L_tube_cm"] / 100
    x = np.linspace(0, L, 301)
    Tq = twall(q, x)
    Tm, _, _ = graetz_1d(q, x, Tq)
    xb = q["x_MoO3_cm"] / 100
    xs = (q["x_MoO3_cm"] + q["x_substrate_cm"] + q["substrate_length_cm"] / 2) / 100
    I = lambda a, xx: float(np.interp(xx, x, a))
    Tel = element_T(q, x)
    Tb, _ = body_balance(q, "boat", I(Tel, xb), I(Tq, xb), I(Tm, xb))
    Ts, _ = body_balance(q, "sub", I(Tel, xs), I(Tq, xs), I(Tm, xs))
    q["T_boat_Mo_C"] = float(np.clip(Tb - 273.15, 200, 1100))
    q["T_substrate_offset_K"] = float(np.clip(Ts - I(Tq, xs), -100, 100))
    return q


def numbers(p, Tq, Tm, u):
    """Re = 4 m_dot/(pi d mu(T_mean)), Pr, Pe_thermal = Re Pr, Gr = g (dT/T_film) d^3/nu_film^2 with dT = |T_quartz - T_mean|, Ri = Gr/Re^2, Ra = Gr Pr (arrays)."""
    kf, muf, cp, M = gas_props(p)
    d, md, Pt = quartz_geometry(p)[0], mdot_kg_s(p), p["pressure_Pa"]
    mu = _vec(muf, Tm)
    Pr = mu * cp / _vec(kf, Tm)
    Re = 4 * md / (math.pi * d * mu)
    Tf = 0.5 * (np.asarray(Tq, float) + np.asarray(Tm, float))
    nu = _vec(muf, Tf) / (Pt * M / (R * Tf))
    Gr = 9.81 * np.abs(np.asarray(Tq, float) - np.asarray(Tm, float)) * d**3 / (Tf * nu**2)
    return {"Re": Re, "Pr": Pr, "Pe_thermal": Re * Pr, "Gr": Gr, "Ri": Gr / Re**2, "Ra": Gr * Pr}


# ----------------------------------------------------------------------------------------------------------------- profile
def _vec(f, T):
    return np.vectorize(lambda t: float(f(float(t))))(np.asarray(T, float))


def _single(p, n, nx, nr, picard, quartz_iter):
    """One deterministic evaluation on n output points; returns dict of arrays and station info."""
    import vessels.cvd_tube as tube
    from vessels.cvd_tube import thermo
    q = resolve_positions(p)
    L = q["L_tube_cm"] / 100
    d = quartz_geometry(q)[0]
    kf, muf, cp, M = gas_props(q)
    md = mdot_kg_s(q)
    Pt = q["pressure_Pa"]
    car = q["carrier"]
    Tin = q["T_ends_C"] + 273.15
    xg = np.linspace(0, L, n)
    Tel_f = lambda x: element_T(q, x)
    belt = lambda x: twall(q, x)  # element profile with the S heat belt
    coupled = q.get("quartz_coupling", "on") == "on"
    Tq_arr, xi_prev, res = None, None, None
    for it in range(quartz_iter if coupled else 1):
        Tq_f = belt if Tq_arr is None else (lambda x, a=Tq_arr, xp=xi_prev: np.interp(x, xp, a))
        if q["gas_model"] == "energy_2d":
            res = energy_2d(q, Tq_f, L, nx, nr, picard)
        else:
            x1 = np.linspace(0, L, nx)
            Tqx = Tq_f(x1)
            Tm1, Tc1, x0_ = graetz_1d(q, x1, Tqx)
            u1 = md / (q["pressure_Pa"] * M / (R * Tm1) * math.pi * d**2 / 4)
            res = {"x": x1, "Tc": Tc1, "Tm": Tm1, "Ta": Tm1, "q_w": np.gradient(Tm1, x1) * md * cp, "Tw": Tqx, "res": 0.0, "u_mean": u1, "u_centre": 2 * u1}
        xi_prev = res["x"]
        if coupled:  # loaded inner wall: element profile minus (heat into the gas per length) x (radial resistance per length)
            Rp = r_prime(q, belt(xi_prev), belt(xi_prev))[0]
            Tq_arr = belt(xi_prev) - res["q_w"] * Rp
    xi = res["x"]
    Tqv = np.interp(xg, xi, Tq_arr) if (coupled and Tq_arr is not None) else belt(xg)
    Tc, Tm = np.interp(xg, xi, res["Tc"]), np.interp(xg, xi, res["Tm"])
    Tel = Tel_f(xg)
    Tel_belt = belt(xg)
    # quartz fin length vs ramp
    Rp0 = r_prime(q, np.max(Tel), np.max(Tel))[0]
    di, do = quartz_geometry(q)
    Aq = math.pi / 4 * (do**2 - di**2)
    fin = math.sqrt(q["quartz_k_W_mK"] * Aq * Rp0)
    # bodies
    Tb, UAb = body_balance(q, "boat", Tel_belt, Tqv, Tm)
    Ts, UAs = body_balance(q, "sub", Tel_belt, Tqv, Tm)
    # transport numbers
    u = np.interp(xg, xi, res["u_mean"])
    uc = np.interp(xg, xi, res["u_centre"])
    num = numbers(q, Tqv, Tm, u)
    Re, Pr, Pet, Gr, Ri, Ra = num["Re"], num["Pr"], num["Pe_thermal"], num["Gr"], num["Ri"], num["Ra"]
    Dm = np.array([float(thermo.fuller_D(car, "MoO3", float(t), Pt, int(q["MoO3.n_oligomer"]))) for t in Tm]) * q["D_scale"]
    Pem = u * d / Dm
    tau = np.concatenate([[0.0], np.cumsum(0.5 * (1 / u[1:] + 1 / u[:-1]) * np.diff(xg))])
    hot = np.where(Tqv - Tin > 5.0)[0]
    x0 = xg[hot[0]] if len(hot) else xg[-1]
    out = dict(x=xg, T_wall=Tel_belt, T_quartz=Tqv, T_gas_centre=Tc, T_gas_mean=Tm, T_boat=Tb, T_substrate=Ts, u=u, u_centre=uc, Re=Re, Pe_thermal=Pet, Pe_mass=Pem,
               Gr=Gr, Ri=Ri, Ra=Ra, tau_cum=tau, UA_boat=UAb, UA_sub=UAs, Pr=Pr, Dm=Dm, res=res["res"], fin=fin, x0=x0)
    ric = q["Ri_c"]
    xth = np.maximum(xg - x0, 0) / np.maximum(0.05 * Re * Pr * d, 1e-12)
    out["flags"] = {"laminar": (Re < 2300).astype(int), "buoyancy_matters": (Ri > ric).astype(int), "axial_conduction_matters": (Pet < 10).astype(int),
                    "thermally_developed": (xth >= 1).astype(int)}
    return out, q


KEYS = ["T_wall", "T_quartz", "T_gas_centre", "T_gas_mean", "T_boat", "T_substrate", "u", "Re", "Ri"]


def profile(values, n=200, n_mc=30, seed=0, nx=None, nr=28):
    """See the module docstring for the returned schema. values: tube values (any subset; defaults filled in). n_mc = 0 switches the Monte Carlo off."""
    from core import params as Pm, uq
    from vessels.cvd_tube import wulff
    values = dict(values)
    tab = values.pop(TABLE_KEY, "")
    v = Pm.validate(wulff.DEFS, values)
    if isinstance(tab, (list, tuple)) or str(tab).strip():
        v[TABLE_KEY] = tab
    v["thermal_model"] = "furnace"
    nx = nx or int(np.clip(math.ceil(v["L_tube_cm"] / 0.25), 200, 800))
    main, q = _single(v, n, nx, nr, 4, 3)
    bands = {k: {"p05": [], "p95": []} for k in KEYS}
    st_bands = {}
    if n_mc:
        rng = np.random.default_rng(seed)
        defs = [d for d in FDEFS if d.sigma] + [d for d in wulff.DEFS if d.name in TUBE_SIGMA and d.sigma]
        draws = {k: [] for k in KEYS}
        sb = {s: {"Tb": [], "Tc": [], "Tm": []} for s in ("boat_MoO3", "substrate")}
        xs = {"boat_MoO3": q["x_MoO3_cm"] / 100, "substrate": (q["x_MoO3_cm"] + q["x_substrate_cm"] + q["substrate_length_cm"] / 2) / 100}
        for _ in range(n_mc):
            try:
                w = uq.sample(defs, v, rng)
                o, _q = _single(w, n, max(nx // 2, 160), 16, 2, 2)
            except (ValueError, FloatingPointError):
                continue
            for k, key in zip(KEYS, ["T_wall", "T_quartz", "T_gas_centre", "T_gas_mean", "T_boat", "T_substrate", "u", "Re", "Ri"]):
                draws[k].append(o[key])
            for s in sb:
                sb[s]["Tb"].append(float(np.interp(xs[s], o["x"], o["T_boat" if s == "boat_MoO3" else "T_substrate"])))
        if draws["T_wall"]:
            for k in KEYS:
                a = np.array(draws[k])
                bands[k] = {"p05": np.percentile(a, 5, axis=0).tolist(), "p95": np.percentile(a, 95, axis=0).tolist()}
            st_bands = {s: (float(np.percentile(sb[s]["Tb"], 5)), float(np.percentile(sb[s]["Tb"], 95))) for s in sb}
    x = main["x"]
    xb, xsb = q["x_MoO3_cm"] / 100, (q["x_MoO3_cm"] + q["x_substrate_cm"] + q["substrate_length_cm"] / 2) / 100
    xS = q["x_S_boat_cm"] / 100
    I = lambda a, xx: float(np.interp(xx, x, a))

    def station(name, xx, body):
        s = {"x_cm": xx * 100}
        for k, key in (("T_wall_K", "T_wall"), ("T_quartz_K", "T_quartz"), ("T_gas_centre_K", "T_gas_centre"), ("T_gas_mean_K", "T_gas_mean"), ("u_mean_m_s", "u"),
                       ("Re", "Re"), ("Pe_thermal", "Pe_thermal"), ("Pe_mass", "Pe_mass"), ("Gr", "Gr"), ("Ri", "Ri"), ("Ra", "Ra")):
            s[k] = I(main[key], xx)
        s["flags"] = {k: int(round(I(main["flags"][k].astype(float), xx))) for k in main["flags"]}
        s["T_body_K"] = I(main[body], xx) if body else float("nan")
        if body in ("T_boat", "T_substrate"):
            UA = I(main["UA_boat" if body == "T_boat" else "UA_sub"], xx)
            m_cp = (q["boat_mass_g"] * q["boat_cp_J_kgK"] if body == "T_boat" else q["sub_mass_g"] * q["sub_cp_J_kgK"]) * 1e-3
            s["tau_body_s"] = float(m_cp / max(UA, 1e-12))
            s["body_lag_K"] = float(s["tau_body_s"] * q["furnace_ramp_K_min"] / 60.0)
        return s
    stations = {"boat_MoO3": station("boat_MoO3", xb, "T_boat"), "boat_S": station("boat_S", xS, None), "substrate": station("substrate", xsb, "T_substrate")}
    if q["boat_temperature"] == "input":
        stations["boat_MoO3"]["T_body_K"] = q["T_boat_Mo_C"] + 273.15
        stations["substrate"]["T_body_K"] = I(main["T_quartz"], xsb) + q["T_substrate_offset_K"]
    stations["boat_S"]["T_body_K"] = q["T_boat_S_C"] + 273.15
    stations["boat_S"]["note"] = "sulfur boat temperature is the input T_boat_S_C (separate heater, as in the legacy model)"
    for s, (a, b) in st_bands.items():
        stations[s]["T_body_p05_K"], stations[s]["T_body_p95_K"] = a, b
    # boat -> substrate transport
    mb = (x >= xb) & (x <= xsb)
    xx = np.linspace(xb, xsb, 200) if xsb > xb else np.array([xb, xb + 1e-3])
    uu = np.interp(xx, x, main["u"])
    t_plug = float(np.trapezoid(1 / uu, xx))
    t_centre = t_plug / 2.0  # Poiseuille centreline = 2 x mean (constant-property bound)
    Dloc = np.interp(xx, x, main["Dm"])
    aR = quartz_geometry(q)[0] / 2
    Pea = uu * aR / Dloc
    Deff = Dloc * (1 + Pea**2 / 48)  # Taylor-Aris, https://en.wikipedia.org/wiki/Taylor_dispersion (Pe = a u / D, valid L >> a Pe, t >> a^2/D)
    Lbs = max(xsb - xb, 1e-3)
    t_diff = float(Lbs**2 / (2 * np.mean(Dloc)))
    t_disp = float(Lbs**2 / (2 * np.mean(Deff)))
    Pe_tr = float(np.mean(uu) * Lbs / np.mean(Deff))
    taylor_ok = bool(Lbs > float(np.mean(aR * Pea)) and t_plug > aR**2 / float(np.mean(Dloc)))
    Reb, Prb = stations["boat_MoO3"]["Re"], I(main["Pr"], xb)
    sc = {"L_hydrodynamic_cm": float(0.0575 * Reb * quartz_geometry(q)[0] * 100), "L_thermal_cm": float(0.05 * Reb * Prb * quartz_geometry(q)[0] * 100),
          "x_heat_start_cm": float(main["x0"] * 100), "expansion_factor_at_boat": stations["boat_MoO3"]["T_gas_mean_K"] / 273.15,
          "residence_boat_to_substrate_plug_s": t_plug, "residence_boat_to_substrate_centreline_s": t_centre, "axial_diffusion_time_s": t_diff,
          "axial_dispersion_time_s": t_disp, "Pe_transport_boat_to_substrate": Pe_tr, "taylor_aris_valid": taylor_ok,
          "carried_by": "convection" if Pe_tr > 10 else ("convection and axial dispersion (comparable)" if Pe_tr > 1 else "axial diffusion/dispersion"),
          "energy_balance_residual": float(main["res"]), "quartz_fin_length_cm": float(main["fin"] * 100),
          "T_quartz_minus_wall_max_K": float(np.max(np.abs(main["T_quartz"] - main["T_wall"]))),
          "boat_minus_quartz_at_boat_K": float(stations["boat_MoO3"]["T_body_K"] - stations["boat_MoO3"]["T_quartz_K"]),
          "buoyancy_matters_boat_to_substrate": bool(np.any(np.interp(xx, x, main["Ri"]) > q["Ri_c"])),
          "Ri_max_boat_to_substrate": float(np.max(np.interp(xx, x, main["Ri"])))}
    notes = ["T_wall is the furnace bore / element temperature (input); T_quartz the inner quartz surface after the radial network (element -> gap -> quartz wall); with quartz_coupling=off they are equal",
             "gas_model=%s: %s" % (q["gas_model"], "axisymmetric energy equation with a prescribed Poiseuille mass-flux profile (no momentum solve, no radial velocity, cp constant, T-dependent k)"
                                   if q["gas_model"] == "energy_2d" else "Hausen developing-flow Nusselt march, no radial profile (centre = mean), no axial conduction (valid Pe >~ 100; here Pe_thermal is %.1f at the boat)" % stations["boat_MoO3"]["Pe_thermal"]),
             "gas properties: %s" % ("NIST argon table 300-1400 K (kinetic-theory shape scaled outside)" if (q["gas_props"] in ("auto", "nist_ar") and q["carrier"] == "Ar") else q["gas_props"] if q["gas_props"] != "auto" else "kinetic theory (core.props)"),
             "quartz treated as two bands (transparent below %.1f um, fraction %.2f; opaque above); quartz emissivity and all boat/substrate properties are synthetic" % (q["quartz_cutoff_um"], q["quartz_nir_transmit"]),
             "axial conduction along the quartz is not solved: fin length %.2f cm vs ramp %.1f cm (%s)" % (sc["quartz_fin_length_cm"], q["ramp_cm"], "negligible" if sc["quartz_fin_length_cm"] < 0.2 * q["ramp_cm"] else "NOT negligible"),
             "no gas radiation, no evaporation heat sink at the boat, no axial radiation (light pipe) in the quartz, no natural-convection correction to Nu (Ri only flagged; Ri_c = %.2f is a convention)" % q["Ri_c"],
             "T_boat/T_substrate arrays are the steady temperature a body of that type WOULD have at x; the stations give the values at the configured boat and substrate",
             "legacy-vs-furnace: the legacy march uses a tanh profile with ramp/3 scale, the furnace profile uses erf with ramp = 10-90 % distance"]
    if q["gas_props"] in ("auto", "nist_ar") and q["carrier"] == "Ar" and (np.min(main["T_gas_mean"]) < 300 or np.max(main["T_gas_mean"]) > 1400):
        notes.append("gas temperature leaves the NIST table range 300-1400 K somewhere along the tube; properties extrapolated")
    if np.any(main["Re"] > 2300):
        notes.append("Re > 2300 somewhere: laminar assumption violated")
    units = {"x_cm": "cm", "T_wall_K": "K", "T_quartz_K": "K", "T_gas_centre_K": "K", "T_gas_mean_K": "K", "T_boat_K": "K", "T_substrate_K": "K", "u_mean_m_s": "m/s", "u_centre_m_s": "m/s",
             "Re": "", "Pe_thermal": "", "Pe_mass": "", "Gr": "", "Ri": "", "Ra": "", "tau_cum_s": "s"}
    cons = {d.name: {"value": q[d.name], "unit": d.unit, "sigma": d.sigma, "source": d.source if d.source != "default" else SYN} for d in FDEFS if d.name in q}
    mcb = {}
    for k, key in zip(KEYS, ["T_wall_K", "T_quartz_K", "T_gas_centre_K", "T_gas_mean_K", "T_boat_K", "T_substrate_K", "u_mean_m_s", "Re", "Ri"]):
        mcb[key] = bands[k]
    return {"schema": "cvd_tube.furnace.profile/1", "thermal_model": "furnace", "gas_model": q["gas_model"], "n": n, "x_cm": (x * 100).tolist(),
            "T_wall_K": main["T_wall"].tolist(), "T_quartz_K": main["T_quartz"].tolist(), "T_gas_centre_K": main["T_gas_centre"].tolist(),
            "T_gas_mean_K": main["T_gas_mean"].tolist(), "T_boat_K": main["T_boat"].tolist(), "T_substrate_K": main["T_substrate"].tolist(),
            "u_mean_m_s": main["u"].tolist(), "u_centre_m_s": main["u_centre"].tolist(), "Re": main["Re"].tolist(), "Pe_thermal": main["Pe_thermal"].tolist(), "Pe_mass": main["Pe_mass"].tolist(),
            "Gr": main["Gr"].tolist(), "Ri": main["Ri"].tolist(), "Ra": main["Ra"].tolist(), "tau_cum_s": main["tau_cum"].tolist(),
            "flags": {k: a.tolist() for k, a in main["flags"].items()},
            "p05": {k: (b["p05"] if b["p05"] else []) for k, b in mcb.items()}, "p95": {k: (b["p95"] if b["p95"] else []) for k, b in mcb.items()},
            "stations": stations, "scalars": sc, "units": units, "notes": notes, "constants": cons}
