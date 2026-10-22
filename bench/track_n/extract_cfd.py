"""Read the STORED OpenFOAM tube cases (no solver run) -> bench/track_n/cfd_extract.json. Only `foamToVTK -latestTime` is run, once per case, on a COPY
(constant/, system/, latest time dir) in a scratch work dir, one case at a time. Same recipe as scripts/export_fields.py.
  python -m bench.track_n.extract_cfd [--root <dir with tube2/cases>] [--only v5agree_default ...]
Per case: axial columns (cell-volume weights within a column of the structured wedge mesh): T_centre (axis cell), T_area (area mean), T_mix (mixing cup,
rho u_x weighted, rho = p M / R T), u_mean (area mean u_x), u_centre, plus stations (MoO3 boat strip centre, release station, substrate centre), the wall
step profile actually imposed (cell-wise T_wall of the CFD), a settledness check from the probe file (relative T change over the last 20 % of time), and
the gravity vector from constant/g (zero: the stored CFD has NO buoyancy)."""
import argparse, json, pathlib, re, shutil, subprocess, sys
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
ROOT = "/private/tmp/claude-501/-Users-yeatanir-OSI-Hackathon/9eda40b9-b622-4dd7-b227-9e90bef27ef6/scratchpad"
BASHRC = "/Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc"
WORK = pathlib.Path(ROOT) / "n_extract_work"
AGREE = ["default", "boat650", "boat750", "boat800", "boatS150", "flow50", "flow200", "flow400", "sub6", "sub20", "furn700", "furn850"]
CASES = [f"v5agree_{a}" for a in AGREE] + [f"v5sweep_{i:02d}" for i in range(40)]


def _vtk(case, work):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    times = sorted((d for d in case.iterdir() if d.is_dir() and re.fullmatch(r"[0-9.eE+-]+", d.name) and d.name != "0"), key=lambda d: float(d.name))
    last = times[-1]
    for n in ("constant", "system"):
        shutil.copytree(case / n, work / n)
    shutil.copytree(last, work / last.name)
    r = subprocess.run(["bash", "-c", f"source {BASHRC} >/dev/null 2>&1; foamToVTK -latestTime"], cwd=work, capture_output=True, text=True, timeout=600)
    vtu = list(work.glob("VTK/*/internal.vtu"))
    if not vtu:
        raise RuntimeError("foamToVTK failed: " + r.stdout[-300:] + r.stderr[-300:])
    return vtu[0], last.name


def _settled(case):
    f = case / "postProcessing" / "probes" / "0" / "T"
    rows = []
    for ln in f.read_text().splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        v = [float(t) for t in ln.replace("(", " ").replace(")", " ").split()]
        rows.append(v)
    a = np.array(rows)
    t, T = a[:, 0], a[:, 1:]
    i0 = int(np.searchsorted(t, t[-1] * 0.8))
    return {"t_end": float(t[-1]), "max_abs_dT_last20pct_K": float(np.max(np.abs(T[-1] - T[i0]))), "n_probe_rows": int(len(t))}


def extract(name, root):
    import pyvista as pv
    from core import params as Pm, props
    from tier2 import openfoam as O
    from vessels import cvd_tube as tube
    from vessels.cvd_tube import wulff
    case = pathlib.Path(root) / "tube2" / "cases" / name
    tc = json.loads((case / "tier2_case.json").read_text())
    known = {d.name for d in wulff.DEFS}
    p = Pm.validate(wulff.DEFS, {k: v for k, v in tc["values"].items() if k in known})
    t2 = {d.name: tc["tier2"].get(d.name, d.default) for d in O.T2_DEFS}
    geo = O._tube_geo(p, t2)
    vtu, tname = _vtk(case, WORK / name)
    g = pv.read(str(vtu)).compute_cell_sizes(length=False, area=False, volume=True)
    c = g.cell_centers().points
    x, r, V = c[:, 0], np.hypot(c[:, 1], c[:, 2]), np.asarray(g.cell_data["Volume"])
    T, U, pr = np.asarray(g.cell_data["T"]), np.asarray(g.cell_data["U"]), np.asarray(g.cell_data["p"])
    M = props.mass(p["carrier"]) * 1e-3
    rho = pr * M / (8.314462618 * T)
    xk = np.round(x, 9)
    cols = np.unique(xk)
    out = {k: [] for k in ("x", "T_centre", "T_area", "T_mix", "u_mean", "u_centre", "T_min", "T_max")}
    for xx in cols:
        m = xk == xx
        w = V[m]
        ux = U[m, 0]
        out["x"].append(float(xx))
        out["T_centre"].append(float(T[m][np.argmin(r[m])]))
        out["T_area"].append(float((w * T[m]).sum() / w.sum()))
        out["T_mix"].append(float((rho[m] * ux * w * T[m]).sum() / (rho[m] * ux * w).sum()))
        out["u_mean"].append(float((w * ux).sum() / w.sum()))
        out["u_centre"].append(float(ux[np.argmin(r[m])]))
        out["T_min"].append(float(T[m].min())); out["T_max"].append(float(T[m].max()))
    # wall profile as imposed: per mesh segment cell centres
    segs, ns = geo["segs"], geo["ns"]
    xw, Tw, kinds = [], [], []
    for (k, x0, x1), n in zip(segs, ns):
        xcs = x0 + (np.arange(n) + 0.5) * (x1 - x0) / n
        tw = {"tube": tube.twall(p, xcs), "boatS": np.full(n, p["T_boat_S_C"] + 273.15), "boatMo": np.full(n, p["T_boat_Mo_C"] + 273.15),
              "substrate": tube.twall(p, xcs) + p["T_substrate_offset_K"]}[k]
        xw += xcs.tolist(); Tw += tw.tolist(); kinds += [k] * n
    bm = next((a, b) for k, a, b in segs if k == "boatMo")
    sub = next((a, b) for k, a, b in segs if k == "substrate")
    stations = {"boat_mid": 0.5 * sum(bm), "release": geo["xr"], "substrate_centre": geo["xs"], "substrate_x0": sub[0], "substrate_x1": sub[1]}
    gfile = (case / "constant" / "g").read_text()
    gv = re.search(r"value\s*\(([^)]*)\)", gfile).group(1)
    rec = {"name": name, "time_dir": tname, "values": {k: p[k] for k in ("tube_id_in", "L_tube_cm", "flow_sccm", "T_furnace_C", "T_ends_C", "T_boat_Mo_C", "T_boat_S_C",
                                                                          "x_MoO3_cm", "x_S_boat_cm", "x_substrate_cm", "substrate_length_cm", "carrier", "pressure_Pa",
                                                                          "L_hot_cm", "ramp_cm", "x_furnace_center_cm", "T_substrate_offset_K")},
           "stations": stations, "cols": {k: np.round(v, 5).tolist() for k, v in out.items()}, "wall_x": np.round(xw, 6).tolist(), "wall_T": np.round(Tw, 4).tolist(),
           "wall_kind": kinds, "settled": _settled(case), "gravity": gv, "values_full": {k: v for k, v in p.items() if not isinstance(v, (list, dict))}, "n_cells": int(g.n_cells), "mdot_check_kg_s": None}
    return rec


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--only", nargs="*", default=CASES)
    ap.add_argument("--out", default=str(HERE / "cfd_extract.json"))
    a = ap.parse_args()
    sys.path.insert(0, str(HERE.parents[1]))
    store = json.loads(pathlib.Path(a.out).read_text()) if pathlib.Path(a.out).exists() else {}
    for n in a.only:
        try:
            store[n] = extract(n, a.root)
            print(n, "ok", store[n]["n_cells"], store[n]["settled"]["max_abs_dT_last20pct_K"], flush=True)
        except Exception as e:  # keep going; the failure is recorded
            store[n] = {"name": n, "error": repr(e)[:300]}
            print(n, "FAILED", repr(e)[:200], flush=True)
        pathlib.Path(a.out).write_text(json.dumps(store))
