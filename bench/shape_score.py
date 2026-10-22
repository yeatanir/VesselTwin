"""MoS2 shape benchmark. python -m bench.shape_score [--write] [-v]
Offline: bench/shape/papers.json (labels, text excerpts, manual completions) -> SetupSpec (llm.extract, rules or replay)
+ flagged manual completion -> vessels.cvd_tube.wulff.shape_map at the stated substrate position -> label -> scores.
Nothing here tunes a model parameter. --write refreshes bench/shape/inputs.json and predictions.json (tests check they match).
Labels: triangle, truncated_triangle, hexagon, mixed, other. The model can only say the first three (class at the substrate
centre); it ABSTAINS when the centre is outside the map or the p05..p95 band of the shape index spans two classes."""
import argparse, json, os
import numpy as np
from core import params as P
from llm.extract import extract
from llm.units import to_unit
from schemas.setupspec import Status
from vessels.cvd_tube import wulff

HERE = os.path.dirname(os.path.abspath(__file__))
SH = os.path.join(HERE, "shape")
# parameters that decide the shape at the substrate; completeness = share known from the paper (stated or manual)
KEYS = ["T_boat_Mo_C", "T_boat_S_C", "T_furnace_C", "flow_sccm", "carrier", "tube_id_in", "x_substrate_cm", "x_S_boat_cm",
        "x_MoO3_cm", "pressure_Pa"]
COARSE = {"triangle_Mo": "triangle", "triangle_S": "triangle", "truncated_triangle": "truncated_triangle", "hexagon": "hexagon"}


def load(): return json.load(open(f"{SH}/papers.json"))


def build_inputs(c) -> dict:
    """-> {'values': canonical overrides, 'provenance': {key: stated|manual}, 'completeness', 'unknown': [...]}"""
    if c["extractor"] == "replay":
        spec = extract(c["text"], "cvd_tube", "replay", runs_dir=os.path.join(HERE, "llm_runs", "claude_agent"), name=c["procedure"])
    else:
        spec = extract(c["text"], "cvd_tube", "rules")
    defs = {d.name: d for d in wulff.DEFS}
    vals, prov = {}, {}
    for k, f in spec.params.items():
        if f.status is Status.stated:
            vals[k] = f.value if defs[k].choices else (to_unit(f.value, f.unit, defs[k].unit) if f.unit else f.value)
            prov[k] = "stated"
    for m in c["manual"]:
        k = m["key"]
        vals[k] = m["value"] if defs[k].choices else (to_unit(m["value"], m["unit"], defs[k].unit) if m["unit"] else m["value"])
        prov[k] = "manual"
    vals = {k: (float(v) if not defs[k].choices else v) for k, v in vals.items()}
    known = [k for k in KEYS if k in prov]
    return {"values": vals, "provenance": prov, "completeness": len(known) / len(KEYS), "unknown": [k for k in KEYS if k not in prov]}


def _cls(s, v): return COARSE[str(wulff.geometry(wulff._r(np.array([s])), v)[0][0])]


def predict(values: dict) -> dict:
    """Shape class at the substrate centre from wulff.shape_map (the extras['shape_map'] of core.api.solve)."""
    v = P.validate(wulff.DEFS, values)
    m = wulff.shape_map(v, n=40, n_mc=30)
    x = v["x_substrate_cm"] + v["substrate_length_cm"] / 2
    xr = np.array(m["x_from_boat_cm"])
    out = {"x_from_boat_cm": x, "map_range_cm": [float(xr[0]), float(xr[-1])], "boundary_cm_from_boat": m["boundary_cm_from_boat"]}
    if x < xr[0] - 1e-9 or x > xr[-1] + 1e-9:
        return out | {"label": None, "abstain": "outside_map"}
    i = int(np.argmin(abs(xr - x)))
    lab = COARSE[m["shape"][i]]
    lo, hi = _cls(m["p05"][i], v), _cls(m["p95"][i], v)
    out |= {"label": lab, "shape_index": m["shape_index"][i], "band_labels": sorted({lo, hi, lab})}
    return out | {"abstain": "band_spans_classes" if len({lo, hi, lab}) > 1 else None}


def confusion(refs, preds, labels):
    """rows = reference, cols = predicted; None predictions (abstentions) go to an extra 'abstain' column."""
    cols = list(labels) + ["abstain"]
    M = {r: {c: 0 for c in cols} for r in labels}
    for r, p in zip(refs, preds):
        M[r][p if p is not None else "abstain"] += 1
    return M


def score(refs, preds, labels):
    """preds may contain None (abstain, counted wrong). Accuracy vs the majority-class baseline of refs."""
    n = len(refs)
    correct = sum(r == p for r, p in zip(refs, preds))
    maj = max(labels, key=lambda l: refs.count(l))
    ans = [(r, p) for r, p in zip(refs, preds) if p is not None]
    return {"n": n, "accuracy": correct / n, "majority_class": maj, "majority_baseline": refs.count(maj) / n,
            "always_triangle_baseline": refs.count("triangle") / n, "answered": len(ans),
            "accuracy_answered": (sum(r == p for r, p in ans) / len(ans)) if ans else None, "confusion": confusion(refs, preds, labels)}


def run(compute=True):
    d = load()
    labels = d["label_set"]
    rows = []
    default_pred = predict({})["label"]
    for c in d["cases"]:
        inp = build_inputs(c)
        pr = predict(inp["values"]) if compute else None
        rows.append({"id": c["id"], "in_scope": c["in_scope"], "paper": c["title"][:50], "reported": c["reported"]["label"],
                     "figure": c["figure"]["label"], "inputs": inp, "prediction": pr, "defaults_only": default_pred})
    return labels, rows


def summarise(labels, rows):
    res = {}
    for name, sel in (("in_scope", [r for r in rows if r["in_scope"]]), ("all", rows)):
        refs = [r["reported"] for r in sel]
        res[name] = {"vs_reported": score(refs, [r["prediction"]["label"] for r in sel], labels),
                     "vs_reported_abstain_if_band": score(refs, [None if r["prediction"]["abstain"] else r["prediction"]["label"] for r in sel], labels),
                     "defaults_only_accuracy": sum(r["reported"] == r["defaults_only"] for r in sel) / len(sel)}
        fs = [r for r in sel if r["figure"]]
        res[name]["vs_figure"] = score([r["figure"] for r in fs], [r["prediction"]["label"] for r in fs], labels)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="refresh bench/shape/inputs.json and predictions.json")
    a = ap.parse_args()
    labels, rows = run()
    if a.write:
        json.dump({r["id"]: r["inputs"] for r in rows}, open(f"{SH}/inputs.json", "w"), indent=1)
        json.dump({r["id"]: r["prediction"] | {"defaults_only": r["defaults_only"]} for r in rows}, open(f"{SH}/predictions.json", "w"), indent=1)
    print("id   scope compl  reported            figure              predicted (abstain)")
    for r in rows:
        p = r["prediction"]
        print(f"{r['id']:4} {'in ' if r['in_scope'] else 'out'}   {r['inputs']['completeness']:.1f}   {r['reported']:19} {str(r['figure']):19} {p['label']} ({p['abstain']}) x={p['x_from_boat_cm']:.1f}cm")
    s = summarise(labels, rows)
    for k, v in s.items():
        print(f"\n== {k}: n={v['vs_reported']['n']}")
        for kk in ("vs_reported", "vs_reported_abstain_if_band", "vs_figure"):
            x = v[kk]
            print(f"  {kk}: acc={x['accuracy']:.2f} (n={x['n']}) majority={x['majority_class']} {x['majority_baseline']:.2f} always-triangle={x['always_triangle_baseline']:.2f} answered={x['answered']} acc_answered={x['accuracy_answered']}")
        print(f"  defaults-only accuracy vs reported: {v['defaults_only_accuracy']:.2f}")
        print("  confusion (rows reported, cols predicted):")
        for r, row in v["vs_reported"]["confusion"].items():
            print(f"    {r:19}", row)


if __name__ == "__main__":
    main()
