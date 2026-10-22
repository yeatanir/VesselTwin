"""Tier 0: dimensionless numbers and regime calls. Pure functions, SI units."""
from enum import Enum

G = 9.81


class Regime(str, Enum):
    reaction_limited = "reaction_limited"
    transport_limited = "transport_limited"  # mixing/diffusion/mass transfer
    heat_limited = "heat_limited"
    convection_assisted = "convection_assisted"  # buoyancy matters on top of diffusion


def reynolds(rho, u, L, mu): return rho * u * L / mu
def peclet(u, L, D): return u * L / D
def damkohler(t_transport, t_reaction): return t_transport / t_reaction
def rayleigh(beta, dT, L, nu, alpha): return G * beta * dT * L**3 / (nu * alpha)
def grashof(beta, dT, L, nu): return G * beta * dT * L**3 / nu**2
def biot(h, L, k): return h * L / k


def classify(Da: float, margin: float = 3.0) -> tuple[Regime, float]:
    """Da>>1: transport is the bottleneck; Da<<1: reaction is. Returns (regime, margin factor).
    Inside [1/margin, margin] the call is ambiguous: report the nearer side, factor<1 flags it."""
    r = Regime.transport_limited if Da >= 1 else Regime.reaction_limited
    f = max(Da, 1 / Da)
    return r, f / margin  # >=1 means outside the ambiguity band
