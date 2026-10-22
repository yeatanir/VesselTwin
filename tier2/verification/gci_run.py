"""Write tier2/verification/gci.json: Roache GCI (tier2/verification/gci.py) for every three-mesh case.
usage: python tier2/verification/gci_run.py [flask_results.json]   (flask rows from flask_np_collect.py, optional)"""
import json, math, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tier2.verification.gci import gci

OUT = pathlib.Path(__file__).with_name("gci.json")
rows = []
# ampoule: levels L0 (3 cells/cm x 8), L1 (6 x 16), L2 (12 x 32); r = 2
am = {r["id"]: r for r in json.load(open(ROOT / "tier2/verification/data/ampoule_mesh_study.json"))}
for pt in ("diffusion", "weak", "tilted", "strong"):
    L = [am[f"m_{pt}_L{i}"] for i in (0, 1, 2)]
    uns = L[2]["osc_last_quarter"] > 0.1 or L[2]["drift_last_quarter"] > 0.05
    g = gci(L[2]["f_cfd"], L[1]["f_cfd"], L[0]["f_cfd"], 2.0, unsteady=uns)
    rows.append(dict(vessel="ampoule", case=pt, values={k: L[0]["values"][k] for k in ("D_mm", "tilt_deg")}, quantity="f_cfd", levels=[x["f_cfd"] for x in L],
                     mesh="L0 3/cm x 8, L1 6 x 16, L2 12 x 32 (axial cells per cm x cells across)", r=2.0, **g,
                     osc_last_quarter=L[2]["osc_last_quarter"], drift_last_quarter=L[2]["drift_last_quarter"]))
# tube: M1 1/cm x 8, M2 2 x 16, M3 4 x 32; r = 2 (stored in docs/tube_cfd_verification.json)
tb = json.load(open(ROOT / "docs/tube_cfd_verification.json"))["mesh"]
for pt, d in tb.items():
    for q in ("p_MoO3_Pa", "ratio_Mo_S", "supersaturation_MoO3_wallT", "MoO3_released_mol_s"):
        f3, f2, f1 = (d[k][q] for k in ("M1", "M2", "M3"))
        g = gci(f1, f2, f3, 2.0, unsteady=d["M3"]["drift"] > 0.05)
        rows.append(dict(vessel="cvd_tube", case=pt, quantity=q, levels=[f3, f2, f1], mesh="M1 1/cm x 8, M2 2 x 16, M3 4 x 32", r=2.0, **g))
if len(sys.argv) > 1:
    rows += json.load(open(sys.argv[1]))
json.dump(dict(method="Roache GCI, Fs 1.25 (3 grids) / 3.0 fallback; see docs/prereg/track-b.md B4; levels listed coarse to fine; gci_fine and change are fractions", rows=rows), open(OUT, "w"), indent=1)
for r in rows:
    print(r["vessel"], r["case"], r["quantity"], "p=%s" % (None if r["p_obs"] is None else round(r["p_obs"], 2)), "GCI=%.1f%%" % (100 * r["gci_fine"]),
          "chg=%.1f%%" % (100 * r["change_medium_to_fine"]), r["flags"])
