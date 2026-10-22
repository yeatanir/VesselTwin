"""Regenerate data/viz_cache/*.npz (2D field maps) from STORED OpenFOAM results. Never runs a solver.

Usage (needs the OpenFOAM v2512 volume mounted; only foamToVTK is run, once per case):
    python scripts/export_fields.py --root <dir holding the case dirs> [--only tube_default ...] [--work <tmp dir>]
Default --root is the Track B scratchpad that holds the stored cases (see CASES below for the relative paths).
Each case is COPIED (constant/, system/, latest time dir) to a work dir so the original case is untouched, then
`foamToVTK -latestTime` -> pyvista -> a plane (wedge cases: the wedge itself with y as radius; 3D cases: a slice) ->
linear interpolation onto a regular grid -> data/viz_cache/<name>.npz (float32, compressed, < 1 MB each).
npz keys: x, y (1D grid axes, m), one 2D array per field (ny, nx; NaN outside the fluid), u, v (in-plane velocity, m/s),
meta (JSON string: case, vessel, n_cells, solver, time_dir, date_made, plane, fields{name:{label,unit,log}}, params, note).
"""
import argparse, json, os, pathlib, re, shutil, subprocess, sys, datetime
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "viz_cache"
DEFAULT_ROOT = "/private/tmp/claude-501/-Users-yeatanir-OSI-Hackathon/9eda40b9-b622-4dd7-b227-9e90bef27ef6/scratchpad"
BASHRC = "/Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc"
NX, NY = 360, 72
F = lambda label, unit, log=False: dict(label=label, unit=unit, log=log)
# name -> (vessel, case dir under --root, plane kind, plane description, fields {array: spec})
CASES = {
    "tube_default": ("cvd_tube", "tube2/cases/v5agree_default", "wedge", "axisymmetric 5-degree wedge, x = axis, y = radius (radial axis stretched in plots)",
                     {"T": F("Temperature", "K"), "speed": F("Velocity magnitude", "m/s"), "Y_MoO3": F("MoO3 mass fraction", "-"), "Y_S2": F("S2 mass fraction", "-")}),
    "ampoule_tilt0_D15": ("ampoule", "default_f", "z0", "half square duct, symmetry plane (x = axis, y = vertical)",
                          {"T": F("Temperature", "K"), "speed": F("Velocity magnitude", "m/s"), "Y_AIn": F("Agent (AIn) fraction", "-")}),
    "ampoule_tilt30_D40": ("ampoule", "tilt30_f", "z0", "half square duct, symmetry plane (x = axis, y across)",
                           {"T": F("Temperature", "K"), "speed": F("Velocity magnitude", "m/s"), "Y_AIn": F("Agent (AIn) fraction", "-")}),
    "ampoule_tilt90_D40": ("ampoule", "tilt90_f", "wedge", "axisymmetric 5-degree wedge, x = axis, y = radius",
                           {"T": F("Temperature", "K"), "speed": F("Velocity magnitude", "m/s"), "Y_AIn": F("Agent (AIn) fraction", "-")}),
    "flask_w400_vertical": ("flask", "trackB/flask/w400_c9", "y0", "vertical slice through the axis (y = 0), x horizontal, z up",
                            {"speed": F("Velocity magnitude", "m/s"), "epsilon": F("Dissipation rate epsilon", "m2/s3", True), "nut": F("Turbulent viscosity", "m2/s", True)}),
    "flask_w400_horizontal": ("flask", "trackB/flask/w400_c9", "zmid", "horizontal slice at mid liquid height (x, y)",
                              {"speed": F("Velocity magnitude", "m/s"), "epsilon": F("Dissipation rate epsilon", "m2/s3", True), "nut": F("Turbulent viscosity", "m2/s", True)}),
}


def _foam_to_vtk(case: pathlib.Path, work: pathlib.Path):
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    times = sorted((d for d in case.iterdir() if d.is_dir() and re.fullmatch(r"[0-9.eE+-]+", d.name) and d.name != "0"), key=lambda d: float(d.name))
    last = times[-1]
    for n in ("constant", "system"):
        shutil.copytree(case / n, work / n)
    shutil.copytree(last, work / last.name)
    r = subprocess.run(["bash", "-c", f"source {BASHRC} >/dev/null 2>&1; foamToVTK -latestTime"], cwd=work, capture_output=True, text=True, timeout=300)
    vtu = list(work.glob("VTK/*/internal.vtu"))
    if not vtu:
        raise RuntimeError("foamToVTK failed: " + r.stdout[-400:] + r.stderr[-400:])
    solver = re.search(r"application\s+(\w+)", (case / "system" / "controlDict").read_text())
    return vtu[0], last, (solver.group(1) if solver else "?")


def _plane(g, kind):
    """-> (px, py, point/cell data dict) in the plane."""
    if kind == "wedge":
        c = g.cell_centers().points
        return c[:, 0], c[:, 1], {k: np.asarray(g.cell_data[k]) for k in g.cell_data}
    if kind == "z0":  # first cell layer next to the symmetry plane z = 0
        c = g.cell_centers().points
        z0 = np.unique(np.round(c[:, 2], 7))[0]
        m = np.isclose(c[:, 2], z0, atol=1e-6)
        return c[m, 0], c[m, 1], {k: np.asarray(g.cell_data[k])[m] for k in g.cell_data}
    if kind in ("y0", "zmid"):
        b = g.bounds
        s = g.slice(normal="y", origin=(0, 1e-9, 0)) if kind == "y0" else g.slice(normal="z", origin=(0, 0, 0.5 * (b[4] + b[5])))
        c = s.cell_centers().points
        data = {k: np.asarray(s.cell_data[k]) for k in s.cell_data}
        return (c[:, 0], c[:, 2], data) if kind == "y0" else (c[:, 0], c[:, 1], data)
    raise ValueError(kind)


def _comp(U, kind):  # in-plane velocity components
    return (U[:, 0], U[:, 2]) if kind == "y0" else (U[:, 0], U[:, 1])


def _grid(px, py, vals, gx, gy, mask_nn):
    from scipy.interpolate import griddata
    from scipy.spatial import cKDTree
    sx, sy = np.ptp(px) or 1.0, np.ptp(py) or 1.0
    P = np.c_[(px - px.min()) / sx, (py - py.min()) / sy]
    GX, GY = np.meshgrid(gx, gy)
    Q = np.c_[(GX.ravel() - px.min()) / sx, (GY.ravel() - py.min()) / sy]
    out = {}
    for k, v in vals.items():
        lin = griddata(P, v, Q, method="linear")
        near = griddata(P, v, Q, method="nearest")
        out[k] = np.where(np.isnan(lin), near, lin)
    if mask_nn:  # non-rectangular domain (flask): blank grid points far from any cell centre (physical distance)
        d, _ = cKDTree(np.c_[px, py]).query(np.c_[GX.ravel(), GY.ravel()])
        nn, _ = cKDTree(np.c_[px, py]).query(np.c_[px, py], k=2)
        bad = d > 3 * np.median(nn[:, 1])
        for k in out:
            out[k][bad] = np.nan
    return {k: v.reshape(GX.shape) for k, v in out.items()}


def export(name, root, work_root):
    import pyvista as pv
    vessel, rel, kind, plane, fields = CASES[name]
    case = pathlib.Path(root) / rel
    vtu, last, solver = _foam_to_vtk(case, pathlib.Path(work_root) / name)
    g = pv.read(str(vtu))
    px, py, data = _plane(g, kind)
    U = data["U"]
    u, v = _comp(U, kind)
    data["speed"] = np.linalg.norm(U, axis=1)
    data["u"], data["v"] = u, v
    gx, gy = np.linspace(px.min(), px.max(), NX), np.linspace(py.min(), py.max(), NY)
    grids = _grid(px, py, {k: np.asarray(data[k], float) for k in [*fields, "u", "v"]}, gx, gy, mask_nn=vessel == "flask")
    for k in grids:
        if fields.get(k, {}).get("log"):
            grids[k] = np.maximum(grids[k], 1e-30)
    tc = json.loads((case / "tier2_case.json").read_text())
    meta = dict(name=name, case=rel, vessel=vessel, n_cells=int(g.n_cells), solver=solver, time_dir=last.name, plane=plane, fields=fields,
                date_made=datetime.datetime.fromtimestamp(last.stat().st_mtime).strftime("%Y-%m-%d"),
                params=tc.get("values", {}), tier2=tc.get("tier2", {k: tc[k] for k in ("Re", "N", "d") if k in tc}),
                note="stored CFD result, not re-run")
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{name}.npz"
    np.savez_compressed(f, x=gx.astype("float32"), y=gy.astype("float32"), meta=json.dumps(meta, default=float),
                        **{k: v.astype("float32") for k, v in grids.items()})
    print(f"{name}: {g.n_cells} cells, t={last.name}, {f.stat().st_size / 1e3:.0f} kB")
    return f


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--work", default=str(pathlib.Path(DEFAULT_ROOT) / "hwork_export"))
    ap.add_argument("--only", nargs="*", default=list(CASES))
    a = ap.parse_args()
    for n in a.only:
        export(n, a.root, a.work)
