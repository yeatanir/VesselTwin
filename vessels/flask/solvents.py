"""Temperature-dependent solvent density, viscosity, cp for the flask solvent table. CoolProp is not installed, so these are
fits to published tables, refitted here (nothing is recalled from memory):
  viscosity  mu [Pa s] = exp(A + B/(T-C)), T in K. Vogel (C>0) when >=6 points, Andrade (C=0) for 3-point sets.
  density    rho [kg/m3] = c0 + c1 (T-298.15) + c2 (T-298.15)^2
Data sources (fit range in C in FIT):
  water      Lide, CRC Handbook 2004 p.6-201 (mu), Dean/Lange 1999 + Lide p.6-15 (rho), via Wikipedia 'Water (data page)'
  ethanol    mu: CHERIC Pure Component database; rho: Lange 10th ed linear fit (Wikipedia 'Ethanol (data page)')
  toluene    mu: CHERIC database (Wikipedia 'Toluene (data page)'); rho: 3-point set (298-318 K) from the pure-toluene rows of
             J Chem Eng Data 2009, doi 10.1021/je900194v (NIST TRC ThermoML)
  DMF, DMSO  'Densities and Viscosities of DMF + NMP and + DMSO, 303.15 to 353.15 K', J Chem Eng Data 2008,
             doi 10.1021/je800138b (pure-component rows, NIST TRC ThermoML)
  ACN, THF   Das & Roy, J Chem Eng Data 2006, 51, 2225, doi 10.1021/je060311a (298-318 K, 3 points each)
  ethylene glycol, glycerol  Ge, Ma, Chu, J Chem Eng Data 2010, 55, 2649, doi 10.1021/je900938b (298-338 K). The glycerol viscosity
             points scatter by ~10 % about the fit; the glycerol fit is the least accurate entry.
  cp (J/g/K, 25 C) from Wikipedia data pages (molar cp / M; the page rows carry no citation; THF: Lebedev 1978 J Chem Thermodyn 10, 321).
Outside the fit range the correlation extrapolates and props() reports in_range=False.
ponytail: pure solvents only (no mixtures, no pressure); T-dependence of the 25 C table in flask.SOLVENTS is the fit evaluated at 25 C."""
import math

# name: (A, B, C, (c0, c1, c2), (T_lo_C, T_hi_C), cp J/g/K)
FIT = {
    "water": (-10.4408, 512.05, 148.56, (996.624, -0.247565, -0.00359488), (0, 100), 4.1787),
    "ethanol": (-13.5008, 2332.28, -53.67, (785.188, -0.846882, 0.0), (-50, 75), 2.44),
    "toluene": (-11.083, 1016.82, 13.96, (862.187, -0.939, 0.0), (-25, 50), 1.693),
    "DMF": (-10.6861, 1043.73, 5.17, (945.235, -0.972657, 0.0), (30, 80), 1.998),
    "DMSO": (-10.3908, 905.68, 80.31, (1095.64, -1.00866, 0.0), (30, 80), 1.958),
    "acetonitrile": (-10.7638, 831.11, 0.0, (776.683, -1.105, 0.0), (25, 45), 2.234),
    "THF": (-10.3925, 810.28, 0.0, (881.033, -1.0, 0.0), (25, 45), 1.718),
    "ethylene_glycol": (-9.278, 610.6, 181.16, (1110.56, -0.706333, 0.0), (25, 65), 2.41),
    "glycerol": (-11.2346, 1392.25, 173.78, (1258.18, -0.629, 0.0), (25, 65), 2.41),
}


def props(solvent: str, T_C: float, mu_factor: float = 1.0) -> dict:
    """rho [kg/m3], mu [Pa s], cp [J/kg/K], in_range flag. mu_factor scales viscosity (emulates sucrose/glycerol-water or dilution)."""
    A, B, C, (c0, c1, c2), (lo, hi), cp = FIT[solvent]
    T = T_C + 273.15
    dT = T - 298.15
    return {"rho": c0 + c1 * dT + c2 * dT * dT, "mu": math.exp(A + B / (T - C)) * mu_factor, "cp": cp * 1e3,
            "in_range": float(lo <= T_C <= hi)}
