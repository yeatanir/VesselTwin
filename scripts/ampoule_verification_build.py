"""Assemble docs/ampoule_cfd_verification.json from sweep/mesh outputs of ampoule_cfd_sweep.py and fit the surrogate.
usage: python scripts/ampoule_verification_build.py <scratch_dir>  (design.json, out?.json, mout_*.json)"""
import glob, json, math, pathlib, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
S = pathlib.Path(sys.argv[1])
load = lambda pat: {x["id"]: x for f in sorted(glob.glob(str(S / pat))) for x in json.load(open(f))}
res, mesh = load("out?.json"), load("mout_*.json")
rows = []
for j in json.load(open(S / "design.json")):
    r = res[j["id"]]
    rows.append(dict(id=j["id"], values=j["values"], tier0_f=j["tier0_f"], tier0_regime=j["tier0_regime"], f_cfd=r["f_cfd"], ok=r["ok"],
                     drift_last_quarter=r["drift_last_quarter"], osc_last_quarter=r["osc_last_quarter"], t_end_s=r["t_end_s"], wall_s=r["wall_s"]))
reg = {}
for th in (1.1, 1.2):
    bad = [dict(id=r["id"], D_mm=r["values"]["D_mm"], tilt_deg=r["values"]["tilt_deg"], tier0_f=round(r["tier0_f"], 3), f_cfd=round(r["f_cfd"], 3))
           for r in rows if (r["tier0_regime"] == "convection_assisted") != (r["f_cfd"] > th)]
    reg[f"threshold_{th}"] = dict(agreement=1 - len(bad) / len(rows), n=len(rows), n_disagree=len(bad), disagreeing=bad)
reg["n_tier0_convection"] = sum(r["tier0_regime"] == "convection_assisted" for r in rows)
reg["n_cfd_convection_1.2"] = sum(r["f_cfd"] > 1.2 for r in rows)
reg["note"] = "Tier 0 = vessels.ampoule.tier0 (calibrated f >= conv_threshold 1.1); CFD class: f_CFD = rate_CFD/rate_diffusion-only > threshold. Target >= 90%."
pts = {}
for r in mesh.values():
    pts.setdefault(r["id"].split("_")[1], {})[int(r["id"][-1])] = r
mp = {}
for k, lv in pts.items():
    if sorted(lv) != [0, 1, 2]:  # unfinished fine level: report what exists (no Richardson/GCI)
        ks = sorted(lv)
        mp[k] = dict(values={a: lv[0]["values"][a] for a in ("D_mm", "tilt_deg")}, levels_done=ks, f_cfd=[lv[i]["f_cfd"] for i in ks],
                     change_pct=[100 * (lv[b]["f_cfd"] - lv[a]["f_cfd"]) / lv[b]["f_cfd"] for a, b in zip(ks, ks[1:])], status="incomplete: fine level not finished")
        continue
    f1, f2, f3 = (lv[i]["f_cfd"] for i in range(3))
    e21, e32 = f2 - f1, f3 - f2
    p = math.log(abs(e21 / e32)) / math.log(2) if e21 * e32 > 0 and e32 else None  # refinement ratio 2
    p_use = p if p and 0.5 < p < 4 else 1.0  # ponytail: fall back to first order (conservative) when not monotone/sane
    ext = f3 + e32 / (2**p_use - 1)
    mp[k] = dict(values={a: lv[0]["values"][a] for a in ("D_mm", "tilt_deg")}, mesh=[(lv[i]["values"]["cells_per_cm"], lv[i]["values"]["n_cross"]) for i in range(3)],
                 f_cfd=[f1, f2, f3], change_coarse_to_medium_pct=100 * e21 / f2, change_medium_to_fine_pct=100 * e32 / f3, observed_order=p, order_used=p_use,
                 f_richardson=ext, gci_fine_pct=100 * 1.25 * abs(e32 / f3) / (2**p_use - 1), fine_vs_extrapolated_pct=100 * (f3 - ext) / ext,
                 drift_last_quarter=[lv[i]["drift_last_quarter"] for i in range(3)], wall_s=[lv[i]["wall_s"] for i in range(3)])
out = dict(meta=dict(generated="2026-10-20", f_cfd="CFD sink-flux rate / dilute Fick diffusion-only rate (Tier 1 J, same as docs/ampoule_convection_scan.json)",
                     sweep="60-point Latin hypercube (seed 7): D 6-45 mm, L 8-20 cm, dT=T_source-T_sink 10-150 K (T_sink 800 C), tilt -90..90, agent 0.5-15 mg/cm3; other params default; mesh 4 cells/cm x 10 across; t_end = 4 L^2/D_C; laminar",
                     solver="tier2/foam/ampouleBoussinesqFoam, OpenFOAM v2512; scripts/ampoule_sweep_design.py, ampoule_cfd_sweep.py, ampoule_verification_build.py"),
           regime_agreement=reg, mesh_convergence=mp, sweep=rows)
(ROOT / "docs" / "ampoule_cfd_verification.json").write_text(json.dumps(out, indent=1))
from surrogate.ampoule import fit
m = fit(ROOT / "docs" / "ampoule_cfd_verification.json")
out["surrogate"] = dict(kernel=m["kernel"], **m["heldout"], test_ids=m["test_ids"], target="held-out error within 5% of solver", model="surrogate/data/ampoule_gp.json")
(ROOT / "docs" / "ampoule_cfd_verification.json").write_text(json.dumps(out, indent=1))
print(json.dumps({k: v for k, v in out.items() if k != "sweep"}, indent=1)[:6000])
