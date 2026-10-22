"""Multi-fidelity surrogate: a GP learns y = log10(CFD / Tier 1) per output; prediction = Tier 1 * 10^y_hat with a predictive band.
Pre-registered in docs/prereg/track-b.md (B2). Matern(nu=2.5) ARD + WhiteKernel, >= 10 restarts, inputs standardised in-fold, LOO by `loo`.
Models are stored as JSON (data + fitted theta), no pickle. ponytail: valid only inside the sweep box (in_range)."""
import json, pathlib, warnings
import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor as GPR
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel as C

ROOT = pathlib.Path(__file__).resolve().parent
LOG = {"ampoule": [1, 1, 0, 0, 1], "tube": [1, 0, 0, 1, 1]}  # which inputs are log-transformed (sizes, flows, loadings)
NAMES = {"ampoule": ["D_mm", "L_cm", "dT_K", "tilt_deg", "agent_mg_per_cm3"], "tube": ["flow_sccm", "T_boat_Mo_C", "T_furnace_C", "tube_id_in", "x_substrate_cm"]}
BOX = {"ampoule": ([6, 8, 10, -90, 0.5], [45, 20, 150, 90, 15]), "tube": ([30, 600, 650, 0.5, 1.0], [1500, 800, 900, 2.5, 20.0])}
DEFAULT = {"tube": {"flow_sccm": 100.0, "T_boat_Mo_C": 700.0, "T_furnace_C": 750.0, "tube_id_in": 1.0, "x_substrate_cm": 12.0}}


def raw(kind, v):
    v = dict(DEFAULT.get(kind, {})) | dict(v)
    if kind == "ampoule" and "dT_K" not in v: v["dT_K"] = v["T_source_C"] - v["T_sink_C"]
    return np.array([v[n] for n in NAMES[kind]], float)


def feat(kind, raws):
    X = np.atleast_2d(np.array(raws, float)).copy()
    for j, lg in enumerate(LOG[kind]):
        if lg: X[:, j] = np.log(X[:, j])
    return X


def kernel(n=5):
    return C(1.0, (1e-2, 1e2)) * Matern(np.ones(n), (0.05, 50), nu=2.5) + WhiteKernel(1e-2, (1e-6, 1.0))


def fit_gp(Z, y, restarts=10, seed=0):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # bound-hit ConvergenceWarnings are expected with n ~ 40-60
        return GPR(kernel(Z.shape[1]), normalize_y=True, n_restarts_optimizer=restarts, random_state=seed).fit(Z, y)


def loo(kind, rawX, y, restarts=10):
    """Leave-one-out: returns (y_hat, y_std) arrays; standardisation and hyperparameters are re-fitted inside every fold."""
    X, n = feat(kind, rawX), len(y)
    yh, ys = np.zeros(n), np.zeros(n)
    for i in range(n):
        tr = np.arange(n) != i
        mu, sd = X[tr].mean(0), X[tr].std(0)
        g = fit_gp((X[tr] - mu) / sd, y[tr], restarts)
        m, s = g.predict(((X[i] - mu) / sd)[None], return_std=True)
        yh[i], ys[i] = m[0], s[0]
    return yh, ys


def save(kind, name, rawX, y, path=None):
    X = feat(kind, rawX)
    mu, sd = X.mean(0), X.std(0)
    g = fit_gp((X - mu) / sd, y)
    out = dict(kind=kind, name=name, names=NAMES[kind], lo=BOX[kind][0], hi=BOX[kind][1], mu=mu.tolist(), sd=sd.tolist(), X=((X - mu) / sd).tolist(),
               y=list(map(float, y)), theta=g.kernel_.theta.tolist(), kernel=str(g.kernel_))
    path = pathlib.Path(path or ROOT / "data" / f"corr_{kind}_{name}.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def load(path):
    m = json.loads(pathlib.Path(path).read_text())
    Z, y = np.array(m["X"]), np.array(m["y"])
    g = GPR(kernel(Z.shape[1]).clone_with_theta(np.array(m["theta"])), normalize_y=True, optimizer=None).fit(Z, y)
    return m, g


def predict(path, values, tier1):
    """Tier 1 value -> corrected value with a log-normal 1-sigma band [lo, hi] and in_range (inside the CFD sweep box)."""
    m, g = load(path)
    r = raw(m["kind"], values)
    mean, s = g.predict(((feat(m["kind"], r)[0] - m["mu"]) / m["sd"])[None], return_std=True)
    f = lambda k: float(tier1 * 10 ** (mean[0] + k * s[0] / 1.0))  # y is log10, std in log10 units
    return dict(value=f(0), lo=f(-1), hi=f(1), y_hat=float(mean[0]), y_std=float(s[0]),
                in_range=bool(np.all(r >= m["lo"]) and np.all(r <= m["hi"])))
