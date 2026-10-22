"""Scipy-only IAST for dual-site Langmuir pure isotherms (no pyIAST needed). Independent of pyIAST: used to check its output
(pyIAST printed 'invalid value in log' warnings for the 13X CO2/H2O case) and by tests. Units: P in bar, q in mol/kg, K in 1/bar."""
import numpy as np
from scipy.optimize import brentq


def _pi(M, lp): return sum(m * np.logaddexp(0.0, np.log(k) + lp) for m, k in M)  # spreading pressure / RT, ln P0 = lp
def _q(M, lp): return sum(m / (1 + np.exp(-np.log(k) - lp)) for m, k in M)


def iast(M, P):
    """M: {species: [(qmax, K), ...]}, P: {species: partial pressure bar} -> {species: loading mol/kg} (ideal adsorbed solution theory)."""
    lP0 = lambda s, x: brentq(lambda lp: _pi(M[s], lp) - x, -100, 2000, xtol=1e-12)
    f = lambda lx: sum(P[s] / np.exp(lP0(s, np.exp(lx))) for s in P) - 1
    x = np.exp(brentq(f, -30, 8))
    z = {s: P[s] / np.exp(lP0(s, x)) for s in P}
    qt = 1 / sum(z[s] / _q(M[s], lP0(s, x)) for s in P)
    return {s: float(qt * z[s]) for s in P}
