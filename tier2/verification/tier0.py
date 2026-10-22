"""Track B Tier 0 replacements (scored in b3_score.py; wiring into the vessels is requested in docs/handoff/requests-b.md, core/ and
vessels/cvd_tube are not mine).
tube: Da_eff = (k_m pi d / Q_f) * int_{boat}^{substrate centre} s(x) dx, k_m = Sh D / d_h, s = max(0, 1 - psat(T_wall(x))/psat(T_boat)):
      the wall only takes MoO3 up where it is colder than the boat (wall = saturation sink in the CFD and in Tier 1). Da_eff >= 1 <-> NTU >= 1 <-> 63 % taken up.
ampoule: f_variant reproduces vessels.ampoule._convection('calibrated') with a selectable stratification closure."""
import numpy as np
from core import props
from core.dimensionless import Regime
from vessels import ampoule as A
from vessels.cvd_tube import twall, psat_MoO3, thermo, IN, P_STD, T_STD
import vessels.cvd_tube as T

G = 9.81


def f_variant(p, strat="duct"):
    """Convection factor f of the ampoule for strat in {'none','legacy_L3','duct'}; 'duct' equals the shipped value (unit-tested), 'legacy_L3' is commit aa4e98c."""
    c = A._core(p)
    dr, D, Sc = c["drho"], c["D"], c["Sc"]
    nu = Sc * D
    L, H = p["L_cm"] / 100, p["D_mm"] / 1000
    th = np.radians(p["tilt_deg"])
    unstable = np.sin(th) * dr > 0
    ra_h = G * abs(dr) * H**3 / (nu * D)
    a = H / L
    f_h = 1 + (ra_h * a * abs(np.cos(th))) ** 2 / 362880.0
    ra_v = G * abs(dr) * L**3 / (nu * D) * abs(np.sin(th)) if unstable else 0.0
    nu_v = max(1.0, 0.069 * ra_v ** (1 / 3) * Sc**0.074) if ra_v > p["Ra_c_vertical"] else 1.0
    sat = lambda t: t / (1 + (t / p["conv_fmax"]) ** p["conv_n"]) ** (1 / p["conv_n"])
    if unstable or np.sin(th) == 0 or strat == "none":
        stab = 1.0
    elif strat == "legacy_L3":
        stab = 1 / (1 + G * abs(dr) * L**3 / (nu * D) * abs(np.sin(th)) / p["Ra_c_vertical"])
    else:
        stab = 1 / (1 + ra_h * a * abs(np.sin(th)) / p["Ra_c_vertical"])
    return float(1 + sat(p["conv_c"] * (f_h - 1)) * stab + sat(nu_v - 1))


def tube_da_eff(p, Sh=None):
    """Wall-uptake NTU between the MoO3 boat and the substrate centre counting only wall length colder than the boat (see module doc)."""
    d, car, Pt = IN * p["tube_id_in"], p["carrier"], p["pressure_Pa"]
    Tf = p["T_furnace_C"] + 273.15
    Qf = p["flow_sccm"] * 1e-6 / 60 * Tf / T_STD * P_STD / Pt
    DM = float(thermo.fuller_D(car, "MoO3", Tf, Pt, int(p["MoO3.n_oligomer"]))) * p["D_scale"]
    km = (Sh or p["Sh"]) * DM / d
    x0 = p["x_MoO3_cm"] / 100
    x1 = (p["x_MoO3_cm"] + p["x_substrate_cm"] + p["substrate_length_cm"] / 2) / 100
    x = np.linspace(x0, x1, 400)
    ps_b = float(psat_MoO3(p, p["T_boat_Mo_C"] + 273.15))
    s = np.clip(1 - psat_MoO3(p, twall(p, x)) / ps_b, 0, None)
    return float(km * np.pi * d / Qf * np.trapezoid(s, x))


def tube_tier0_new(p):
    """(regime, Da_eff). heat_limited branch identical to vessels.cvd_tube.tier0; otherwise Da_eff >= 1 -> transport_limited."""
    r0, _, nums = T.tier0(p)
    da = tube_da_eff(p)
    if r0 == Regime.heat_limited:
        return r0, da
    return (Regime.transport_limited if da >= 1 else Regime.reaction_limited), da
