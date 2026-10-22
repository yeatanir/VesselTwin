"""Run MoS2-tube Tier 2 (OpenFOAM) cases and cache their parsed results as JSON, at most `JOBS` solver processes at once.
usage (python): from scripts.tube_cfd import run_many; run_many({"name": (values, tier2_knobs), ...})
ponytail: results are cached by case name only; delete the case dir to rerun."""
import concurrent.futures as cf, json, pathlib, subprocess, time
from tier2.openfoam import write_case, read_results, tube_fields

ROOT = pathlib.Path("/private/tmp/claude-501/-Users-yeatanir-OSI-Hackathon/9eda40b9-b622-4dd7-b227-9e90bef27ef6/scratchpad/tube2/cases")
import os
JOBS = int(os.environ.get("TUBE_JOBS", 3))
HERE = pathlib.Path(__file__).resolve().parents[1]


def run(name, values, t2=None):
    d = ROOT / name
    out = d / "result.json"
    if out.exists(): return json.loads(out.read_text())
    t0 = time.time()
    write_case("cvd_tube", {**values, **(t2 or {})}, d)
    r = subprocess.run(["bash", str(HERE / "tier2/run.sh"), str(d)], capture_output=True, text=True)
    if not list(d.glob("postProcessing/probes/*/U")): return {"name": name, "failed": r.stderr[-300:] + r.stdout[-300:]}
    pp = read_results(d, "cvd_tube", values)
    res = {"name": name, "wall_s": round(time.time() - t0), "p_MoO3_Pa": pp.species["MoO3_g"]["p_Pa"].p50, "p_S2_Pa": pp.species["S2_g"]["p_Pa"].p50,
           "ratio_Mo_S": pp.derived["ratio_Mo_S"].p50, "ss_gasT": pp.derived["supersaturation_MoO3"].p50, "T_gas_K": pp.T_K.p50,
           **{k: v.p50 for k, v in pp.derived.items() if k not in ("ratio_Mo_S", "supersaturation_MoO3")}, "values": values, "tier2": t2}
    out.write_text(json.dumps(res, indent=1))
    return res


def run_many(cases):
    with cf.ThreadPoolExecutor(JOBS) as ex:
        return dict(zip(cases, ex.map(lambda k: run(k, *cases[k]), cases)))
