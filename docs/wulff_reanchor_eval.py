"""Before/after of the kink re-anchoring (docs/wulff_reanchor.md). python -m docs.wulff_reanchor_eval  (or python docs/wulff_reanchor_eval.py)
Nothing is tuned: 'before' = default constants, 'after' = MLIP closures E_kink_Mo / E_kink_S applied via apply_wulff_closures.
Also records the old collapse (legacy_gamma + MLIP gamma) for reference. Writes docs/wulff_reanchor_eval.json."""
import json, collections, pathlib, sys
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import params as P
from atomistic import edges
from bench import shape_score as ss
from vessels.cvd_tube import wulff

V0 = P.defaults(wulff.DEFS)
KINK = wulff.apply_wulff_closures(V0, edges.closures_kink())
GAMMA = wulff.apply_wulff_closures(V0, edges.closures()) | {"eq_model": "legacy_gamma"}


def describe(v):
    m = wulff.shape_map(v, n=40, n_mc=30)
    cnt = collections.Counter(m["shape"])
    return {"classes": dict(cnt), "boundary_cm_from_boat": m["boundary_cm_from_boat"], "shape_index_first_mid_last": [m["shape_index"][0], m["shape_index"][20], m["shape_index"][-1]],
            "mean_band_width_p95_minus_p05": float(np.mean(np.array(m["p95"]) - np.array(m["p05"]))),
            "shape_vs_x": list(zip([round(x, 1) for x in m["x_from_boat_cm"]], m["shape"]))}


def bench(closure_values):
    """Run bench.shape_score with closure parameters merged into every case's values (bench/* untouched)."""
    orig = ss.predict
    if closure_values:
        extra = {k: x for k, x in closure_values.items() if k not in V0 or x != V0[k]}
        ss.predict = lambda vals: orig(vals | extra)
    try:
        labels, rows = ss.run()
    finally:
        ss.predict = orig
    s = ss.summarise(labels, rows)
    return {k: {"n": x["vs_reported"]["n"], "acc": x["vs_reported"]["accuracy"], "majority": x["vs_reported"]["majority_class"],
                "majority_baseline": x["vs_reported"]["majority_baseline"], "acc_abstain_if_band": x["vs_reported_abstain_if_band"]["accuracy"],
                "answered_if_band": x["vs_reported_abstain_if_band"]["answered"], "defaults_only": x["defaults_only_accuracy"],
                "confusion": x["vs_reported"]["confusion"]} for k, x in s.items()}, [(r["id"], r["reported"], r["prediction"]["label"], r["prediction"]["abstain"]) for r in rows]


if __name__ == "__main__":
    out = {"p_eq_Pa_at_1000K": {n: {e: float(wulff.p_eq(v, e, 1000.0)) for e in ("Mo", "S")} for n, v in (("default", V0), ("kink_mlip", KINK), ("legacy_mlip_gamma", GAMMA))}}
    for name, v in (("map_default", V0), ("map_kink_mlip", KINK), ("map_legacy_mlip_gamma", GAMMA)):
        out[name] = describe(v); print(name, out[name]["classes"], out[name]["boundary_cm_from_boat"], out[name]["mean_band_width_p95_minus_p05"], flush=True)
    SIM = {"MoO3.psat_model": "simnad_ocr", "MoO3.P_ref_Pa": 1.2}  # previous (OCR'd Simnad & Spilners) basis, for continuity
    for name, v in (("bench_before", None), ("bench_after", KINK), ("bench_before_simnad", SIM), ("bench_after_simnad", KINK | SIM)):
        out[name], out[name + "_rows"] = bench(v); print(name, {k: (x["acc"], x["majority_baseline"]) for k, x in out[name].items()}, flush=True)
    pathlib.Path(__file__).with_suffix(".json").write_text(json.dumps(out, indent=1))
