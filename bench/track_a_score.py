"""Track A scoring, exactly as pre-registered in docs/prereg/track-a.md. python -m bench.track_a_score [--write]
Sensitivity direction (Venables proxies, paired MC change, 3-way calls) + shape benchmark under configurations M0/M1/M2.
Run once after the pre-registration commit."""
import argparse, json, os
from collections import Counter
import numpy as np
from core import params as P, uq
from vessels.cvd_tube import wulff, growth

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/track_a"
TOL, NMC, NPTS, IS, ECORN = 0.05, 100, 5, (1, 2, 3), (0.0, 2.0)  # tol in ln units; E_eff corners eV (synthetic range 0-2 eV)
# id: (set, sweep param, lo, hi, base overrides, observable, label, class)   class: primary | secondary | shape
ITEMS = {
 "s01": ("dev", "flow_sccm", 10, 160, {}, "nucleation", "increase", "primary"),
 "s03": ("dev", "flow_sccm", 50, 300, {}, "domain", "decrease", "primary"),
 "s04": ("dev", "flow_sccm", 50, 150, {}, "coverage", "increase", "primary"),
 "s05": ("dev", "m_MoO3_mg", 10, 30, {"duration_min": 5, "m_S_mg": 200}, "layers", "class_change", "secondary"),
 "s06": ("dev", "m_S_mg", 100, 400, {"duration_min": 5, "m_MoO3_mg": 15}, "domain", "class_change", "secondary"),
 "s07": ("dev", "T_furnace_C", 650, 800, {}, "coverage", "class_change", "secondary"),
 "s08": ("dev", "gap_mm", 2, 10, {}, "layers", "decrease", "primary"),
 "s09": ("dev", "T_boat_Mo_C", 200, 400, {}, "nucleation", "increase", "primary"),
 "s10": ("dev", "T_furnace_C", 700, 850, {}, "nucleation", "decrease", "primary"),
 "s11": ("dev", "T_boat_S_C", 180, 300, {}, "shape", "class_change", "primary"),
 "s13": ("dev", "T_furnace_C", 750, 850, {}, "coverage", "decrease", "primary"),
 "s14": ("dev", "boat_area_MoO3_cm2", 1, 4, {}, "coverage", "increase", "primary"),
 "j1": ("heldout", "T_boat_Mo_C", 800, 825, {}, "domain", "increase", "primary"),
 "j2": ("heldout", "T_boat_Mo_C", 825, 850, {}, "domain", "decrease", "primary"),
 "j3": ("heldout", "T_boat_Mo_C", 825, 850, {}, "nucleation", "increase", "primary"),
}
EXCLUDED = {"s02": "transverse substrate coordinate; model is 1-D along the tube", "s12": "MoO3 film thickness: needs film area and MoO3 density (no sourced values)"}
ORIG8 = ["s01", "s03", "s04", "s09", "s10", "s11", "s13", "s14"]


def _reversal(y):
    k = int(np.argmax(y)) if abs(y.max() - y[0]) + abs(y.max() - y[-1]) >= abs(y.min() - y[0]) + abs(y.min() - y[-1]) else int(np.argmin(y))
    return 0 < k < len(y) - 1 and abs(y[k] - y[0]) > TOL and abs(y[k] - y[-1]) > TOL


def call_from(Ys):
    """Ys: list of (draws x points) arrays (one per E corner). -> call, diagnostics."""
    nm = float(np.mean(np.concatenate([[_reversal(y) for y in Y] for Y in Ys])))
    if nm >= 0.9: return "non_monotonic", {"nm_frac": nm}
    Ds = [Y[:, -1] - Y[:, 0] for Y in Ys]
    p05, p95 = min(np.percentile(D, 5) for D in Ds), max(np.percentile(D, 95) for D in Ds)
    p50 = float(np.median(np.concatenate(Ds)))
    d = {"nm_frac": nm, "D_p05": float(p05), "D_p50": p50, "D_p95": float(p95)}
    if max(abs(p05), abs(p95)) < TOL: return "no_change", d
    if p05 > 0: return "increase", d
    if p95 < 0: return "decrease", d
    return "uncertain", d


def sensitivity_item(sid):
    st, par, lo, hi, base, obs, label, cls = ITEMS[sid]
    xs = np.linspace(lo, hi, NPTS)
    v0 = P.validate(wulff.DEFS, base)
    rng = np.random.default_rng(0)
    draws = [v0] + [uq.sample(wulff.DEFS, v0, rng) for _ in range(NMC - 1)]
    corners = ECORN if par == "T_furnace_C" else (0.0,)
    Y = {(i, e): [] for i in IS for e in corners}
    zero = True
    for dv in draws:
        try:
            sts = [growth.state(P.validate(wulff.DEFS, dv | {par: float(x)})) for x in xs]
        except (ValueError, FloatingPointError):
            continue
        zero &= all(s["F"] <= 0 for s in sts)
        for i in IS:
            for e in corners:
                Y[(i, e)].append([growth.observables(s, i, e)[obs] for s in sts])
    calls, diag = {}, {}
    for i in IS:
        calls[i], diag[i] = call_from([np.array(Y[(i, e)]) for e in corners])
    final = calls[1] if len(set(calls.values())) == 1 else "uncertain"
    return {"id": sid, "set": st, "param": par, "sweep": [lo, hi], "observable": obs, "label": label, "class": cls, "calls_by_i": {str(k): v for k, v in calls.items()},
            "call": final, "diag_i1": diag[1], "zero_flux": bool(zero), "n_draws": len(Y[(1, corners[0])])}


def shape_item(sid, cfg=None):
    from bench import shape_score as S
    st, par, lo, hi, base, obs, label, cls = ITEMS[sid]
    d = api_defaults() | (cfg or {})
    labs, ab = [], []
    for x in np.linspace(lo, hi, NPTS):
        with wulff.with_sigma(cfg or {}):
            p = S.predict(d | {par: float(x)})
        labs.append(p["label"]); ab.append(p["abstain"])
    call = "uncertain" if (ab[0] or ab[-1]) else ("class_change" if labs[0] != labs[-1] else "no_change")
    return {"id": sid, "set": st, "param": par, "sweep": [lo, hi], "observable": "shape", "label": label, "class": cls, "call": call, "labels": labs, "abstain": ab,
            "cfg": cfg or "M0", "zero_flux": False}


def api_defaults():
    from core import api
    return api.defaults("cvd_tube")


def correct(call, label):
    if label in ("increase", "decrease"): return call == label
    if label == "class_change": return call == "class_change"
    return call == label


def table(rows, key, n_extra=None):
    """rows: list of dicts with 'label' and predictions under `key`. -> (i) acc unc-wrong, (ii) acc confident, abstain rate"""
    n = len(rows)
    ok = sum(correct(r[key], r["label"]) for r in rows)
    unc = sum(r[key] == "uncertain" for r in rows)
    return {"n": n, "correct": ok, "acc_uncertain_wrong": ok / n if n else None, "n_confident": n - unc, "acc_confident": ok / (n - unc) if n - unc else None,
            "abstain_rate": unc / n if n else None}


def run_sensitivity():
    rows = {sid: (shape_item(sid) if ITEMS[sid][5] == "shape" else sensitivity_item(sid)) for sid in ITEMS}
    blind = {x["id"]: x["predicted_direction"] for x in json.load(open(f"{HERE}/sensitivity/blind_dev_s01_s14.json")) + json.load(open(f"{HERE}/sensitivity/blind_heldout_jian.json"))}
    old = {r["id"]: r for r in json.load(open(f"{HERE}/sensitivity/predictions.json"))["predictions"]}
    for sid, r in rows.items():
        r["blind"], r["always_increase"] = blind[sid], "increase"
        r["old_model"] = old[sid]["direction"] if sid in old and old[sid]["status"] == "modelled" else None
        r["old_model_uncertain"] = bool(old.get(sid, {}).get("uncertain")) if r["old_model"] else None
    return rows


def run_shape(configs):
    from bench import shape_score as S
    d = S.load(); labels = d["label_set"]; out = {}
    for name, cfg in configs.items():
        rows = []
        for c in d["cases"]:
            inp = S.build_inputs(c)
            with wulff.with_sigma(cfg):
                pr = S.predict(inp["values"] | cfg)
            rows.append({"id": c["id"], "in_scope": c["in_scope"], "reported": c["reported"]["label"], "pred": pr["label"], "abstain": pr["abstain"]})
        res = {}
        for scope, sel in (("in_scope", [r for r in rows if r["in_scope"]]), ("all", rows)):
            refs = [r["reported"] for r in sel]
            sc = S.score(refs, [r["pred"] for r in sel], labels)
            res[scope] = {"n": sc["n"], "accuracy": sc["accuracy"], "majority_class": sc["majority_class"], "majority_baseline": sc["majority_baseline"],
                          "always_triangle": sc["always_triangle_baseline"], "abstain_rate": sum(r["abstain"] is not None for r in sel) / len(sel),
                          "acc_abstain_wrong": sum(r["reported"] == r["pred"] and r["abstain"] is None for r in sel) / len(sel),
                          "predicted_classes": dict(Counter(r["pred"] for r in sel))}
        out[name] = {"scores": res, "cases": rows}
    return out


def collapse(configs):
    out = {}
    for name, cfg in configs.items():
        v = P.validate(wulff.DEFS, cfg)
        with wulff.with_sigma(cfg):
            m = wulff.shape_map(v, n=40, n_mc=30)
        out[name] = {"classes": dict(Counter(m["shape"])), "boundary_cm_from_boat": m["boundary_cm_from_boat"], "mean_band": float(np.mean(np.array(m["p95"]) - np.array(m["p05"])))}
    return out


CFG = {"M0_default_synthetic": {}, "M1_MACE_kink": {"E_kink_Mo.E_eV": 0.52, "E_kink_S.E_eV": 0.008},
       "M2_A1_dft_rosen_Mo_MACE_S": {"eq_model": "dft_rosen", "E_kink_S.E_eV": 0.008}}
DIAG = {"diagnostic_dft_rosen_Mo_synthetic_S": {"eq_model": "dft_rosen"}}  # not pre-registered, labelled diagnostic


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    rows = run_sensitivity()
    prim = [r for r in rows.values() if r["set"] == "dev" and r["class"] == "primary"]
    out = {"items": rows, "excluded": EXCLUDED}
    out["T1_dev_primary"] = {k: table(prim, k) for k in ("call", "blind", "always_increase")}
    o8 = [rows[s] for s in ORIG8]
    out["T2_original8"] = {k: table(o8, k) for k in ("call", "blind", "always_increase")}
    out["T2_original8"]["old_model"] = {"n": 8, "correct": 5, "acc_uncertain_wrong": 4 / 8, "note": "from bench/sensitivity/predictions.json: 5/8, 4/8 counting its 1 uncertain flag as wrong"}
    out["T3_secondary_class_change_nonshape"] = [{"id": s, "call": rows[s]["call"], "calls_by_i": rows[s].get("calls_by_i"), "rule": "correct iff non_monotonic", "correct": rows[s]["call"] == "non_monotonic"} for s in ("s05", "s06", "s07")]
    held = [r for r in rows.values() if r["set"] == "heldout"]
    out["T4_heldout"] = {k: table(held, k) for k in ("call", "blind", "always_increase")}
    out["s11_other_configs"] = {n: shape_item("s11", c)["call"] for n, c in CFG.items() if n != "M0_default_synthetic"}
    out["shape_benchmark"] = run_shape(CFG)
    out["shape_map_collapse"] = collapse(CFG | DIAG)
    print(json.dumps({k: v for k, v in out.items() if k not in ("items", "shape_benchmark")}, indent=1, default=float))
    for r in rows.values():
        print(r["id"], r["set"], r["param"], r["observable"], "label", r["label"], "call", r["call"], r.get("calls_by_i"), "zero" if r["zero_flux"] else "", "blind", r["blind"], r.get("diag_i1"))
    for n, s in out["shape_benchmark"].items(): print(n, json.dumps(s["scores"], default=float))
    if a.write:
        os.makedirs(OUT, exist_ok=True)
        json.dump(out, open(f"{OUT}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
