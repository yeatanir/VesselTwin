"""GP surrogate of the ampoule convection factor f_CFD (OpenFOAM sink rate / diffusion-only rate) over the sweep inputs.
Inputs: D_mm, L_cm, dT_K (= T_source-T_sink, sink 800 C in the sweep), tilt_deg, agent_mg_per_cm3. Target: log f_CFD.
fit(sweep_json) reads docs/ampoule_cfd_verification.json ("sweep": rows with the inputs, f_cfd, ok), splits 75/25 (seeded), fits an ARD-RBF
GP, saves surrogate/data/ampoule_gp.json (training data + kernel hyperparameters; predict() refits with optimizer=None, so no pickle).
ponytail: one GP, no model zoo; valid only inside the sweep box (in_range flag), other params (thermo, T_sink level) at defaults."""
import json, pathlib, warnings
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel as C

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = ROOT / "data" / "ampoule_gp.json"
NAMES = ["D_mm", "L_cm", "dT_K", "tilt_deg", "agent_mg_per_cm3"]
LO, HI = [6, 8, 10, -90, 0.5], [45, 20, 150, 90, 15]  # sweep box (scripts/ampoule_sweep_design.py)


def _x(v):
    v = dict(v)
    if "dT_K" not in v:
        v["dT_K"] = v["T_source_C"] - v["T_sink_C"]
    return np.array([np.log(v["D_mm"]), v["L_cm"], v["dT_K"], v["tilt_deg"], np.log(v["agent_mg_per_cm3"])], float)


def _gp(X, y, theta=None, k=None):
    return GPR(k if k is not None else C(1.0) * RBF(np.ones(X.shape[1]), (0.1, 1e3)) + WhiteKernel(1e-3, (1e-6, 1e-1)),
               normalize_y=True, n_restarts_optimizer=5 if theta is None else 0, optimizer="fmin_l_bfgs_b" if theta is None else None, random_state=0)


def fit(sweep_json, out=MODEL, test_frac=0.25, seed=0):
    rows = [r for r in json.load(open(sweep_json))["sweep"] if r.get("ok") and r.get("f_cfd")]
    X, y = np.array([_x(r["values"]) for r in rows]), np.log([r["f_cfd"] for r in rows])
    idx = np.random.default_rng(seed).permutation(len(rows))
    nt = int(round(test_frac * len(rows)))
    te, tr = idx[:nt], idx[nt:]
    mu, sd = X[tr].mean(0), X[tr].std(0)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # bound-hit ConvergenceWarnings on short length scales are expected
        g = _gp((X[tr] - mu) / sd, y[tr]).fit((X[tr] - mu) / sd, y[tr])
    err = np.abs(np.exp(g.predict((X[te] - mu) / sd)) / np.exp(y[te]) - 1)  # relative error of f
    errm1 = np.abs((np.exp(g.predict((X[te] - mu) / sd)) - 1) - (np.exp(y[te]) - 1))  # absolute error in f-1 (convective enhancement)
    model = dict(names=NAMES, lo=LO, hi=HI, mu=mu.tolist(), sd=sd.tolist(), X=X[tr].tolist(), y=y[tr].tolist(), kernel=str(g.kernel_), theta=g.kernel_.theta.tolist(),
                 ids=[rows[i]["id"] for i in tr], test_ids=[rows[i]["id"] for i in te],
                 heldout=dict(n_train=len(tr), n_test=len(te), mean_rel_err_f=float(err.mean()), max_rel_err_f=float(err.max()), median_rel_err_f=float(np.median(err)),
                              mean_abs_err_fm1=float(errm1.mean()), max_abs_err_fm1=float(errm1.max()), frac_within_5pct=float((err <= 0.05).mean())))
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(model, open(out, "w"), indent=1)
    return model


def load(path=MODEL):
    m = json.load(open(path))
    X, y = (np.array(m["X"]) - m["mu"]) / m["sd"], np.array(m["y"])
    k = C(1.0) * RBF(np.ones(X.shape[1])) + WhiteKernel(1e-3)
    g = _gp(X, y, theta=m["theta"], k=k.clone_with_theta(np.array(m["theta"]))).fit(X, y)
    return m, g


def predict_full(values, path=MODEL):
    """Dashboard form: f (convection factor), 1-sigma interval [f_lo, f_hi], regime guess (f > 1.2), in_range (inside the sweep box)."""
    m, g = load(path)
    x = _x(values)
    mean, s = g.predict(((x - m["mu"]) / m["sd"])[None], return_std=True)
    f, lo, hi = (float(np.exp(mean[0] + k * s[0])) for k in (0, -1, 1))
    ok = bool(np.all(x[[0, 4]] >= np.log([m["lo"][0], m["lo"][4]])) and np.all(x[[0, 4]] <= np.log([m["hi"][0], m["hi"][4]]))
              and np.all(x[[1, 2, 3]] >= [m["lo"][1], m["lo"][2], m["lo"][3]]) and np.all(x[[1, 2, 3]] <= [m["hi"][1], m["hi"][2], m["hi"][3]]))
    return dict(f=f, f_lo=lo, f_hi=hi, convection_assisted=f > 1.2, in_range=ok)


def predict(values, path=MODEL):
    return predict_full(values, path)["f"]


def fit_default():
    return fit(ROOT.parent / "docs" / "ampoule_cfd_verification.json")
