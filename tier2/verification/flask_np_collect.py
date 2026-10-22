"""Collect Np from the steady flask mesh-study cases (flask_np_run.sh), run the field post-processing needed for the dissipation cross-check,
compute GCI triplets and write docs/flask_closure_np.json rows. usage (inside the OpenFOAM shell): python flask_np_collect.py <case_root> <out_rows.json>"""
import json, math, pathlib, subprocess, sys, os
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import numpy as np
from tier2.flask import analyse
from tier2.verification.gci import gci

root, outp = pathlib.Path(sys.argv[1]), sys.argv[2]
res = {}
for d in sorted(p for p in root.glob("w*_c*") if p.is_dir()):
    if not (d / "run.pid").read_text().count("done"): continue
    t = int(json.loads((d / "tier2_case.json").read_text())["t_simple"])
    env = {**os.environ, "PWD": str(d)}
    if not (d / str(t) / "grad(U)").exists():
        for fn in ("writeCellVolumes", "writeCellCentres", "grad(U)"):
            subprocess.run(["postProcess", "-func", fn, "-latestTime"], cwd=d, env=env, capture_output=True)
    a = analyse(d)
    mom = [ln for ln in (d / "postProcessing/forces/0/moment.dat").read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    c = json.loads((d / "tier2_case.json").read_text())
    Mz = [abs(float(ln.replace("(", " ").replace(")", " ").split()[3])) for ln in mom]
    N3d5 = c["N"] ** 3 * c["d"] ** 5
    npt = [m * c["omega"] / N3d5 for m in Mz]
    res[d.name] = dict(Re=a["Re"], n_cells=a["n_cells"], Np_torque=a["Np_torque"], Np_dissip=a["Np_dissip"], iter_drift_last100=abs(npt[-1] / npt[-11] - 1) if len(npt) > 11 else None,
                       cells_per_cm=float(d.name.split("_c")[1]), rpm=int(d.name[1:4]), Np_tier1=c["tier1"]["Np"])
rows = []
for rpm in (400, 800):
    for trip in ((13.5, 9, 6), (9, 6, 4)):
        keys = [f"w{rpm}_c{c:g}" for c in trip]
        if not all(k in res for k in keys): continue
        n = [res[k]["n_cells"] for k in keys]
        r1, r2 = (n[0] / n[1]) ** (1 / 3), (n[1] / n[2]) ** (1 / 3)
        r = (r1 + r2) / 2
        for q in ("Np_torque", "Np_dissip"):
            f1, f2, f3 = (res[k][q] for k in keys)
            g = gci(f1, f2, f3, r, p_formal=2.0)
            if abs(r1 - r2) / r > 0.10: g["flags"].append(f"refinement ratios differ ({r1:.2f}, {r2:.2f})")
            rows.append(dict(vessel="flask", case=f"water_{rpm}rpm_cells_per_cm_{trip[0]:g}-{trip[1]:g}-{trip[2]:g}", quantity=q, levels=[f3, f2, f1], n_cells=n[::-1], r=r, Re=res[keys[0]]["Re"],
                             iter_drift_last100=[res[k]["iter_drift_last100"] for k in keys], **g))
json.dump(rows, open(outp, "w"), indent=1)
json.dump(res, open(pathlib.Path(outp).with_name("flask_np_raw.json"), "w"), indent=1)
for r in rows: print(r["case"], r["quantity"], [round(x, 4) for x in r["levels"]], "p", r["p_obs"], "GCI %.1f%%" % (100 * r["gci_fine"]), r["flags"])
