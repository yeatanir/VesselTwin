"""MoS2 tube Tier 2 credibility runs: mesh convergence, Tier 1 vs CFD, Tier 0 vs CFD regimes, sweep for the surrogate.
usage: python scripts/tube_cfd_verification.py <mesh|agree|sweep>   (runs missing cases, 3 solvers at a time, cached by name)
       python scripts/tube_cfd_verification.py report               (assembles docs/tube_cfd_verification.json from cached cases)
Domain is trimmed to 8 cm past the substrate for BOTH Tier 1 and CFD (axial diffusion length D/u ~ 1 cm, so the outlet does not matter).
t_end = 3 residence times of the heated gas (checked per case by `drift_last_quarter`)."""
import json, math, pathlib, sys
import numpy as np
from scipy.stats import qmc
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent), str(pathlib.Path(__file__).resolve().parents[1])]
from tube_cfd import ROOT, run_many  # noqa: E402
from core import props  # noqa: E402
from core.params import validate  # noqa: E402
import vessels.cvd_tube as T  # noqa: E402

LEVELS = {"M1": dict(cells_per_cm=1.0, n_cross=8), "M2": dict(cells_per_cm=2.0, n_cross=16), "M3": dict(cells_per_cm=4.0, n_cross=32)}
BASE = dict(src_refine=4.0, wall_grading=0.4, max_co=1.0)
SWEEP_MESH = LEVELS["M2"]  # same as the agreement runs (M2 is within ~2-4 % of M3 on the mesh study)
OUT = pathlib.Path(__file__).resolve().parents[1] / "docs" / "tube_cfd_verification.json"
MESH_PTS = {"default": {}, "boat650_flow200": {"T_boat_Mo_C": 650.0, "flow_sccm": 200.0},
            "hot850_flow50_sub8": {"T_furnace_C": 850.0, "T_boat_Mo_C": 750.0, "flow_sccm": 50.0, "x_substrate_cm": 8.0}}
AGREE_PTS = {"default": {}, "boat650": {"T_boat_Mo_C": 650.0}, "boat750": {"T_boat_Mo_C": 750.0}, "boat800": {"T_boat_Mo_C": 800.0},
             "flow50": {"flow_sccm": 50.0}, "flow200": {"flow_sccm": 200.0}, "flow400": {"flow_sccm": 400.0},
             "sub6": {"x_substrate_cm": 6.0}, "sub20": {"x_substrate_cm": 20.0}, "furn700": {"T_furnace_C": 700.0}, "furn850": {"T_furnace_C": 850.0},
             "boatS150": {"T_boat_S_C": 150.0}}


def trim(v):
    v = dict(v)
    p = validate(T.DEFS, v)
    v["L_tube_cm"] = max(20.0, p["x_MoO3_cm"] + p["x_substrate_cm"] + p["substrate_length_cm"] + 8.0)
    return v


def t_end(v):
    p = validate(T.DEFS, v)
    x = np.linspace(0, p["L_tube_cm"] / 100, 300)
    Q0 = 101325 * p["flow_sccm"] * 1e-6 / 60 / (props.R * 273.15) * props.R / p["pressure_Pa"]  # m3/s per K of gas T
    res = np.trapezoid(math.pi * (0.0254 * p["tube_id_in"]) ** 2 / 4 / (Q0 * T.twall(p, x)), x)
    return float(np.clip(3 * res, 60, 4000))


def case(v, mesh):
    v = trim(v)
    return v, {**mesh, **BASE, "t_end_s": round(t_end(v))}


def tier1(v):
    p = validate(T.DEFS, trim(v))
    s = T.solve(p)
    return dict(p_MoO3_Pa=s["species.MoO3_g.p_Pa"], p_S2_Pa=s["species.S2_g.p_Pa"], ratio_Mo_S=s["ratio_Mo_S"], ss_wallT=s["supersaturation_MoO3"],
                ss_gasT=s["supersaturation_MoO3_gasT"], T_gas_K=s["T_gas_K"], supply_mol_s=s["MoO3_supply_mol_s"], sub_frac=s["MoO3_to_substrate_frac"])


def lhs(n=40, seed=3):
    lo, hi = np.array([math.log(30), 600, 650, 0.5, 1.0]), np.array([math.log(1500), 800, 900, 2.5, 20.0])
    X = lo + qmc.LatinHypercube(d=5, seed=seed).random(n) * (hi - lo)
    return [{"flow_sccm": float(math.exp(x[0])), "T_boat_Mo_C": float(x[1]), "T_furnace_C": float(x[2]), "tube_id_in": float(x[3]), "x_substrate_cm": float(x[4])} for x in X]


def cfd_regime(r, theta_c=0.1, f_c=1 - math.exp(-1)):
    """CFD side, from the solution only. heat_limited: the gas at the substrate has closed < 90 % of the wall-inlet temperature gap.
    else transport_limited if >= 63 % (1 - 1/e, i.e. NTU >= 1) of the MoO3 released by the boat is taken up by walls before the substrate centre;
    else reaction_limited (supply-limited: the vapour passes the substrate barely depleted)."""
    th = (r["T_wall_K"] - r["T_gas_K"]) / (r["T_wall_K"] - (r["values"].get("T_ends_C", 25.0) + 273.15))
    fup = 1 - r["MoO3_at_substrate_mol_s"] / r["MoO3_released_mol_s"]
    return ("heat_limited" if th > theta_c else "transport_limited" if fup >= f_c else "reaction_limited"), th, fup


def cases_for(stage):
    if stage == "mesh":
        return {f"v5mesh_{pn}_{ln}": case(v, m) for pn, v in MESH_PTS.items() for ln, m in LEVELS.items()}
    if stage == "agree":
        return {f"v5agree_{n}": case(v, LEVELS["M2"]) for n, v in AGREE_PTS.items()}
    return {f"v5sweep_{i:02d}": case(v, SWEEP_MESH) for i, v in enumerate(lhs())}


def cached(name):
    f = ROOT / name / "result.json"
    return json.loads(f.read_text()) if f.exists() else None


def build_report():
    out = {"note": "OpenFOAM v2512 buoyantPimpleFoam + passive scalars, axisymmetric wedge; Tier 1 = vessels.cvd_tube.solve with current sourced constants",
           "mesh_levels": LEVELS, "mesh_common": BASE}
    key = ("p_MoO3_Pa", "ratio_Mo_S", "supersaturation_MoO3_wallT", "ss_gasT", "MoO3_released_mol_s", "T_gas_K")
    mesh = {}
    for pn in MESH_PTS:
        rs = {ln: cached(f"v5mesh_{pn}_{ln}") for ln in LEVELS}
        if not all(rs.values()): continue
        d = {ln: {k: r[k] for k in key} | {"drift": r["drift_last_quarter"]} for ln, r in rs.items()}
        d["change_M1_to_M2_pct"] = {k: 100 * (rs["M2"][k] / rs["M1"][k] - 1) for k in key}
        d["change_M2_to_M3_pct"] = {k: 100 * (rs["M3"][k] / rs["M2"][k] - 1) for k in key}
        d["pass_lt2pct_M2_to_M3"] = all(abs(v) < 2 for k, v in d["change_M2_to_M3_pct"].items() if k != "T_gas_K")
        mesh[pn] = d
    out["mesh"] = mesh
    ag = {}
    for n, v in AGREE_PTS.items():
        r = cached(f"v5agree_{n}")
        if not r: continue
        t1 = tier1(v)
        c = {"p_MoO3_Pa": r["p_MoO3_Pa"], "p_S2_Pa": r["p_S2_Pa"], "ratio_Mo_S": r["ratio_Mo_S"], "ss_wallT": r["supersaturation_MoO3_wallT"],
             "ss_gasT": r["ss_gasT"], "T_gas_K": r["T_gas_K"], "supply_mol_s": r["MoO3_released_mol_s"]}
        ag[n] = {"values": v, "tier1": t1, "cfd": c, "cfd_over_tier1": {k: c[k] / t1[k] for k in c}, "drift": r["drift_last_quarter"],
                 "frac_released_taken_before_substrate_cfd": 1 - r["MoO3_at_substrate_mol_s"] / r["MoO3_released_mol_s"], "tier1_sub_frac": t1["sub_frac"]}
    out["agreement"] = ag
    if ag:
        out["agreement_summary"] = {k: {"median": float(np.median([a["cfd_over_tier1"][k] for a in ag.values()])),
                                        "min": min(a["cfd_over_tier1"][k] for a in ag.values()), "max": max(a["cfd_over_tier1"][k] for a in ag.values())}
                                    for k in ("p_MoO3_Pa", "p_S2_Pa", "ratio_Mo_S", "ss_wallT", "ss_gasT", "T_gas_K", "supply_mol_s")}
    rows = []
    for i, v in enumerate(lhs()):
        r = cached(f"v5sweep_{i:02d}")
        if not r: continue
        reg, th, fup = cfd_regime(r)
        t0 = T.tier0(validate(T.DEFS, trim(v)))[0].value
        rows.append({"id": f"v5sweep_{i:02d}", "values": v, "ok": r["drift_last_quarter"] < 0.02, "drift": r["drift_last_quarter"], "ratio_Mo_S": r["ratio_Mo_S"],
                     "supersaturation_MoO3_wallT": r["supersaturation_MoO3_wallT"], "ss_gasT": r["ss_gasT"], "p_MoO3_Pa": r["p_MoO3_Pa"], "p_S2_Pa": r["p_S2_Pa"],
                     "theta_gas": th, "frac_upstream_uptake": fup, "ss_wall": r["supersaturation_MoO3_wallT"], "regime_cfd": reg, "regime_tier0": t0})
    out["sweep"] = rows
    if rows:
        ok = [r for r in rows if r["ok"]]
        dis = [r for r in ok if r["regime_cfd"] != r["regime_tier0"]]
        sens = {}
        for fc in (0.5, 1 - math.exp(-1), 0.8):
            sens[f"f_c={fc:.2f}"] = float(np.mean([(("transport_limited" if r["frac_upstream_uptake"] >= fc else "reaction_limited") == r["regime_tier0"]) for r in ok]))
        out["regime"] = {"definition": cfd_regime.__doc__, "n_cases": len(ok), "agreement": 1 - len(dis) / len(ok),
                         "counts_cfd": {k: sum(r["regime_cfd"] == k for r in ok) for k in ("heat_limited", "transport_limited", "reaction_limited")},
                         "counts_tier0": {k: sum(r["regime_tier0"] == k for r in ok) for k in ("heat_limited", "transport_limited", "reaction_limited")},
                         "agreement_vs_f_threshold": sens, "disagreements": [{k: r[k] for k in ("id", "values", "regime_cfd", "regime_tier0", "frac_upstream_uptake", "theta_gas")} for r in dis]}
        try:
            from surrogate import tube as ST
            sweep_json = pathlib.Path(OUT).with_suffix(".sweep.tmp")
            sweep_json.write_text(json.dumps({"sweep": rows}))
            m = ST.fit(sweep_json)
            sweep_json.unlink()
            out["surrogate"] = {t: m["targets"][t]["heldout"] for t in ST.TARGETS} | {"plan_target": "within 5 % of the solver", "model": "surrogate/data/tube_gp.json"}
        except Exception as e:  # report rather than hide
            out["surrogate"] = {"error": repr(e)}
    out["constants_basis"] = ("vessels.cvd_tube defaults at run time: MoO3.psat_model=smolik_hsc (P_ref 53.3 Pa at 1000 K), (MoO3)3 vapour, literature S8/S2 basis; "
                              "CFD cases take the same values dict. Earlier mesh/agreement runs with the Simnad-OCR 1.2 Pa basis (prefixes v2-v4) are NOT used here.")
    out["findings"] = [
        "Boat source: mixed BC is the Robin law flux = h (ref - Y_wall) with the exact wall-cell centroid distance; boat release still changes +2..5 % per refinement (first order, ring-edge singularity), so the <2 % target is NOT met.",
        "CFD boat release is a median 2.9x Tier 1 supply and CFD p(S2) 6.5x Tier 1: the axisymmetric wedge makes each boat a full-circumference ring, Tier 1 a disk (boat_Sh_model=tube changes Tier 1 by only ~9 %). Geometry, not the BC.",
        "Tier 1 closure pointers: boat transfer (disk vs ring) sets supply and Mo:S; wall-uptake between boat and substrate (Sherwood/NTU, uniform 3.66, no entrance effect) sets the position trend (substrate 6 cm: CFD/T1 p 2.9, 20 cm: 0.008); gas-T lag is fine (T_gas CFD/T1 0.98-1.0).",
        "CFD fixes made this session: substrate strip used substrate_width_cm (now substrate_length_cm); substrate was a perfect sink (now saturation sink like the wall); oligomer/S-atom species basis; momentumPredictor off (yes gave a spurious radial vortex train); refined cells on boats, substrate and the stretch between; GAMG.",
        "Regime: CFD classes defined in cfd_regime(); no case is heat_limited in either tier; every disagreement is Tier 0 transport_limited (Da>=1) vs CFD reaction_limited (walls between boat and substrate are hotter than the boat so they take up little).",
        "Surrogate: 30 train / 10 held-out GP on log outputs over a box where outputs span 5-25 orders of magnitude; misses the 5 % target by far (see surrogate); it is no better than Tier 1 itself (CFD/Tier1 log-std 1.3)."]
    OUT.write_text(json.dumps(out, indent=1))
    print("wrote", OUT)


if __name__ == "__main__":
    st = sys.argv[1]
    if st == "report":
        build_report()
        raise SystemExit(0)
    res = run_many(cases_for(st))
    for k, r in res.items(): print(k, {a: (round(b, 5) if isinstance(b, float) else b) for a, b in r.items() if a in ("p_MoO3_Pa", "ratio_Mo_S", "ss_gasT", "wall_s", "failed", "drift_last_quarter")})
