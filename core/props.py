"""Gas properties from kinetic theory (never from the LLM). Chapman-Enskog viscosity, Fuller diffusion, Eucken conductivity.
Upgrade path: CoolProp/thermo once installed. Lennard-Jones: Bird, Stewart & Lightfoot. Fuller volumes: Fuller 1966.
Entries marked 'estimate' are not tabulated values."""
import math

R = 8.314462618
# name: (M g/mol, sigma A, eps/k K, cp/R)
GAS = {"Ar": (39.948, 3.542, 93.3, 2.5), "N2": (28.014, 3.798, 71.4, 3.5),
       "H2": (2.016, 2.827, 59.7, 3.5), "I2": (253.81, 5.160, 474.2, 4.5), "CO2": (44.01, 3.941, 195.2, 4.5)}
# Fuller diffusion volumes. I2 (2x I atom), S2, MoO3 (atomic sums; Mo volume not tabulated) are estimates
FULLER = {"Ar": 16.1, "N2": 17.9, "H2": 6.12, "I2": 59.6, "CO2": 26.9,
          "S2": 2 * 22.9, "MoO3": 22.9 + 3 * 6.11 }
M_SPECIES = {"S2": 64.13, "MoO3": 143.95, "I2": 253.81}


def _omega_mu(Ts):  # Neufeld collision integral, viscosity
    return 1.16145 * Ts**-0.14874 + 0.52487 * math.exp(-0.7732 * Ts) + 2.16178 * math.exp(-2.43787 * Ts)


def _omega_D(Ts):
    return 1.06036 * Ts**-0.1561 + 0.193 * math.exp(-0.47635 * Ts) + 1.03587 * math.exp(-1.52996 * Ts) + 1.76474 * math.exp(-3.89411 * Ts)


def mass(g): return M_SPECIES.get(g) or GAS[g][0]


def viscosity(g, T):
    M, s, e, _ = GAS[g]
    return 2.6693e-6 * math.sqrt(M * T) / (s**2 * _omega_mu(T / e))  # Pa s


def density(g, T, P): return P * mass(g) * 1e-3 / (R * T)


def cp_mass(g): return GAS[g][3] * R / (mass(g) * 1e-3)  # J/kg/K


def conductivity(g, T):  # modified Eucken
    M = GAS[g][0] * 1e-3
    return viscosity(g, T) * (cp_mass(g) + 1.25 * R / M)


def diffusivity(a, b, T, P):
    """Fuller-Schettler-Giddings binary diffusivity, m2/s. P in Pa."""
    Ma, Mb = mass(a), mass(b)
    return 1e-4 * 1e-3 * T**1.75 * math.sqrt(1 / Ma + 1 / Mb) / ((P / 1.01325e5) * (FULLER[a] ** (1 / 3) + FULLER[b] ** (1 / 3)) ** 2)


def prandtl(g, T): return viscosity(g, T) * cp_mass(g) / conductivity(g, T)
