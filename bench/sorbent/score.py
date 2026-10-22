"""Part 2 scoring (pre-registered in docs/prereg/track-e.md): 13X wall heat transfer fit/hold-out, CALF-20 unchanged, IAST vs EDSL.
Run: PYTHONPATH=<dir with pyiast> python -m bench.sorbent.score  -> bench/sorbent/results.json"""
import json, pathlib, sys
import numpy as np
from scipy.optimize import brentq
from core import props
from vessels.sorbent import benchmark as bm, DATA
import vessels.sorbent as sb

HERE = pathlib.Path(__file__).parent
COL = bm.B["13X_Z1002ND_breakthrough_CO2_He"]["column"]


def run13(h_in):
    old = COL["h_in"]
    COL["h_in"] = h_in
    try:
        return bm.x13_breakthrough()
    finally:
        COL["h_in"] = old


def reynolds():
    """Particle Reynolds number at the two 13X flows (He, 295 K, 1 bar, sccm taken at 273.15 K), d_p = assumed 2 mm."""
    T, A, dp = 273.15 + COL["T_C"], np.pi / 4 * COL["D_m"] ** 2, COL["dp_mm_ASSUMED"] * 1e-3
    out = {}
    for k, q in COL["flows_sccm"].items():
        u = q * 1e-6 / 60 * T / 273.15 / A
        out[k] = props.density("He", T, 1e5) * u * dp / props.viscosity("He", T)
    return out


def fit_t50(idx):
    """Method 1 (pre-registered): root of the t50 error; none exists in the bounds, so return the bounded minimiser of |err| (a boundary value)."""
    from scipy.optimize import minimize_scalar
    r = minimize_scalar(lambda h: abs(run13(h)[idx]["err"]), bounds=(0.5, 300.0), method="bounded", options={"xatol": 1e-2})
    return float(r.x)


def fit_tpeak(idx):
    """Method 2 (Amendment 1): root of (model T_peak - measured T_peak) at z = 0.8 L."""
    f = lambda h: run13(h)[idx]["Tpeak_model_C"] - run13(h)[idx]["Tpeak_exp_C"]
    return brentq(f, 0.5, 300.0, xtol=1e-3)


def calf():
    sb._CACHE.clear(); sb._PAT.clear()  # the Jacobian-pattern cache leaks between columns and moves CALF-20 t50 by ~2 pp at RTOL 3e-3 (see progress file)
    return [r["err"] for r in bm.calf20_breakthrough()]


def iast():
    import pyiast, pandas as pd
    p = bm._p("sorbent__13X_CO2", P_kPa=102.0)
    pk = sb._pk(p)
    out = []
    for r in bm.B["13X_Z1002ND_competitive"]["points"]:
        T = 273.15 + r["T_C"]
        yw = r["RH"] * sb.psat(T) / 102e3
        pg = {"CO2": np.geomspace(1e-5, 1e3, 200), "H2O": np.geomspace(1e-9, 1e3, 200)}  # bar
        iso = {}
        for sp in ("CO2", "H2O"):
            q = [float(sb._eq(pk, {sp: np.array([x * 1e5 / (sb.R * T)])}, T)[sp][0]) for x in pg[sp]]
            df = pd.DataFrame({"P": pg[sp], "L": q})
            i = sb.SPS.index(sp)  # exact pure-component parameters of the model (K in 1/bar) as starting guess: the fit only has to confirm them
            Kb = [float(pk["K0s"][i][k] * np.exp(pk["Qs"][i][k] * (1 / T - 1 / sb.T0)) / (sb.R * T) * 1e5) for k in (0, 1)]
            guess = {"M1": float(pk["qss"][i][0]), "K1": Kb[0], "M2": float(pk["qss"][i][1]), "K2": Kb[1]}
            iso[sp] = pyiast.ModelIsotherm(df, loading_key="L", pressure_key="P", model="DSLangmuir", param_guess=guess)
        q_iast = pyiast.iast(np.array([(1 - yw) * 1.02, yw * 1.02]), [iso["CO2"], iso["H2O"]])  # bar
        e = sb._eq(pk, {"CO2": np.array([(1 - yw) * 102e3 / (sb.R * T)]), "H2O": np.array([yw * 102e3 / (sb.R * T)])}, T)
        out.append({"RH": r["RH"], "qCO2_exp": r["q_CO2"], "qH2O_exp": r["q_H2O"], "qCO2_edsl": float(e["CO2"][0]), "qH2O_edsl": float(e["H2O"][0]),
                    "qCO2_iast": float(q_iast[0]), "qH2O_iast": float(q_iast[1])})
    for o in out:
        for sp in ("CO2", "H2O"):
            for m in ("edsl", "iast"):
                o[f"err_{sp}_{m}"] = o[f"q{sp}_{m}"] / o[f"q{sp}_exp"] - 1
    return out


if __name__ == "__main__":
    res = {"Re_p": reynolds(), "before": run13(COL["h_in"]), "calf20_before": calf()}
    h1 = fit_t50(0)
    res["method1_h_in"], res["method1_after"] = h1, run13(h1)
    h2 = fit_tpeak(0)  # fit on y = 0.15, hold out y = 0.5
    res["method2_h_in"], res["method2_after"] = h2, run13(h2)
    res["calf20_after_method2"] = calf()  # CALF-20 has its own h_in; asserts nothing moved
    h2r = fit_tpeak(1)
    res["method2_reverse_h_in"], res["method2_reverse_after"] = h2r, run13(h2r)
    res["iast"] = iast()
    (HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: v for k, v in res.items() if k != "iast"}, indent=1, default=float)[:3500])
    print(json.dumps(res["iast"], indent=1, default=float))
