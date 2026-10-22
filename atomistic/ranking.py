"""Decision ranking: which atomistic calculation would most change the experimental outcome?
Expected change = |d outcome / d param| * sigma_param, central finite differences through Tier 1 (core.api.solve only).
ponytail: inherits every Tier 1 placeholder (synthetic constants make the numbers illustrative, the machinery is real);
sigma is the ParamDef 1-sigma (stand-in for ensemble disagreement); linear response, no interactions between params."""
import json, re
import numpy as np
from core import api

# outcome per vessel: (key, label, unit). 'boundary_cm' comes from extras.shape_map, others from passport.derived p50.
OUTCOMES = {
    "cvd_tube": ("boundary_cm", "triangle-hexagon shape boundary position from the MoO3 boat", "cm"),
    "ampoule": ("transport_rate_mmol_h", "transport rate", "mmol/h"),
    "flask": ("Da_micro", "micromixing Damkohler number t_micro/t_reaction (mixing-sensitive margin)", ""),
    "sorbent": ("t_break5_min", "breakthrough time at 5%", "min"),
    "photoreactor": ("Da_mix", "photon-supply / mixing-supply ratio (>1 mass-transfer limited)", ""),
}
COST_WEIGHT = {"cheap": 1, "medium": 10, "expensive": 100}  # editable; relative CPU-time classes
# (param-name regex, calculation type, cost class); first match wins. Params matching nothing are not atomistic candidates.
CALC_TABLE = [
    (r"^gamma_edge_", "DFT edge energy vs mu_S (nanoribbon)", "medium"),
    (r"^k_attach_.*\.Ea_eV", "ReaxFF/MLIP attachment barrier (NEB)", "medium"),
    (r"^k_attach_.*\.A$", "MLIP-MD / TST attachment prefactor", "expensive"),
    (r"^alpha_", "MLIP-MD evaporation/sticking coefficient", "expensive"),
    (r"(^|\.)(dH_kJmol|dS_JmolK|P_ref_Pa)$", "DFT/JANAF thermochemistry of gas species", "cheap"),
    (r"^D0_cm2s$", "ab initio collision integral / diffusivity", "cheap"),
    (r"^k2_M_s$", "xTB/DFT competing-pathway barrier", "medium"),
    (r"^isotherm\.(qmax|b_ref)$", "GCMC isotherm (MLIP/DFT-fit force field)", "medium"),
    (r"^isotherm\.Q$", "DFT binding energy + GCMC isosteric heat", "medium"),
    (r"^k_ldf$", "MLIP-MD pore diffusivity", "expensive"),
]
ATOMISTIC_GROUPS = {"thermo", "isotherm", "wulff", "reaction", "model"}
RATIONALE = ("Pin down {param} ({label}) with {calc} [{cost}]: its one-sigma uncertainty ({sigma} {unit}) "
             "moves the {outcome} by {delta} {ounit}.")
_memo: dict = {}


def _g(x):
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.3g}"


def solve(vessel, ov, key, n_mc=1, seed=0):
    k = (vessel, json.dumps(ov, sort_keys=True), key == "boundary_cm", n_mc, seed)
    if k not in _memo:
        _memo[k] = api.solve(vessel, ov, n_mc=n_mc, seed=seed, extras=key == "boundary_cm")
    return _memo[k]


def outcome_value(res, key):
    if key == "boundary_cm":
        return float(res["extras"]["shape_map"]["boundary_cm_from_boat"])
    return float(res["passport"]["derived"][key]["p50"])


def _outcome(vessel, outcome):
    key, label, unit = (outcome, outcome, "") if outcome else OUTCOMES[vessel]
    if outcome and vessel in OUTCOMES and outcome == OUTCOMES[vessel][0]:
        key, label, unit = OUTCOMES[vessel]
    return key, label, unit


def _sigma(d, v):
    return d["sigma"] * abs(v) if d["sigma_rel"] else d["sigma"]


def _base(vessel, values):
    return api.defaults(vessel) | (values or {})


def _solve_with(vessel, values, name, x, key, n_mc, seed):
    return outcome_value(solve(vessel, (values or {}) | {name: x}, key, n_mc, seed), key)


def uncertain(vessel):
    return [d for d in api.schema(vessel) if d["sigma"] and d["choices"] is None]


def slopes(vessel, values=None, outcome=None, n_mc=1, seed=0, h=0.5):
    """Central difference for every uncertain param: signed slope, sigma, d(outcome) for +-sigma. Sorted by |d|."""
    key = _outcome(vessel, outcome)[0]
    base = _base(vessel, values)
    out = []
    for d in uncertain(vessel):
        v, s = base[d["name"]], _sigma(d, base[d["name"]])
        lo = max(v - h * s, d["lo"]) if d["lo"] is not None else v - h * s
        hi = min(v + h * s, d["hi"]) if d["hi"] is not None else v + h * s
        if hi <= lo or s == 0:
            continue
        fm, fp = _solve_with(vessel, values, d["name"], lo, key, n_mc, seed), _solve_with(vessel, values, d["name"], hi, key, n_mc, seed)
        slope = (fp - fm) / (hi - lo)
        slope = slope if np.isfinite(slope) else 0.0
        out.append({"param": d["name"], "label": d["label"], "unit": d["unit"], "group": d["group"], "source": d["source"],
                    "value": v, "sigma": s, "slope": slope, "delta": abs(slope) * s})
    return sorted(out, key=lambda r: -r["delta"])


def _calc(r):
    for rx, calc, cost in CALC_TABLE:
        if re.search(rx, r["param"]) and r["group"] in ATOMISTIC_GROUPS:
            return calc, cost
    return None


def rank_calculations(vessel, values=None, outcome=None, n_mc=1, seed=0) -> list[dict]:
    key, label, ounit = _outcome(vessel, outcome)
    rows = []
    for r in slopes(vessel, values, outcome, n_mc, seed):
        c = _calc(r)
        if c is None:
            continue
        rows.append(r | {"calc": c[0], "cost": c[1], "cost_weight": COST_WEIGHT[c[1]], "outcome": label, "outcome_unit": ounit,
                         "expected_change": r["delta"], "per_cost": r["delta"] / COST_WEIGHT[c[1]]})
    for i, r in enumerate(rows, 1):
        r["rank"] = i
        r["rationale"] = RATIONALE.format(param=r["param"], label=r["label"], calc=r["calc"], cost=r["cost"], sigma=_g(r["sigma"]),
                                          unit=r["unit"] or "-", outcome=label, delta=_g(r["delta"]), ounit=ounit or "-")
    return rows


def benchmark(vessel, values=None, outcome=None, n_seeds=50, n_mc=1, pool="candidates") -> dict:
    """Does the top-ranked calculation change the outcome more than a random one? Each seed draws an actual parameter error
    z_i~N(0,1) sigma for every param, evaluates the true Tier 1 response (interpolated on a z-grid of real solves) and compares.
    pool: 'candidates' (random atomistic calc) or 'all' (random uncertain param, atomistic or not)."""
    key = _outcome(vessel, outcome)[0]
    cand = [r["param"] for r in rank_calculations(vessel, values, outcome, n_mc)]
    names = cand if pool == "candidates" else [r["param"] for r in slopes(vessel, values, outcome, n_mc)]
    if not cand or len(names) < 2:
        return {"vessel": vessel, "pool": pool, "n_candidates": len(cand), "n_pool": len(names), "rank1_win": None, "top3_win": None}
    base, by = _base(vessel, values), {d["name"]: d for d in uncertain(vessel)}
    grid = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    f0 = outcome_value(solve(vessel, values or {}, key, n_mc), key)
    curves = {}
    for n in names:
        d, v = by[n], base[n]
        fs = []
        for z in grid:
            x = v + z * _sigma(d, v)
            x = min(max(x, d["lo"] if d["lo"] is not None else -np.inf), d["hi"] if d["hi"] is not None else np.inf)
            fs.append(f0 if z == 0 else _solve_with(vessel, values, n, x, key, n_mc, 0))
        curves[n] = np.abs(np.nan_to_num(np.array(fs) - f0))
    rng = np.random.default_rng(0)
    w1 = w3 = 0
    top = cand[0]
    for _ in range(n_seeds):
        z = dict(zip(names, rng.standard_normal(len(names))))
        d = {n: float(np.interp(z[n], grid, curves[n])) for n in names}
        others = [n for n in names if n != top]
        w1 += d[top] > d[others[rng.integers(len(others))]]
        w3 += max(d[n] for n in cand[:3]) > np.median(list(d.values()))
    return {"vessel": vessel, "pool": pool, "n_candidates": len(cand), "n_pool": len(names), "n_seeds": n_seeds,
            "rank1_win": w1 / n_seeds, "top3_win": w3 / n_seeds, "top": top}
