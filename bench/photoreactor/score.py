"""Score the photoreactor against published ferrioxalate actinometry (pre-registered in docs/prereg/track-e.md).
Run: python -m bench.photoreactor.score  -> writes bench/photoreactor/results.json"""
import json, pathlib
import numpy as np
import vessels.photoreactor as pr
from core import params as P
from vessels.photoreactor import H, C_LIGHT, NA

HERE = pathlib.Path(__file__).parent
TOL = {"saenz_qpb_cuvette": 1.25, "saenz_is_cuvette": 1.5}
SIG = {"phi": 0.03, "n_wall": 0.04, "n_liq": 0.02, "wall_mm": 0.05}


def load():
    return json.loads((HERE / "setups.json").read_text())


def predicted_slope(p):
    """Initial conversion per photon fluence, percent / (umol m-2)."""
    v = P.validate(pr.DEFS, p)
    c = pr.core(v)
    Ep = pr.irradiance(v) * 1e4 / (H * C_LIGHT / (v["lambda_nm"] * 1e-9) * NA) * 1e6  # umol m-2 s-1 (W/cm2 -> W/m2)
    return 100 * (c["r0"] / c["n0"]) / Ep, c


def score(name, setup, n_mc=500, seed=0):
    p, meas = setup["params"], setup["measured"]
    a, c = predicted_slope(p)
    R = a / meas["value"]
    oat = {}
    for k, s in SIG.items():
        hi, lo = predicted_slope(p | {k: p[k] + s})[0], predicted_slope(p | {k: p[k] - s})[0]
        oat[k] = abs(np.log(hi / lo)) / 2
    hi, lo = predicted_slope(p | {"eps_A": 1500.0})[0], a
    oat["eps_A(333->1500)"] = abs(np.log(hi / lo))
    rng = np.random.default_rng(seed)
    lo = {d.name: (d.lo, d.hi) for d in pr.DEFS}
    Rs = [predicted_slope(p | {k: float(np.clip(p[k] + s * rng.standard_normal(), *lo[k])) for k, s in SIG.items()})[0] / meas["value"] for _ in range(n_mc)]  # clipped to ParamDef bounds
    alt = {"phi=1.26": predicted_slope(p | {"phi": 1.26})[0] / meas["value"], "n_wall=1.485": predicted_slope(p | {"n_wall": 1.485})[0] / meas["value"]}
    tol = TOL[name]
    s0 = pr.solve(P.validate(pr.DEFS, p))
    return {"predicted_slope": a, "measured_slope": meas["value"], "measured_sigma": meas["sigma"], "ratio": R,
            "ratio_p05_p95": [float(np.percentile(Rs, 5)), float(np.percentile(Rs, 95))], "tolerance_factor": tol,
            "pass": bool(1 / tol <= R <= tol), "wall_T": s0["wall_transmission"], "fraction_absorbed": s0["fraction_absorbed"],
            "Da_mix": s0["Da_mix"], "uncertainty_one_sigma_dln": oat, "main_uncertainty": max(oat, key=oat.get), "sensitivity_ratio": alt}


if __name__ == "__main__":
    out = {k: score(k, v) for k, v in load()["setups"].items()}
    (HERE / "results.json").write_text(json.dumps(out, indent=1))
    for k, r in out.items():
        print(k, f"R={r['ratio']:.3f} p05-p95={r['ratio_p05_p95'][0]:.3f}-{r['ratio_p05_p95'][1]:.3f} tol x{r['tolerance_factor']} pass={r['pass']} main={r['main_uncertainty']} alt={r['sensitivity_ratio']}")
