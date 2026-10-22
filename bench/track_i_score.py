"""Track I scoring, exactly as pre-registered in docs/prereg/track-i.md. python -m bench.track_i_score [--write]
Reuses bench.track_a_score (same items, MC, call rules, tables). All items are development data. Run once after the pre-registration commit."""
import argparse, json, os
from bench import track_a_score as A
from vessels.cvd_tube import thermo, wulff

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track_i")
LIQ = {"MoO3.psat_model": "smolik_liquid_cc"}
SHAPE_CFG = dict(A.CFG)
SHAPE_CFG |= {k + "L": v | LIQ for k, v in A.CFG.items()}
SHAPE_CFG |= {"M3_momeni_eq_kT_PRIMARY": {"edge_model": "momeni_eq", "momeni_mapping": "kT"},
              "M4_momeni_eq_bridge": {"edge_model": "momeni_eq", "momeni_mapping": "bridge"}}


def sens(extra):
    """Run the Track A sensitivity items with `extra` merged into every item's base overrides (and the s11 shape call)."""
    saved = dict(A.ITEMS)
    try:
        for sid, it in saved.items():
            A.ITEMS[sid] = it[:4] + (it[4] | extra,) + it[5:]
        with thermo.with_liq_sigma(extra):
            rows = {}
            for sid in A.ITEMS:
                rows[sid] = A.shape_item(sid, extra) if A.ITEMS[sid][5] == "shape" else A.sensitivity_item(sid)
    finally:
        A.ITEMS.clear(); A.ITEMS.update(saved)
    blind = {x["id"]: x["predicted_direction"] for x in json.load(open(f"{A.HERE}/sensitivity/blind_dev_s01_s14.json")) + json.load(open(f"{A.HERE}/sensitivity/blind_heldout_jian.json"))}
    for sid, r in rows.items():
        r["blind"], r["always_increase"] = blind[sid], "increase"
        r["set"] = "dev (j1-j3: formerly held-out, now seen)" if sid.startswith("j") else "dev"
    return rows


def tables(rows):
    prim = [r for r in rows.values() if r["id"].startswith("s") and r["class"] == "primary"]
    o8 = [rows[s] for s in A.ORIG8]
    j = [rows[s] for s in ("j1", "j2", "j3")]
    allp = prim + j
    t = {name: {k: A.table(sel, k) for k in ("call", "blind", "always_increase")} for name, sel in
         (("T1_dev_primary_s", prim), ("T2_original8", o8), ("T4_j1_j3", j), ("T5_all_primary_incl_j", allp))}
    t["T3_secondary"] = [{"id": s, "call": rows[s]["call"], "correct": rows[s]["call"] == "non_monotonic"} for s in ("s05", "s06", "s07")]
    return t


def shape_run(cfgs):
    out = {}
    for name, cfg in cfgs.items():
        with thermo.with_liq_sigma(cfg):
            out[name] = A.run_shape({name: cfg})[name]
    return out


ADD_CFG = {"M0_default_synthetic": {}, "M1_MACE_kink": A.CFG["M1_MACE_kink"], "M2_A1_dft_rosen_Mo_MACE_S": A.CFG["M2_A1_dft_rosen_Mo_MACE_S"],
           "M3_momeni_v1_kT": {"edge_model": "momeni_eq_v1", "momeni_mapping": "kT"},
           "M5_momeni_v2_kT": {"edge_model": "momeni_eq", "momeni_mapping": "kT"},
           "M6_momeni_v2_bridge": {"edge_model": "momeni_eq", "momeni_mapping": "bridge"}}
D1_SETUP = {"T_boat_Mo_C": 800.0, "T_furnace_C": 800.0, "T_boat_S_C": 130.0, "tube_id_in": 1.575, "flow_sccm": 100.0, "pressure_Pa": 710 * 133.322,
            "duration_min": 15.0, "m_MoO3_mg": 2.0, "m_S_mg": 200.0, "x_MoO3_cm": 50.0, "x_S_boat_cm": 35.5, "x_substrate_cm": 0.5}


def check_d1(cfg, n_mc=60):
    """Addendum B, D1: paired MC change of |s| from 0.5 to 1.5 cm downstream of the MoO3 boat (Momeni 2018 own experiment)."""
    import numpy as np
    from core import params as P, uq
    v = P.validate(wulff.DEFS, D1_SETUP | cfg)
    rng = np.random.default_rng(0)
    xrel = np.array([0.5, 1.5])
    ds = []
    with wulff.with_sigma(cfg):
        for k in range(n_mc):
            vv = v if k == 0 else uq.sample(wulff.DEFS, v, rng)
            try:
                s = wulff._curve(vv, xrel)
            except (ValueError, FloatingPointError):
                continue
            ds.append(abs(s[1]) - abs(s[0]))
    ds = np.array(ds); p05, p50, p95 = (float(np.percentile(ds, q)) for q in (5, 50, 95))
    call = "more_triangular" if p05 > 0.05 else "less_triangular" if p95 < -0.05 else "no_change" if max(abs(p05), abs(p95)) < 0.05 else "uncertain"
    s0 = wulff._curve(v, xrel)
    return {"call": call, "correct": call == "more_triangular", "d_abs_s_p05_p50_p95": [p05, p50, p95], "s_nominal": [float(s0[0]), float(s0[1])], "n": len(ds)}


def check_d2(cfg):
    """Addendum B, D2: s(pS2 = 1000 Pa) - s(10 Pa) at pMoO3 = 10 Pa, T = 1073 K; Wang 2014 expects a decrease."""
    from core import params as P
    v = P.defaults(wulff.DEFS) | cfg
    s = [wulff.shape_at(v, (10.0, pS), 1073.0)["shape_index"] for pS in (10.0, 1000.0)]
    d = s[1] - s[0]
    call = "decrease" if d < -0.05 else "increase" if d > 0.05 else "no_change"
    return {"call": call, "correct": call == "decrease", "s_at_pS10_pS1000": s}


def addendum(write):
    res = {"D1": {}, "D2": {}}
    for n, c in ADD_CFG.items():
        res["D1"][n], res["D2"][n] = check_d1(c), check_d2(c)
        print(n, "D1", res["D1"][n], "D2", res["D2"][n])
    new = {k: ADD_CFG[k] for k in ("M3_momeni_v1_kT", "M5_momeni_v2_kT", "M6_momeni_v2_bridge")}
    res["shape_benchmark"] = shape_run({k: new[k] for k in ("M5_momeni_v2_kT", "M6_momeni_v2_bridge")})
    res["s11"] = {k: A.shape_item("s11", new[k])["call"] for k in new}
    col = {}
    for n in ("M5_momeni_v2_kT", "M6_momeni_v2_bridge"): col |= A.collapse({n: new[n]})
    res["shape_map_collapse"] = col
    for n, s_ in res["shape_benchmark"].items(): print(n, json.dumps(s_["scores"], default=float))
    print(res["s11"], json.dumps(col, default=float))
    if write:
        os.makedirs(OUT, exist_ok=True)
        json.dump(res, open(f"{OUT}/results_addendum.json", "w"), indent=1, default=float)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); ap.add_argument("--addendum", action="store_true"); a = ap.parse_args()
    if a.addendum:
        return addendum(a.write)
    res = {"sens_before": None, "sens_after": None}
    for key, extra in (("sens_before", {}), ("sens_after", LIQ)):
        rows = sens(extra)
        res[key] = {"items": rows, "tables": tables(rows)}
        print(key, json.dumps(res[key]["tables"], default=float))
        for r in rows.values(): print(key, r["id"], r["label"], r["call"], r.get("calls_by_i"), "zero" if r["zero_flux"] else "", r.get("diag_i1"))
    res["s11_by_config"] = {}
    for n, c in SHAPE_CFG.items():
        with thermo.with_liq_sigma(c):
            res["s11_by_config"][n] = A.shape_item("s11", c)["call"]
    res["shape_benchmark"] = shape_run(SHAPE_CFG)
    for n, s in res["shape_benchmark"].items(): print(n, json.dumps(s["scores"], default=float))
    col = {}
    for n, c in SHAPE_CFG.items():
        with thermo.with_liq_sigma(c):
            col |= A.collapse({n: c})
    res["shape_map_collapse"] = col
    print(json.dumps(col, default=float))
    if a.write:
        os.makedirs(OUT, exist_ok=True)
        json.dump(res, open(f"{OUT}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
