"""GP surrogate of the MoS2-tube Tier 2 (OpenFOAM) outputs at the substrate: Mo:S ratio and MoO3 supersaturation (wall T), over the sweep inputs.
Targets: ratio_Mo_S, MoO3 supersaturation vs wall T and vs gas T. Inputs: flow_sccm, T_boat_Mo_C, T_furnace_C, tube_id_in, x_substrate_cm (rest at ParamDef defaults). Targets: log of each output.
fit(sweep_json) reads docs/tube_cfd_verification.json ("sweep": rows with `values`, `ratio_Mo_S`, `supersaturation_MoO3_wallT`, `ok`), splits 75/25 (seeded),
fits one ARD-RBF GP per target and stores training data + kernel hyperparameters in surrogate/data/tube_gp.json (no pickle).
ponytail: one GP per target, no model zoo; valid only inside the sweep box (in_range flag)."""
import json, pathlib
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process.kernels import RBF, WhiteKernel, ConstantKernel as C

ROOT = pathlib.Path(__file__).resolve().parent
MODEL = ROOT / "data" / "tube_gp.json"
NAMES = ["flow_sccm", "T_boat_Mo_C", "T_furnace_C", "tube_id_in", "x_substrate_cm"]
LO, HI = [30, 600, 650, 0.5, 1.0], [1500, 800, 900, 2.5, 20.0]  # sweep box (scripts/tube_cfd_verification.py lhs)
TARGETS = ["ratio_Mo_S", "supersaturation_MoO3_wallT", "ss_gasT"]


def _x(v):
    d = {"flow_sccm": 100.0, "T_boat_Mo_C": 700.0, "T_furnace_C": 750.0, "tube_id_in": 1.0, "x_substrate_cm": 12.0} | dict(v)  # ParamDef defaults
    return np.array([np.log(d["flow_sccm"]), d["T_boat_Mo_C"], d["T_furnace_C"], np.log(d["tube_id_in"]), d["x_substrate_cm"]], float)


def _k(n): return C(1.0) * RBF(np.ones(n), (0.1, 100)) + WhiteKernel(1e-3, (1e-8, 1e-1))


def fit(sweep_json, out=MODEL, test_frac=0.25, seed=0):
    rows = [r for r in json.load(open(sweep_json))["sweep"] if r.get("ok")]
    X = np.array([_x(r["values"]) for r in rows])
    idx = np.random.default_rng(seed).permutation(len(rows))
    nt = int(round(test_frac * len(rows)))
    te, tr = idx[:nt], idx[nt:]
    mu, sd = X[tr].mean(0), X[tr].std(0)
    Z = (X - mu) / sd
    m = dict(names=NAMES, lo=LO, hi=HI, mu=mu.tolist(), sd=sd.tolist(), ids=[rows[i]["id"] for i in tr], test_ids=[rows[i]["id"] for i in te], targets={})
    for t in TARGETS:
        y = np.log([r[t] for r in rows])
        g = GPR(_k(5), normalize_y=True, n_restarts_optimizer=5, random_state=0).fit(Z[tr], y[tr])
        err = np.abs(np.exp(g.predict(Z[te])) / np.exp(y[te]) - 1)
        m["targets"][t] = dict(X=Z[tr].tolist(), y=y[tr].tolist(), theta=g.kernel_.theta.tolist(), kernel=str(g.kernel_),
                               heldout=dict(n_train=len(tr), n_test=len(te), mean_rel_err=float(err.mean()), median_rel_err=float(np.median(err)),
                                            max_rel_err=float(err.max()), frac_within_5pct=float((err <= 0.05).mean())))
    pathlib.Path(out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(m, open(out, "w"), indent=1)
    return m


def _load(path, t):
    m = json.load(open(path))
    d = m["targets"][t]
    X, y = np.array(d["X"]), np.array(d["y"])
    g = GPR(_k(5).clone_with_theta(np.array(d["theta"])), normalize_y=True, optimizer=None).fit(X, y)
    return m, g


def predict_full(values, target="ratio_Mo_S", path=MODEL):
    """value, 1-sigma interval [lo, hi] (log-normal), in_range (inside the sweep box)."""
    m, g = _load(path, target)
    x = _x(values)
    mean, s = g.predict(((x - m["mu"]) / m["sd"])[None], return_std=True)
    v, lo, hi = (float(np.exp(mean[0] + k * s[0])) for k in (0, -1, 1))
    xr = np.array([np.exp(x[0]), x[1], x[2], np.exp(x[3]), x[4]])
    return dict(value=v, lo=lo, hi=hi, in_range=bool(np.all(xr >= m["lo"]) and np.all(xr <= m["hi"])))


def predict(values, target="ratio_Mo_S", path=MODEL): return predict_full(values, target, path)["value"]


def uncertainty(values, target="ratio_Mo_S", path=MODEL):
    r = predict_full(values, target, path)
    return r["lo"], r["hi"]


def in_range(values, path=MODEL): return predict_full(values, TARGETS[0], path)["in_range"]
