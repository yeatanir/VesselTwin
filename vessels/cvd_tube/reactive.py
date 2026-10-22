"""Track M: reactive substrate sink and wall-uptake variants for the MoS2 tube (all behind explicit switches; defaults reproduce the old model).

PROPOSED REDUCED-ORDER CLOSURE, NOT A VALIDATED MoS2 KINETIC LAW. No source is open for any constant below; all are synthetic.

Closure (substrate_uptake_model = "reactive"). The default model deposits Mo on the substrate only where the MoO3 pressure exceeds the pure-MoO3
saturation pressure at the substrate temperature (condensation: J = k_m (C_bulk - C_sat(T_sub)), zero when the substrate is as hot as the boat).
MoS2 forms by sulfurization, treated here as irreversible, so the substrate is instead a first-order sink in series with gas-side transfer:
    J_Mo,sub = k_eff (C_Mo,bulk - C_Mo,eq_rxn),   k_eff = k_m k_rxn / (k_m + k_rxn),
    k_rxn = k0 exp(-Ea / k_B T_sub) a_S^n,        a_S = p_S2(local) / S_ref_Pa.
k_m is the model's existing substrate mass-transfer coefficient (Sh D/d times the Stefan factor), C_Mo,eq_rxn = C_eq_rxn_Pa/(R T) (0 = irreversible).
Limits: k_rxn -> inf gives k_eff -> k_m (mass-transfer limited), k_rxn -> 0 gives zero flux.
Assumptions: first-order in the Mo supply (formula-unit pressure of (MoO3)n, vapour-phase intermediates instantaneous as in the base model); power law in
sulfur activity; no sulfur depletion by the film; Arrhenius with one effective barrier; no film-thickness or nucleation dependence; the reactive
sink uses the substrate temperature (wall T + T_substrate_offset_K) and S2 from the local gas composition (thermo.s2_fraction).
Plausible ranges (synthetic, NOT from a source): log10 k0 in [-3, 2] (k0 in m/s; upper end = Hertz-Knudsen limit v_bar/4 ~ 55 m/s for (MoO3)3 at 1000 K,
i.e. unit sticking; lower end = reaction ~1e5 slower than that); Ea in [0, 2] eV (0 = barrierless sulfurization, 2 eV = upper end of oxide
surface-reaction barriers; no value opened); n in [0, 2] (0 = independent of S; 1-2 = one or two S2 per Mo unit). With k_m ~ 1e-2 m/s the combined
range spans fully reaction-limited to fully mass-transfer-limited at 1100 K. They are never tuned to the benchmark.

Wall variants (wall_uptake_model): "condensation" (default, old), "reflecting" (no wall uptake; only the substrate area removes Mo),
"sticking" (condensation driving force with a finite accommodation: k_w = k_m s v/(k_m + s v), v = sqrt(RT/(2 pi n M)) from Hertz-Knudsen,
s = wall_sticking in [1e-4, 1]), "reactive" (the same k_rxn law as the substrate on the wall area, at the wall T, C_eq = C_eq_rxn).
Scoped sigmas (a ParamDef sigma adds an RNG draw per MC sample and would shift every stored default MC stream; same reason as thermo.with_liq_sigma):
use `with_structural_sigma()` to enable them."""
from contextlib import contextmanager
import numpy as np
from core.params import ParamDef as P

KB = 8.617333e-5  # eV/K
SYN = "synthetic"
SUB_MODELS = ["condensation", "reactive"]
WALL_MODELS = ["condensation", "reflecting", "sticking", "reactive"]
RANGES = {  # synthetic plausible ranges used by the structural ensemble (bench/track_m_score.py); sampled uniformly in the stated variable
    "rxn_log10_k0_m_s": (-3.0, 2.0), "rxn_Ea_eV": (0.0, 2.0), "rxn_n_S": (0.0, 2.0), "wall_log10_sticking": (-4.0, 0.0)}
_TAG = "proposed reduced-order closure, not a validated MoS2 kinetic law; "
RDEFS = [
    P("substrate_uptake_model", "Substrate Mo uptake closure", "", "condensation", choices=SUB_MODELS, group="model",
      help=_TAG + "condensation (default): J = k_m (C - C_sat(T_sub))+. reactive: J = k_eff (C - C_eq_rxn), k_eff = k_m k_rxn/(k_m+k_rxn), "
           "k_rxn = k0 exp(-Ea/kT_sub) a_S^n (irreversible sulfurization sink)"),
    P("wall_uptake_model", "Tube-wall Mo uptake closure", "", "condensation", choices=WALL_MODELS, group="model",
      help="condensation (default, old); reflecting = zero flux; sticking = condensation with finite sticking wall_sticking; reactive = same k_rxn law as the substrate at the wall T"),
    P("rxn_log10_k0_m_s", "log10 of the sulfurization rate prefactor k0 (k0 in m/s)", "", 1.0, -12.0, 12.0, 0.0, False, source=SYN, group="model",
      help=_TAG + "plausible range -3..2 (upper end = Hertz-Knudsen limit, ~55 m/s); the wide hard bounds only allow limit tests; scoped sigma 1.0 dex (with_structural_sigma)"),
    P("rxn_Ea_eV", "Sulfurization activation energy Ea", "eV", 0.5, 0.0, 6.0, 0.0, False, source=SYN, group="model",
      help=_TAG + "plausible range 0..2 eV; no source opened; scoped sigma 0.5 eV"),
    P("rxn_n_S", "Order in sulfur activity n", "", 1.0, 0.0, 4.0, 0.0, False, source=SYN, group="model",
      help=_TAG + "plausible range 0..2; scoped sigma 0.5"),
    P("S_ref_Pa", "Reference S2 pressure for a_S = p_S2 / S_ref", "Pa", 50.0, 1e-3, 1e6, source=SYN, group="model",
      help="convention only: rounded default S2 pressure at the default substrate (48.5 Pa); a different reference is absorbed into k0"),
    P("C_eq_rxn_Pa", "Pressure-equivalent of C_Mo,eq_rxn for the reactive sink", "Pa", 0.0, 0.0, 1e3, 0.0, False, source=SYN, group="model",
      help="0 = irreversible sulfurization (default); equivalent formula-unit pressure at which the reactive sink stops"),
    P("wall_sticking", "Wall sticking coefficient (wall_uptake_model=sticking)", "", 1.0, 1e-4, 1.0, source=SYN, group="model",
      help="accommodation of MoO3 vapour on the wall in the Hertz-Knudsen velocity; sweep 1e-4..1; no measured value"),
]
SCOPED_SIGMA = {"rxn_log10_k0_m_s": 1.0, "rxn_Ea_eV": 0.5, "rxn_n_S": 0.5, "T_substrate_offset_K": 30.0}


@contextmanager
def with_structural_sigma(defs, sigmas=None, only_if=None):
    """Temporarily give the synthetic closure constants (and, for items whose substrate temperature the paper does not state, the substrate
    temperature offset, sigma 30 K) a wide sigma for the existing Monte Carlo. only_if: dict of values that must be set to enable (e.g. reactive model)."""
    s = SCOPED_SIGMA if sigmas is None else sigmas
    by = {d.name: d for d in defs}
    old = {k: by[k].sigma for k in s if k in by}
    on = only_if is None or only_if.get("substrate_uptake_model") == "reactive" or only_if.get("wall_uptake_model") == "reactive"
    try:
        if on:
            for k, v in s.items():
                if k in by: by[k].sigma = v
        yield
    finally:
        for k, v in old.items(): by[k].sigma = v


def k_rxn(p, T, p_S2):
    """k_rxn = k0 exp(-Ea/kT) a_S^n [m/s]; T [K], p_S2 [Pa] (scalars or arrays)."""
    aS = np.maximum(p_S2, 0.0) / p["S_ref_Pa"]
    return 10.0 ** p["rxn_log10_k0_m_s"] * np.exp(-p["rxn_Ea_eV"] / (KB * T)) * aS ** p["rxn_n_S"]


def series(km, kr):
    """k_m k_r / (k_m + k_r), stable for kr -> inf (-> km) and kr -> 0 (-> 0)."""
    kr = np.asarray(kr, float)
    return km / (1.0 + km / np.maximum(kr, 1e-300))  # kr = inf -> km, kr = 0 -> ~0
