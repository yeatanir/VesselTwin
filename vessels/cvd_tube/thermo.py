"""MoS2 CVD tube: vapour-pressure laws, sulfur speciation and gas diffusivities, with the literature basis of each.
Species basis (read this before comparing numbers):
 - Mo-bearing vapour over MoO3 is a mixture of (MoO3)n, n = 3, 4, 5 (Berkowitz, Inghram, Chupka, J. Chem. Phys. 26, 842 (1957), title
   'Polymeric gaseous species in the sublimation of molybdenum trioxide'; only abstracts/secondary summaries read). Pressure and flow
   are carried in MoO3-formula-unit equivalents: p_unit = sum_n n p_n, so Mo mole fraction = p_unit/P. Diffusion and Hertz-Knudsen use ONE
   oligomer (param MoO3.n_oligomer, default 3, the trimer).
 - Total vapour pressure over solid MoO3: Simnad & Spilners, Trans. AIME (1956), log10 p[mmHg] = -16140/T - 5.53 log10 T + 30.69,
   25 C to melting point (1075 K). Read from an OCR'd index page; origin of the fit (own data or compilation) NOT verified, so it carries
   a free level MoO3.P_ref_Pa (pressure at 1000 K, sigma 50 %). It gives ~1 Pa at 1000 K, 30x BELOW the old synthetic placeholder. Not used above ~1075 K.
 - Sulfur: total vapour pressure over liquid S from an Antoine fit log10 p[Torr] = 6.69535 - 2285.37/(t[C] + 155) found on a forum page;
   NOT traced to a primary source, but checked against the normal boiling point (717.8 K -> 766 Torr) and against the shape of Rau,
   Kutty & Guedes de Carvalho, J. Chem. Thermodyn. 5, 833 (1973). Boat vapour is S8 (+S6, S7: lumped as S8). In the hot zone S8 = 4 S2
   equilibrium from NIST-JANAF (Chase 1998, via NIST WebBook) Shomate fits: S2 (298-6000 K; dfH 128.60 kJ/mol), S8 (S0 430.23 J/mol/K)
   and dfH(S8, g) = 100.416 kJ/mol (experimental sublimation enthalpy of alpha-S, quoted by Jackson, Tiana & Walsh, Chem. Sci. 7, 1082
   (2016), DOI 10.1039/C5SC03088A). S3-S7 neglected (Jackson et al. note JANAF itself interpolates them).
 - Gas diffusivity: Fuller-Schettler-Giddings (Ind. Eng. Chem. 58(5), 18 (1966)), as core.props; the Mo atomic volume is NOT tabulated
   (22.9 = S used as stand-in), so D(MoO3 oligomer) is an estimate: D_scale carries the uncertainty (sigma 25 %).
 - MoO3 evaporation coefficient: no published value found -> stays synthetic.
ponytail: S3-S7 species ignored; the liquid-MoO3 branch of Simnad & Spilners is not used; Fuller volumes for oligomers = n x monomer."""
import numpy as np
from core import props

R = props.R
KP_T = 1000.0
# NIST WebBook Shomate (t = T/1000): A B C D E F G H ; H-H298 = A t + B t^2/2 + C t^3/3 + D t^4/4 - E/t + F - H [kJ/mol]
_S2 = (33.51313, 5.065360, -1.059670, 0.089905, -0.211911, 117.6855, 266.0919, 128.6003)
_S8 = (180.6697, 1.918988, -0.520130, 0.044394, -2.270155, -61.56045, 635.5496, 0.0)
V_MO3 = props.FULLER["MoO3"]  # estimate (see above)
V_S = 22.9


def _shomate(c, T):
    A, B, C, D, E, F, G, H = c
    t = np.asarray(T, float) / 1000
    return A * t + B * t**2 / 2 + C * t**3 / 3 + D * t**4 / 4 - E / t + F - H, A * np.log(t) + B * t + C * t**2 / 2 + D * t**3 / 3 - E / (2 * t**2) + G


def kp_S8_S2(T, dHf_S8_kJ=100.416):
    """K_p [bar^3] of S8(g) = 4 S2(g) from JANAF Shomate fits. T in K (array ok)."""
    (h2, s2), (h8, s8) = _shomate(_S2, T), _shomate(_S8, T)
    dG = (4 * (128.6003 + h2) - (dHf_S8_kJ + h8)) * 1e3 - np.asarray(T, float) * (4 * s2 - s8)
    return np.exp(-dG / (R * np.asarray(T, float)))


def s2_fraction(a, T, P, dHf_S8_kJ=100.416):
    """Fraction x of S ATOMS present as S2 (rest S8) when S atoms are a mole fraction `a` of the gas at T, P [Pa].
    x^4/(1-x) = 2 K / (a P_bar)^3 ; monotone, bisection (vectorised, 40 halvings)."""
    g = 2 * kp_S8_S2(T, dHf_S8_kJ) / np.maximum(a * P / 1e5, 1e-30) ** 3
    lo, hi = np.zeros_like(g), np.ones_like(g)
    for _ in range(40):
        mid = (lo + hi) / 2
        big = mid**4 > g * (1 - mid)
        hi, lo = np.where(big, mid, hi), np.where(big, lo, mid)
    return (lo + hi) / 2


T_MELT = 1068.0  # K, melting point used by the Smolik et al. 2000 solid fit's range


def _liquid_cc(p, T, f):
    """Track I liquid branch. Solid: Smolik law (x P_ref/f(1000), as before) up to T_MELT. Liquid: Clausius-Clapeyron continuation
    ln p = ln p_m + B (1/T_m - 1/T), anchored at the solid value p_m at T_MELT (continuity) and pinned so p(Tb) = 1 atm at the nominal
    B = ln(101325/p_m) / (1/T_m - 1/Tb) (MoO3.Tb_K); the MC factor MoO3.liq_Bfac multiplies B (anchor kept, pin then holds only at the nominal).
    ponytail: single effective B (constant enthalpy); MoO3 'sublimes' per CRC so Tb is a conventional pin; p is the total (MoO3)n pressure."""
    pm = float(f(T_MELT)) * p["MoO3.P_ref_Pa"] / float(f(1000.0))
    B = np.log(101325.0 / pm) / (1 / T_MELT - 1 / p["MoO3.Tb_K"]) * p["MoO3.liq_Bfac"]
    liq = pm * np.exp(B * (1 / T_MELT - 1 / np.maximum(T, T_MELT)))
    return np.where(T > T_MELT, liq, f(T) * p["MoO3.P_ref_Pa"] / float(f(1000.0)))


def psat_MoO3(p, T):
    """Total Mo-bearing vapour pressure over MoO3, MoO3-unit equivalents [Pa]."""
    if p["thermo_basis"] == "legacy_synthetic":
        return p["MoO3.P_ref_Pa"] * np.exp(-p["MoO3.dH_kJmol"] * 1e3 / R * (1 / T - 1 / 1000.0))
    m = p.get("MoO3.psat_model", "smolik_hsc")
    if m in ("smolik_hsc", "smolik_liquid_cc"):
        # Smolik et al., INEEL/EXT-2000, doi:10.2172/752007, Eq. 6 (HSC-derived total (MoO3)n pressure over SOLID MoO3, Torr, T in K);
        # ~53 Pa at 1000 K. Berkowitz, Inghram & Chupka 1957 points (as reprinted by Fletcher 1966) run ~2x higher at 883-973 K.
        # smolik_hsc: T is clamped at the melting point (1068 K), which underestimates the liquid.
        f = lambda T: 133.322 * 10 ** (lambda t: 8599.81 / t - 186.495 + 63.1654 * np.log10(t) - 0.0078447 * t - 4154834 / t**2)(np.minimum(T, T_MELT))
        if m == "smolik_liquid_cc":
            return _liquid_cc(p, np.asarray(T, float), f)
    else:  # simnad_ocr: coefficients read from an OCR'd index page; at 973 K it is ~60x BELOW Berkowitz and ~30x below the HSC fit
        f = lambda T: 133.322 * 10 ** (p["MoO3.logP_A"] / T + p["MoO3.logP_B"] * np.log10(T) + p["MoO3.logP_C"])
    return f(T) * p["MoO3.P_ref_Pa"] / f(1000.0)


def psat_S(p, T):
    """Total sulfur vapour pressure over liquid S [Pa] (legacy: old synthetic S2 Clapeyron law)."""
    if p["thermo_basis"] == "legacy_synthetic":
        return 101325.0 * np.exp(-p["S.dH_kJmol"] * 1e3 / R * (1 / T - 1 / 717.8))
    return 133.322 * 10 ** (p["S.antoine_A"] - p["S.antoine_B"] / (T - 273.15 + p["S.antoine_C"])) * p["S.P_scale"]


def fuller_D(car, sp, T, P, n=3):
    """Binary diffusivity carrier-species [m2/s]. sp in {MoO3 (n-mer), S2, S8}."""
    Ma = props.mass(car)
    Mb, Vb = {"MoO3": (n * props.M_SPECIES["MoO3"], n * V_MO3), "S2": (64.13, 2 * V_S), "S8": (256.52, 8 * V_S)}[sp]
    return 1e-7 * T**1.75 * np.sqrt(1 / Ma + 1 / Mb) / ((P / 1.01325e5) * (props.FULLER[car] ** (1 / 3) + Vb ** (1 / 3)) ** 2)


from contextlib import contextmanager  # noqa: E402


@contextmanager
def with_liq_sigma(cfg, sigma=0.384):
    """Give MoO3.liq_Bfac its assumed sigma only while psat_model='smolik_liquid_cc' (a ParamDef sigma adds one RNG draw per MC sample for
    EVERY configuration, which would shift the stored default MC streams; same reason as wulff.with_sigma). sigma = (B_Blackburn - B_pin)/1.645/B_pin:
    B_Blackburn Eq.14 = 14123 ln10 = 32519 K; B_pin = 19929 K for Tb = 1428 K (so the p95 slope is Blackburn's, the p05 slope 7370 K lies below Fieser's 18000 K)."""
    from vessels import cvd_tube as tube
    d = next(x for x in tube.DEFS if x.name == "MoO3.liq_Bfac")
    old, d.sigma = d.sigma, (sigma if cfg.get("MoO3.psat_model") == "smolik_liquid_cc" else d.sigma)
    try:
        yield
    finally:
        d.sigma = old
