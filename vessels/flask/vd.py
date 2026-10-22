"""Villermaux-Dushman test reaction and a generic competitive incorporation model.
Verified against (what could be read, Oct 2026):
 - reactions (1) H2BO3- + H+ -> H3BO3 (instantaneous, k1 ~ 1e11 L/mol/s), (2) 5I- + IO3- + 6H+ -> 3I2 + 3H2O,
   rate r2 = k2 [H+]^2 [I-]^2 [IO3-], (3) I2 + I- <-> I3-. Fournier, Falk & Villermaux, Chem Eng Sci 51 (1996) 5053 (not readable);
   rate law and k2(I) as quoted by Mohammadi et al., J Chem Petrochem Eng (jchpe.ut.ac.ir/article_89303), citing Guichardon, Falk &
   Villermaux, Chem Eng Sci 55 (2000) 4245 (Part II): log10 k2 = 9.28105 - 3.664 sqrt(I) for I <= 0.166 M,
   = 8.383 - 1.5112 sqrt(I) + 0.237 I above (k2 in M^-3 s^-1, I = ionic strength in M). The 2021-22 kinetics revisits (Arian & Pauer
   J Flow Chem 2021; Bourne-style perchloric acid refits, ChemRxiv/Ind Eng Chem Res 2021) say k2 is still ionic-strength dependent
   and the sulfuric acid correlation is not trustworthy above ~0.1 M; absolute Xs is therefore uncertain by a factor, ranking is safe.
 - K = [I3-]/([I2][I-]) = 10^(555/T + 7.355 - 2.575 log10 T), Palmer, Ramette & Mesmer, J Solution Chem 13 (1984) 673.
 - Y = 2 (n_I2 + n_I3-) / n_H+,0 ; Y_ST = 6 [IO3-]0 / (6 [IO3-]0 + [H2BO3-]0) ; Xs = Y / Y_ST, Xs = 1 total segregation, 0 ideal
   micromixing (Commenge & Falk, Chem Eng Process 50 (2011) 979, definition as reproduced by PMC9866573 Eq 6-8; Guichardon & Falk 2000).
 - Xs is proportional to the mixing time at small Xs within one concentration set (t_m ~ a Xs; Commenge 2011 as summarised in the SI of
   arXiv:1909.11868, Eq 13). That linearity is a test here.
Segregated limit: the model gives Xs -> 1 as the engulfment time -> infinity (0.8 at t_m = 1e5 s, 0.99 at 1e11 s for the 0.032/0.006 set).
The approach is logarithmically slow because the iodate reaction slows as acid is consumed (rate ~ [H+]^2 [I-]^2) and I3- formation
sequesters iodide when it is near-stoichiometric (5 I-/IO3-). So a value of ~0.7 at finite t_m is chemistry, not a bug.
Concentration sets below are the ones that could be read in full (H+ = 2 x [H2SO4]); the original Fournier 1996 and Guichardon 2000
stirred-tank sets could not be retrieved and are NOT included.
ponytail: ionic strength is from the buffer salts only (acid ignored), k2 at 25 C only (no T-dependence found), aqueous chemistry
whatever the flask solvent, drop volume 1 and a single scalar E (no local E distribution), borate neutralisation algebraic."""
import numpy as np
from scipy.integrate import solve_ivp

# set name: (c_H+, c_H2BO3-, c_I-, c_IO3-) mol/L ; source
VD_SETS = {
    "commenge_style_micromixer": (0.01, 0.09, 0.03, 0.006),  # PMC9866573 Table 1 (KI .03, KIO3 .006, H3BO3 .09 + NaOH .09; H2SO4 .005)
    "tmixer_lowRe": (0.03, 0.09, 0.032, 0.006),  # arXiv:1909.11868 SI Tab S1, H2SO4 0.015 (Re 100-650)
    "tmixer_highRe": (0.05, 0.09, 0.032, 0.006),  # same, H2SO4 0.025 (Re 700-4000)
    "stirred_1M_acid": (1.0, 0.09, 0.03, 0.006),  # acid 1.0 M H+ from Yang et al., Adv Mater Phys Chem 2012, 2, 150 (buffer set of PMC9866573)
}


def K_I3(T):
    return 10 ** (555 / T + 7.355 - 2.575 * np.log10(T))  # Palmer, Ramette, Mesmer 1984


def k2_dushman(I):
    """Guichardon, Falk, Villermaux 2000 via jchpe.ut.ac.ir/article_89303 Eq 5-6; 25 C."""
    s = np.sqrt(I)
    return 10 ** (9.28105 - 3.664 * s) if I <= 0.166 else 10 ** (8.383 - 1.5112 * s + 0.237 * I)


def segregation_index(p, t_micro, T=298.15):
    """Incorporation model: acid drop (volume 1) grows dV/dt = E V, E = 1/t_micro, engulfing bulk reagents. Returns (Xs, Y)."""
    cH, cB, cI, cIO3 = p["vd.c_H_M"], p["vd.c_B_M"], p["vd.c_I_M"], p["vd.c_IO3_M"]
    E = 1 / t_micro
    K = K_I3(T)
    k2 = k2_dushman(cI + cIO3 + cB)  # K+/Na+ counter-ions: I = sum of the 1:1 salt concentrations
    a = cH

    def triiodide(V, nI, nI2):  # moles I3-: K (nI2-x)(nI-x) = x V, stable root
        B = K * (nI2 + nI) + V
        C = K * nI2 * nI
        return 2 * C / (B + np.sqrt(max(B * B - 4 * K * C, 0.0))) if C > 0 else 0.0

    def rhs(t, y):
        V, nI, nIO3, nI2, r6 = y
        x = triiodide(V, nI, nI2)
        nHf = max(a - r6 - cB * (V - 1), 0.0)  # borate takes cB per engulfed volume instantly
        r = k2 * (nHf / V) ** 2 * (max(nI - x, 0) / V) ** 2 * max(nIO3, 0) / V
        return [E * V, E * V * cI - 5 * r * V, E * V * cIO3 - r * V, 3 * r * V, 6 * r * V]

    ev = lambda t, y: a - y[4] - cB * (y[0] - 1) - 1e-9 * a  # free acid exhausted
    ev.terminal = True
    t_end = 1.5 * np.log(1 + cH / cB) / E  # borate alone exhausts the acid by V = 1 + cH/cB
    s = solve_ivp(rhs, (0, t_end), [1.0, 0, 0, 0, 0], method="Radau", rtol=1e-6, atol=1e-14, events=ev)
    Y = 2 * s.y[3, -1] / a
    return float(Y / (6 * cIO3 / (6 * cIO3 + cB))), float(Y)


def Y_ST(p):
    return 6 * p["vd.c_IO3_M"] / (6 * p["vd.c_IO3_M"] + p["vd.c_B_M"])


def incorporation(k1, k2, A0, B0, E, scheme="consecutive", C0=0.0, dilution=None, return_y=False):
    """Semi-batch competitive pair, feed B (conc B0) into bulk A0 (and competitor C0), drop volume 1 grows dV/dt = E V.
    consecutive (Bourne): A + B -> R (k1), R + B -> S (k2). parallel: A + B -> R (k1), C + B -> S (k2).
    Engulfment runs to V_end = 1 + B0/(A0 + C0), then the mixed volume reacts out (E = 0). Returns undesired fraction
    X = 2 xi2/(xi1+xi2) (consecutive, Bourne's Xs) or xi2/(xi1+xi2) (parallel), xi = reaction extents."""
    cons = scheme == "consecutive"
    Vend = dilution or 1 + B0 / (A0 + C0)

    def rhs(E_):
        def f(t, y):
            V, A, C, B, R, S, x1, x2 = y
            r1 = k1 * A * B / V
            r2 = k2 * (R if cons else C) * B / V
            return [E_ * V, E_ * V * A0 - r1, E_ * V * C0 - (0 if cons else r2), -r1 - r2, r1 - (r2 if cons else 0), r2, r1, r2]
        return f

    y0 = [1.0, 0, 0, B0, 0, 0, 0, 0]
    s1 = solve_ivp(rhs(E), (0, np.log(Vend) / E), y0, method="Radau", rtol=1e-6, atol=1e-12)
    y1 = s1.y[:, -1]
    y1[0] = Vend
    t2 = 60 / (min(k for k in (k1, k2) if k > 0) * min(A0, B0 / Vend))  # ~60 slowest half-lives of the mixed volume
    s2 = solve_ivp(rhs(0.0), (0, t2), y1, method="Radau", rtol=1e-6, atol=1e-12)
    y = s2.y[:, -1]
    X = (2 if cons else 1) * y[7] / max(y[6] + y[7], 1e-300)
    return (float(min(X, 1.0)), y) if return_y else float(min(X, 1.0))
