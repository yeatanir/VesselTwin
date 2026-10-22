"""Sensitivity-direction benchmark. python -m bench.sensitivity_score [--write]
Held-out bench/sensitivity/papers.json (14 observations, collected blind of the model; never edited here) vs the cvd_tube model.
MAP below was written BEFORE the first run (mapping + expected sign logic); nothing is tuned to the benchmark.
Each modellable item: sweep one canonical parameter low->high (core.api.solve, n_mc=100), read a Passport proxy at p05/p50/p95,
derive a direction. Items with no model parameter or no honest proxy are recorded 'not_modellable', never forced.
Proxies are ASSUMPTIONS: nucleation density ~ supersaturation_MoO3 (more driving force -> more nuclei); domain size ~ -supersaturation
(nucleation-limited, fewer nuclei -> larger domains); coverage / growth supply ~ flux_MoO3_mol_m2_s; shape ~ wulff shape class
(bench.shape_score.predict) at the substrate centre."""
import argparse, json, os
import numpy as np
from core import api

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/sensitivity"
DIRS = ["increase", "decrease", "no_change", "class_change", "non_monotonic"]
TOL = 0.05  # relative change of the proxy over the sweep below which we call it no_change (assumption)
SS, FLUX = "supersaturation_MoO3", "flux_MoO3_mol_m2_s"

# id: (param, [lo, hi], proxy, sign, expected sign logic)  | None-param => not_modellable with reason.
# sign: +1 observed quantity rises with proxy, -1 falls with proxy; proxy 'shape' = Wulff class at substrate centre.
MAP = {
 "s01": ("flow_sccm", [10, 160], SS, +1, "nucleation density ~ supersaturation. Prior: more carrier dilutes MoO3 vapour (SS down) but model is transport-limited so wall flux may rise; no confident sign. Paper's later decline above 160 not tested."),
 "s02": (None, None, None, None, "substrate lateral position in a flow-velocity profile; model is 1-D along the tube axis, no transverse coordinate"),
 "s03": ("flow_sccm", [50, 300], SS, -1, "domain size ~ -supersaturation. Prior: unclear (same as s01); more flow -> less residence/dilution -> expect SS down -> bigger domains (opposite to observed) if dilution dominates."),
 "s04": ("flow_sccm", [50, 150], FLUX, +1, "coverage ~ MoO3 flux to substrate. Prior: transport-limited, flux up with flow."),
 "s05": (None, None, None, None, "MoO3 charge mass / layer number: model is steady-state (no source depletion) and has no layer-number output"),
 "s06": (None, None, None, None, "sulfur charge mass: model has S boat T and area but no S amount; domain size from S amount has no proxy"),
 "s07": (None, None, None, None, "coverage/layer-number/3D-island sequence vs growth T: no layer-number or coalescence output, outcome mixes several quantities"),
 "s08": (None, None, None, None, "vertical source-substrate gap: model is 1-D, no vertical coordinate; layer number not modelled"),
 "s09": ("T_boat_Mo_C", [300, 400], SS, +1, "RANGE CLIPPED: paper 200-400 C, model lower bound is 300 C. nucleation density ~ SS. Prior: Psat(MoO3) rises steeply with T so SS up. (Absolute MoO3 vapour at 200-400 C is tiny; only the sign is tested.)"),
 "s10": ("T_furnace_C", [700, 850], SS, +1, "nucleation density ~ SS with T_boat_Mo fixed. Prior: hotter substrate -> Psat_eq(substrate) up -> SS down -> nucleation down. Range assumed (paper gave none)."),
 "s11": ("T_boat_S_C", [180, 300], "shape", None, "shape class (hex -> triangle) from Wulff shape_map via Mo:S ratio. Prior: more S vapour -> lower Mo:S -> shift toward S-rich (triangle_S/hexagon). Size peak not modelled; Mo boat T default, not 835 C."),
 "s12": (None, None, None, None, "MoO3 thin-film thickness (precursor amount): model has no source inventory"),
 "s13": ("T_furnace_C", [750, 850], FLUX, +1, "coverage density ~ MoO3 flux to substrate. Prior: flux drops as substrate gets hotter (re-evaporation) -> decrease."),
 "s14": ("boat_area_MoO3_cm2", [1, 4], FLUX, +1, "coverage ~ MoO3 supply; boat area as stand-in for nanoribbon density (range assumed). Prior: more area -> more flux."),
}
N_PTS = 5


def _metric(res, proxy):
    d = res["passport"]["derived"][proxy]
    return d["p05"], d["p50"], d["p95"]


def _dir(y):
    """direction from a series of p50 values over the sweep"""
    y = np.asarray(y, float); span = np.ptp(y); ref = max(abs(y).max(), 1e-300)
    if span / ref < TOL: return "no_change"
    d = np.diff(y); big = abs(d) > TOL * span
    s = np.sign(d[big])
    if len(set(s)) > 1: return "non_monotonic"
    return "increase" if y[-1] > y[0] else "decrease"


def _end_sign(a, b, tol=1e-12):
    return 0 if abs(b - a) <= tol * max(abs(a), abs(b), 1e-300) else (1 if b > a else -1)


def predict_one(sid):
    param, rng, proxy, sign, logic = MAP[sid]
    if param is None:
        return {"id": sid, "status": "not_modellable", "reason": logic}
    xs = list(np.linspace(rng[0], rng[1], N_PTS))
    base = {"id": sid, "parameter": param, "sweep": rng, "proxy": proxy, "expected_logic": logic}
    if proxy == "shape":
        from bench import shape_score as S
        d = api.defaults("cvd_tube")
        ps = [S.predict(d | {param: float(x)}) for x in xs]
        labs = [p["label"] for p in ps]
        ab = [p["abstain"] for p in ps]
        direction = "class_change" if len(set(labs)) > 1 else "no_change"
        return base | {"status": "modelled", "values": xs, "labels": labs, "abstain": ab, "direction": direction,
                       "uncertain": any(ab), "band": "label bands from shape_score p05/p95 shape index"}
    res = [api.solve("cvd_tube", {param: float(x)}, n_mc=100, extras=False) for x in xs]
    m = np.array([_metric(r, proxy) for r in res]) * sign  # cols p05,p50,p95 (sign flip swaps meaning of p05/p95 but band sign test is symmetric)
    if sign < 0: m = m[:, ::-1]
    direction = _dir(m[:, 1])
    # band: endpoint p05 and p95 deltas must agree with the p50 delta in sign (if p50 is monotone)
    s50 = _end_sign(m[0, 1], m[-1, 1])
    flips = [_end_sign(m[0, c], m[-1, c]) != s50 for c in (0, 2)] if direction in ("increase", "decrease") else [False, False]
    overlap = bool(max(m[0, 0], m[-1, 0]) <= min(m[0, 2], m[-1, 2]))
    return base | {"status": "modelled", "values": xs, "proxy_p05_p50_p95": m.tolist(), "regime": [r["regime"] for r in res],
                   "direction": direction, "band_overlap_endpoints": overlap, "uncertain": any(flips)}


def match(pred, obs):
    if obs == "class_change": return pred in ("class_change", "non_monotonic")
    return pred == obs


def run():
    papers = {p["id"]: p for p in json.load(open(f"{OUT}/papers.json"))}
    rows = []
    for sid, p in papers.items():
        r = predict_one(sid)
        r |= {"observed": p["observed_direction"], "outcome_quantity": p["outcome_quantity"], "confidence": p["confidence"],
              "parameter_obs": p["parameter"], "change": p["change"]}
        if r["status"] == "modelled":
            r["match"] = match(r["direction"], p["observed_direction"])
            r["match_strict"] = bool(r["match"] and not r["uncertain"])
        rows.append(r)
    return rows


BASELINE = "/private/tmp/claude-501/-Users-yeatanir-OSI-Hackathon/9eda40b9-b622-4dd7-b227-9e90bef27ef6/scratchpad/blind/baseline_predictions.json"


def summary(rows, baseline=None):
    mod = [r for r in rows if r["status"] == "modelled"]
    obs = [r["observed"] for r in mod]
    maj = max(sorted(set(obs)), key=obs.count)
    s = {"n_total": len(rows), "n_modellable": len(mod), "n_not_modellable": len(rows) - len(mod),
         "correct": sum(r["match"] for r in mod), "correct_strict_uncertain_wrong": sum(r["match_strict"] for r in mod),
         "n_uncertain": sum(r["uncertain"] for r in mod),
         "majority_class": maj, "majority_baseline_correct": obs.count(maj),
         "chance_note": "5 direction classes; uniform chance 20%"}
    if baseline:
        b = {x["id"]: x["predicted_direction"] for x in baseline}
        ok = {r["id"]: match(b[r["id"]], r["observed"]) for r in rows}
        allobs = [r["observed"] for r in rows]
        s |= {"blind_correct_all14": sum(ok.values()), "blind_correct_on_modellable8": sum(ok[r["id"]] for r in mod),
              "majority_all14": max(sorted(set(allobs)), key=allobs.count), "majority_all14_correct": allobs.count(max(sorted(set(allobs)), key=allobs.count))}
        for r in rows: r["blind"] = b[r["id"]]; r["blind_match"] = ok[r["id"]]
    return s


def write_md(rows, s):
    L = ["# Sensitivity-direction benchmark (held-out, 14 observations)", "",
         "Generated by `python -m bench.sensitivity_score --write`. Benchmark: `bench/sensitivity/papers.json` (collected blind of the model, unedited). "
         "Raw output: `bench/sensitivity/predictions.json`. No model parameter was tuned to these items; the proxy mapping was written in the script before the first run "
         "(one later change: s09 sweep clipped to 300-400 C because the model's `T_boat_Mo_C` lower bound is 300 C).", "",
         "| id | observed (quantity) | model sweep | proxy | predicted | band | match | blind baseline |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] == "modelled":
            sw = f"{r['parameter']} {r['sweep'][0]:g}->{r['sweep'][1]:g}"
            band = "uncertain" if r["uncertain"] else "ok"
            L.append(f"| {r['id']} | {r['observed']} ({r['outcome_quantity']}) | {sw} | {r['proxy']} | {r['direction']} | {band} | {'yes' if r['match'] else 'NO'} | {r.get('blind','-')} ({'yes' if r.get('blind_match') else 'NO'}) |")
        else:
            L.append(f"| {r['id']} | {r['observed']} ({r['outcome_quantity']}) | - | - | not_modellable | - | - | {r.get('blind','-')} ({'yes' if r.get('blind_match') else 'NO'}) |")
    L += ["", "## Summary (honest)", "",
          f"- Modellable: {s['n_modellable']} of {s['n_total']}; not_modellable: {s['n_not_modellable']} (no model parameter or no honest proxy; listed with reasons in the script MAP).",
          f"- Model direction accuracy on modellable items: **{s['correct']}/{s['n_modellable']}** ({s['correct']/s['n_modellable']:.0%}); counting band-uncertain predictions as wrong: {s['correct_strict_uncertain_wrong']}/{s['n_modellable']}. Uncertain flags: {s['n_uncertain']}.",
          f"- Majority-class baseline on the same items ('{s['majority_class']}' always): {s['majority_baseline_correct']}/{s['n_modellable']}. Uniform chance over 5 classes: 20%.",
          f"- Model minus majority baseline: {s['correct']-s['majority_baseline_correct']:+d} item(s)."]
    if "blind_correct_all14" in s:
        L += [f"- Blind no-tool baseline (separate agent, same 14 questions): {s['blind_correct_all14']}/14 overall, {s['blind_correct_on_modellable8']}/{s['n_modellable']} on the model's modellable items. Majority class over all 14 ('{s['majority_all14']}'): {s['majority_all14_correct']}/14."]
    else:
        L += ["- Blind baseline file not found at run time; not compared."]
    L += ["", "## Caveats", "",
          "- n is tiny (8 scored items, 14 total). One item moves accuracy by 12.5 points; differences of 1-2 items from the majority or blind baselines are not evidence either way.",
          "- Proxies are assumptions, not model outputs of the observed quantity: nucleation density ~ supersaturation_MoO3; domain size ~ -supersaturation; coverage ~ MoO3 flux to substrate; shape ~ Wulff class at the substrate centre. A wrong proxy makes a wrong prediction that says nothing about the transport/thermo physics.",
          "- Several sweep ranges are assumed (s10, s14) or clipped (s09); s11 uses the default Mo boat T, not the paper's 835 C. Model rates are partly synthetic (Passport `synthetic: true`).",
          "- Observed labels 'class_change' are matched by a predicted class_change or non_monotonic; non-monotonic observations in s01/s04/s06/s07/s11 beyond the labelled range were not tested.",
          "- s11 'class_change' rests on a single sweep point whose shape band spans two classes (flagged uncertain); treat as fragile.",
          "- Direction rule: 5 equispaced points, p50 proxy, no_change below 5% relative span, non_monotonic if the p50 series reverses by more than 5% of its span. s04 is non_monotonic only through a ~8%-of-span late dip (borderline, p05-p95 bands overlap); s03 and s13 have real interior peaks in the proxy. Peaks in s03/s13 are model-proxy features, so the 'wrong' verdicts there could reflect the proxy choice (s03: -supersaturation) as much as the physics."]
    open(f"{HERE}/../docs/sensitivity_benchmark.md", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    rows = run(); s = summary(rows, json.load(open(BASELINE)) if os.path.exists(BASELINE) else None)
    for r in rows: print(r["id"], r["status"], r.get("direction", "-"), "obs:", r["observed"], r.get("match", "-"), "unc" if r.get("uncertain") else "")
    print(s)
    if a.write:
        json.dump({"summary": s, "predictions": rows}, open(f"{OUT}/predictions.json", "w"), indent=1, default=float)
        write_md(rows, s)
