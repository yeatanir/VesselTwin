"""Monte-Carlo wrapper: perturb params by their sigma, run a fast scalar solver, return percentile Dists."""
import numpy as np
from schemas.passport import Dist, Passport
from core.params import ParamDef


def sample(defs: list[ParamDef], values: dict, rng) -> dict:
    out = dict(values)
    for d in defs:
        if d.sigma and d.choices is None:
            v = values[d.name]
            s = d.sigma * abs(v) if d.sigma_rel else d.sigma
            x = v + s * rng.standard_normal()
            out[d.name] = min(max(x, d.lo if d.lo is not None else -np.inf), d.hi if d.hi is not None else np.inf)
    return out


def monte_carlo(solve, defs, values, n=100, seed=0) -> dict[str, Dist]:
    """solve(values) -> {key: float}. Returns {key: Dist(p05,p50,p95)}; failed samples are dropped."""
    rng = np.random.default_rng(seed)
    runs = [solve(values)]  # sample 0 is the nominal case
    for _ in range(n - 1):
        try:
            runs.append(solve(sample(defs, values, rng)))
        except (ValueError, FloatingPointError):
            pass
    keys = runs[0].keys()
    res = {}
    for k in keys:
        a = np.array([r[k] for r in runs], float)
        a = a[np.isfinite(a)]
        res[k] = Dist(p05=float(np.percentile(a, 5)), p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95))) if len(a) else Dist(p50=float("nan"))
    return res


def to_passport(vessel, site, source, mc: dict[str, Dist], units: dict[str, str], synthetic: bool, tier=1) -> Passport:
    """Key convention: 'T_K', 'species.<name>.<qty>', everything else -> derived."""
    sp, der = {}, {}
    for k, d in mc.items():
        d = d.model_copy(update={"unit": units.get(k, "")})
        if k.startswith("species."):
            _, name, qty = k.split(".", 2)
            sp.setdefault(name, {})[qty] = d
        elif k != "T_K":
            der[k] = d
    return Passport(vessel=vessel, site=site, T_K=mc["T_K"].model_copy(update={"unit": "K"}), species=sp,
                    derived=der, source=source, tier=tier, synthetic=synthetic)
