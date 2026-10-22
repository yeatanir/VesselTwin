"""Reasoning trace: a deterministic scripted policy (stand-in for the LLM tool loop) that answers one benchmark question
and records every tool call. A real LLM backend replaces `run_policy` and must emit the same schema (docs/trace_schema.md).
Labels are defined ONLY here (LABEL_RULES / EVIDENCE_CAP) and enforced by `validate`. Offline: no network, seeded."""
import json, pathlib, re
import numpy as np
from core import api
from llm.extract import extract, detect_vessel
from llm.excerpt_match import supports

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACES = ROOT / "traces"
SCHEMA_VERSION = 1
SEED, N_MC = 0, 30
LABELS = ("hypothesis", "uncertain", "benchmarked")  # rank order: a label may never exceed the weakest evidence behind it

LABEL_RULES = {
    "benchmarked": "This exact comparison passed a documented held-out benchmark item (model direction == paper direction, p05/p95 band "
                   "does not contradict it, band endpoints do not overlap). It says nothing about overall skill: the sensitivity "
                   "benchmark is 2/8 (original 8 items) against a blind no-tool baseline of 6/8.",
    "uncertain": "Some documented support, but a flag applies: band overlap or sign flip, a single-paper quote, a span-checked "
                 "extraction, or a fragile benchmark match.",
    "hypothesis": "No passing benchmark: synthetic or default inputs, a benchmark the model failed, or a benchmark that only ties "
                  "the majority baseline (shape class: accuracy 0.50 = majority baseline). Never shown as a result.",
}
# evidence kind -> highest label it can support. A claim's cap is the MINIMUM over all its evidence (weakest link).
EVIDENCE_CAP = {
    "benchmark_pass": "benchmarked",        # ref = sensitivity item id with match true, not uncertain, no band overlap
    "benchmark_pass_fragile": "uncertain",  # matched but band overlaps / uncertain flag / sign flip
    "benchmark_fail": "hypothesis",         # model disagreed with the paper
    "benchmark_at_baseline": "hypothesis",  # benchmark no better than majority baseline (shape class)
    "synthetic_model": "hypothesis",        # Passport flagged synthetic=True
    "paramdef_default": "hypothesis",       # value is a ParamDef default, not stated
    "span_check": "uncertain",              # value found in text and span-checked
    "literature_quote": "uncertain",        # verbatim quote from one paper
    "tier_status": "hypothesis",            # tiers.json: cvd_tube verification misses its targets, Wulff rates synthetic/tuned
}


def cap_of(evidence):
    if not evidence:
        return "hypothesis"
    return min((EVIDENCE_CAP[e["kind"]] for e in evidence), key=LABELS.index)


def _read(p):
    return json.loads((ROOT / p).read_text())


def _words(s):
    return len(s.split())


def question_ids():
    return [p["id"] for p in _read("bench/sensitivity/papers.json")]


# ---- recorder ----
class Rec:
    def __init__(self):
        self.calls = []

    def call(self, name, args, fn, summarise):
        out = fn()
        self.calls.append({"name": name, "args": args, "result_summary": summarise(out)})
        return out

    def take(self):
        c, self.calls = self.calls, []
        return c


def _g(x):
    return f"{x:.3g}"


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", re.sub(r"[*#\n]+", " ", text)) if s.strip()]


def search_literature(paper, papers):
    """Verbatim excerpts only (<=40 words). Own benchmark paper, siblings with the same observed parameter, and answer sentences
    from docs/literature/*.json that share a content word with the question (verbatim substring of the stored answer)."""
    out = []
    for p in papers:
        if p["id"] == paper["id"] or p["parameter"] == paper["parameter"]:
            for q in [x.strip() for x in p["quote"].split("...") if x.strip()]:
                if _words(q) <= 40:
                    out.append({"source": "bench/sensitivity/papers.json", "id": p["id"], "doi": p["doi"], "citation": p["citation"],
                                "quote": q, "observed_direction": p["observed_direction"], "confidence": p["confidence"],
                                "is_question_paper": p["id"] == paper["id"]})
    toks = {t for t in re.findall(r"[a-z0-9]{5,}", (paper["parameter"] + " " + paper["outcome_quantity"]).lower())} - {"rate", "size", "layer"}
    for f in sorted((ROOT / "docs/literature").glob("edison_*.json")):
        ans = json.loads(f.read_text())["answer"]
        for s in _sentences(ans):
            if _words(s) <= 40 and re.search(r"MoS|MoO", s) and len(toks & set(re.findall(r"[a-z0-9]{5,}", s.lower()))) >= 2 and s in re.sub(r"[*#\n]+", " ", ans):
                out.append({"source": f"docs/literature/{f.name}", "id": f.stem, "doi": None, "citation": f"Edison literature agent answer ({f.stem})",
                            "quote": s, "observed_direction": None, "confidence": None, "is_question_paper": False})
    for e in out:  # pre-registered support rule (docs/prereg/track-c.md): alias + value within 2%
        e["support"] = supports(paper["id"], paper["change"], e["quote"])
    return out[:8]


def is_sign_flip(signs):
    """True only when the p05 and p95 series trend in strictly opposite directions (+1 vs -1). A flat series (0) is not a flip."""
    return signs is not None and signs[0] * signs[2] < 0


def sign_series(arr):
    """direction sign of each series (p05,p50,p95) endpoint-to-endpoint, 0 if |change| < 5% of series max."""
    a = np.asarray(arr, float)
    res = []
    for c in range(3):
        d = a[-1, c] - a[0, c]
        res.append(0 if abs(d) < 0.05 * max(abs(a[:, c]).max(), 1e-300) else int(np.sign(d)))
    return res


# knob -> (kind, step): rel = +-fraction of the value, abs = +- native units (temperatures in C)
KNOBS = {"flow_sccm": ("rel", 0.1), "T_boat_Mo_C": ("abs", 25), "T_boat_S_C": ("abs", 25), "T_furnace_C": ("abs", 25), "boat_area_MoO3_cm2": ("rel", 0.1)}


def knob_bars(values, proxy):
    """Each knob moved by +-10% (flow, boat area) or +-25 C (temperatures), clipped to bounds, re-solved with the same seed. Effect = change in the proxy p50, in % of the base p50;
    whisker = same change computed from the p05 and p95 of the proxy."""
    sch = {d["name"]: d for d in api.schema("cvd_tube")}

    def get(v):
        r = api.solve("cvd_tube", v, n_mc=N_MC, seed=SEED, extras=False)
        d = r["passport"]["derived"][proxy]
        return d["p05"], d["p50"], d["p95"]

    base = get(values)
    rows = []
    for k, (kind, st) in KNOBS.items():
        x0 = values.get(k, api.defaults("cvd_tube")[k])
        d = x0 * st if kind == "rel" else st
        lo, hi = max(x0 - d, sch[k]["lo"]), min(x0 + d, sch[k]["hi"])
        a, b = get(values | {k: lo}), get(values | {k: hi})
        e = [100 * (b[i] - a[i]) / abs(base[1]) for i in range(3)]
        rows.append({"knob": k, "low": lo, "high": hi, "step": f"{st:.0%}" if kind == "rel" else f"{st} C", "effect_p50_pct": e[1], "effect_p05_pct": e[0], "effect_p95_pct": e[2]})
    return {"proxy": proxy, "base_p05_p50_p95": list(base), "rows": rows}


def run_policy(qid, n_mc=N_MC):
    """Scripted policy: fixed order of tool calls. Returns the trace dict (schema in docs/trace_schema.md)."""
    papers = {p["id"]: p for p in _read("bench/sensitivity/papers.json")}
    pred = {p["id"]: p for p in _read("bench/sensitivity/predictions.json")["predictions"]}
    paper, pr = papers[qid], pred[qid]
    from bench.sensitivity_score import MAP
    tiers = _read("tiers.json")
    R = Rec()
    q = (f"{paper['system']}. What happens to the {paper['outcome_quantity']} when the {paper['parameter']} changes "
         f"({paper['change']})?")
    steps = []

    # 1 extract setup
    vessel = R.call("detect_vessel", {"text": q}, lambda: detect_vessel(q), lambda v: v)
    spec = R.call("extract_setup", {"text": q, "vessel": vessel, "backend": "rules", "fill_defaults": True},
                  lambda: extract(q, vessel, "rules", fill_defaults=True),
                  lambda s: "%d stated, %d default, %d missing" % tuple(sum(f.status.value == k for f in s.params.values()) for k in ("stated", "default", "missing")))
    dflt = api.defaults(vessel)
    fields = {k: {"status": f.status.value, "value": f.value, "unit": f.unit, "span": f.span, "note": f.note} for k, f in spec.params.items()}
    stated = [k for k, f in fields.items() if f["status"] == "stated"]
    claims = [{"id": "c1.1", "text": f"{len(stated)} setup parameter(s) are stated in the question text"
               + (": " + ", ".join(stated) if stated else "; everything else is a model default"),
               "evidence": [{"kind": "span_check", "ref": "llm/span_check.py"}] if stated else [{"kind": "paramdef_default", "ref": "ParamDef"}]}]
    if len(stated) < len(fields):
        claims.append({"id": "c1.2", "text": f"{len(fields) - len(stated)} parameters are ParamDef defaults, not facts about this experiment",
                       "evidence": [{"kind": "paramdef_default", "ref": "ParamDef"}]})
    steps.append({"name": "extract_setup", "title": "Extract the setup", "tool_calls": R.take(), "claims": claims,
                  "data": {"vessel": vessel, "fields": fields}})

    # 2 literature
    lit = R.call("search_literature", {"parameter": paper["parameter"], "outcome": paper["outcome_quantity"]},
                 lambda: search_literature(paper, list(papers.values())), lambda r: f"{len(r)} excerpt(s)")
    claims = []
    own = [e for e in lit if e["is_question_paper"]]
    if own:
        claims.append({"id": "c2.1", "text": f"Paper reports: {paper['outcome_quantity']} shows '{paper['observed_direction']}' for "
                       f"{paper['parameter']} ({paper['change']})", "evidence": [{"kind": "literature_quote", "ref": own[0]["doi"], "quote": own[0]["quote"]}]})
    steps.append({"name": "literature", "title": "Literature evidence", "tool_calls": R.take(), "claims": claims,
                  "data": {"excerpts": lit, "found": bool(lit), "observed_direction": paper["observed_direction"], "doi": paper["doi"],
                           "paper_confidence": paper["confidence"], "paper_notes": paper["notes"]}})

    # 3 vessel run
    res = R.call("run_vessel", {"vessel": vessel, "spec_hash_fields": stated, "n_mc": n_mc, "seed": SEED},
                 lambda: api.solve(vessel, spec=spec, n_mc=n_mc, seed=SEED), lambda r: f"regime={r['regime']}, synthetic={r['passport']['synthetic']}")
    ps = res["passport"]
    rows = [("T_K", ps["T_K"])] + [(f"{s}.{qn}", d) for s, qs in ps["species"].items() for qn, d in qs.items()] + list(ps["derived"].items())
    passport = [{"quantity": n, "unit": d["unit"], "p05": d["p05"], "p50": d["p50"], "p95": d["p95"]} for n, d in rows if d["p05"] is not None]
    proxy = MAP[qid][2] if MAP[qid][2] not in (None, "shape") else "supersaturation_MoO3"
    bars = R.call("knob_sensitivity", {"proxy": proxy, "knobs": list(KNOBS), "step": "+-10% or +-25 C"},
                  lambda: knob_bars(res["values"], proxy), lambda b: "largest: " + max(b["rows"], key=lambda r: abs(r["effect_p50_pct"]))["knob"])
    sm = res["extras"]["shape_map"]
    xc = res["values"]["x_substrate_cm"] + res["values"]["substrate_length_cm"] / 2
    i = int(np.argmin(np.abs(np.array(sm["x_from_boat_cm"]) - xc)))  # shape-map axis = cm from the MoO3 boat (as in bench/shape_score)
    shape_here = sm["shape"][i] if sm.get("shape") else None
    syn = [{"kind": "tier_status", "ref": "tiers.json:cvd_tube"}] + ([{"kind": "synthetic_model", "ref": "Passport.synthetic"}] if ps["synthetic"] else [])
    claims = [{"id": "c3.1", "text": "Passport quantities (p05/p50/p95) are placeholders-in-play, not validated predictions"
               if ps["synthetic"] else "Passport quantities from sourced inputs",
               "evidence": syn},
              {"id": "c3.2", "text": f"Predicted flake shape class at the substrate: {shape_here}",
               "evidence": [{"kind": "benchmark_at_baseline", "ref": "docs/track_a_results.md: accuracy 0.50 = majority baseline"}]},
              {"id": "c3.3", "text": f"Knob effects on {proxy} (one step each side) with p05..p95 whiskers are model sensitivities",
               "evidence": syn}]
    steps.append({"name": "vessel_model", "title": "Run the vessel model", "tool_calls": R.take(), "claims": claims,
                  "data": {"regime": res["regime"], "tier": ps["tier"], "synthetic": ps["synthetic"], "passport": passport,
                           "knob_bars": bars, "shape_here": shape_here, "tier_status": tiers["cvd_tube"]["status"]}})

    # 4 compare
    cmp_ = R.call("compare_direction", {"id": qid, "model_source": "bench/sensitivity/predictions.json"}, lambda: pr, lambda p: f"status={p['status']}, direction={p.get('direction')}")
    d = {"status": pr["status"], "observed": paper["observed_direction"], "parameter": pr.get("parameter"), "sweep": pr.get("sweep"),
         "proxy": pr.get("proxy"), "reason": pr.get("reason"), "model_direction": pr.get("direction"), "match": pr.get("match"),
         "uncertain": pr.get("uncertain"), "band_overlap_endpoints": pr.get("band_overlap_endpoints"), "values": pr.get("values"),
         "labels": pr.get("labels"), "summary": _read("bench/sensitivity/predictions.json")["summary"], "flip": False, "signs": None, "series": None}
    claims = []
    if pr["status"] == "not_modellable":
        d["verdict"] = "not_modellable"
    else:
        if "proxy_p05_p50_p95" in pr:
            m = np.array(pr["proxy_p05_p50_p95"])
            s = MAP[qid][3]
            raw = (m[:, ::-1] * s) if s < 0 else m  # undo the benchmark's sign-adjust so the chart shows the real proxy
            d["series"] = raw.tolist()
            d["signs"] = sign_series(raw)
            d["flip"] = is_sign_flip(d["signs"])
        fragile = bool(pr.get("uncertain") or pr.get("band_overlap_endpoints") or d["flip"])
        d["verdict"] = "disagree" if not pr["match"] else ("agree_fragile" if fragile else "agree")
        kind = {"disagree": "benchmark_fail", "agree_fragile": "benchmark_pass_fragile", "agree": "benchmark_pass"}[d["verdict"]]
        claims.append({"id": "c4.1", "text": f"Model direction '{pr['direction']}' vs paper '{paper['observed_direction']}' for {pr['parameter']} "
                       f"{pr['sweep'][0]}->{pr['sweep'][1]}: {d['verdict'].replace('_', ' ')}",
                       "evidence": [{"kind": kind, "ref": qid}]})
        if d["flip"]:
            claims.append({"id": "c4.2", "text": "Model p05 and p95 trends point in opposite directions: the sign of the effect is not determined by the model",
                           "evidence": [{"kind": "benchmark_pass_fragile", "ref": qid}]})
    steps.append({"name": "compare", "title": "Model vs literature direction", "tool_calls": R.take(), "claims": claims, "data": d})

    # 5 briefs
    from atomistic import brief as B
    lead = max(bars["rows"], key=lambda r: abs(r["effect_p50_pct"]))
    br = R.call("make_atomistic_brief", {"vessel": vessel, "n_mc": n_mc, "seed": SEED}, lambda: B.make_brief(vessel, res["values"], n_mc=n_mc, seed=SEED),
                lambda b: f"{len(b['ranking'])} ranked calculations")
    verdict = d["verdict"] if "verdict" in d else "not_modellable"
    exp_lines = [f"Change first: {lead['knob']} (model: {lead['effect_p50_pct']:+.1f}% in {proxy} for +-{lead['step']}, p05..p95 {lead['effect_p05_pct']:+.1f}..{lead['effect_p95_pct']:+.1f}%)."]
    if verdict == "disagree":
        exp_lines.append(f"Model and paper disagree on {pr['parameter']}: measure {paper['outcome_quantity']} at 4+ points across {pr['sweep'][0]}-{pr['sweep'][1]} to see whether the trend is non-monotonic.")
    elif verdict == "not_modellable":
        exp_lines.append("The model has no knob for the question's parameter; treat the paper's observation as the only evidence and measure it directly.")
    else:
        exp_lines.append(f"Measure {paper['outcome_quantity']} at both ends of {pr['parameter']} {pr['sweep'][0]}-{pr['sweep'][1]} and compare with the paper's '{paper['observed_direction']}'.")
    exp_lines.append("Record the substrate position and boat positions: they are always defaults in this model.")
    top = br["ranking"][:3]
    sim_lines = [f"Rank {r['rank']}: {r['calc']} for {r['param']} [{r['cost']}], sigma {_g(r['sigma'])} {r['unit']} moves the outcome by {_g(r['delta'])} {r['outcome_unit'] or '-'}." for r in top] or ["No atomistic calculation maps to a nonzero effect."]
    kind = {"agree": "benchmark_pass", "agree_fragile": "benchmark_pass_fragile", "disagree": "benchmark_fail"}.get(verdict)
    exp_ev = ([{"kind": kind, "ref": qid}] if kind else []) + syn  # advice rests on the model sensitivities too: weakest link wins
    claims = [{"id": "c5.1", "text": exp_lines[0], "evidence": exp_ev},
              {"id": "c5.2", "text": sim_lines[0], "evidence": syn}]
    steps.append({"name": "briefs", "title": "Two briefs", "tool_calls": R.take(), "claims": claims,
                  "data": {"experimentalist": exp_lines, "simulation": sim_lines, "simulation_markdown": B.to_markdown(br), "synthetic": br["synthetic"]}})

    for n, s in enumerate(steps, 1):
        s["idx"] = n
        for c in s["claims"]:
            c["label"] = cap_of(c["evidence"])
    return {"schema_version": SCHEMA_VERSION, "trace_id": f"sens_{qid}", "policy": {"name": "scripted_v1", "kind": "scripted", "llm": None},
            "question": {"id": qid, "text": q, "benchmark": "bench/sensitivity/papers.json"}, "seed": SEED, "n_mc": n_mc,
            "steps": steps, "limits": known_misses()}


def known_misses():
    t = _read("tiers.json")
    return {"sensitivity": "Sensitivity-direction benchmark (pre-registered, Track A): model 2/8 on the original 8 modellable items, always-increase 4/8, blind no-tool baseline 6/8; held-out j1-j3 (n = 3, one paper) model 0/3 (docs/track_a_results.md).",
            "shape": "Shape-class benchmark: accuracy 0.50, equal to the always-triangle baseline (n = 14, 8 in scope; docs/track_a_results.md). Shape class is a hypothesis.",
            "tiers": {k: v["status"] for k, v in t.items() if k in ("cvd_tube", "ampoule")}}


# ---- validation ----
def validate(tr):
    """Raise AssertionError on schema violations or any label above its evidence cap."""
    pred = {p["id"]: p for p in _read("bench/sensitivity/predictions.json")["predictions"]}
    assert tr["schema_version"] == SCHEMA_VERSION and tr["policy"]["kind"] in ("scripted", "llm")
    assert tr["question"]["id"] in pred and tr["question"]["text"]
    assert [s["name"] for s in tr["steps"]] == ["extract_setup", "literature", "vessel_model", "compare", "briefs"]
    for s in tr["steps"]:
        assert s["tool_calls"] and all({"name", "args", "result_summary"} <= set(c) for c in s["tool_calls"]), s["name"]
        for c in s["claims"]:
            assert c["label"] in LABELS, c
            assert all(e["kind"] in EVIDENCE_CAP for e in c["evidence"]), c
            assert LABELS.index(c["label"]) <= LABELS.index(cap_of(c["evidence"])), f"label exceeds evidence: {c}"
            for e in c["evidence"]:
                if e["kind"] == "benchmark_pass":
                    p = pred[e["ref"]]
                    assert p.get("match") and not p.get("uncertain") and not p.get("band_overlap_endpoints"), f"benchmarked without a clean pass: {c}"
                if e["kind"] == "literature_quote":
                    assert _words(e["quote"]) <= 40, c
            if "shape class" in c["text"]:
                assert c["label"] == "hypothesis", c
    for e in next(s for s in tr["steps"] if s["name"] == "literature")["data"]["excerpts"]:
        assert _words(e["quote"]) <= 40
    return True


def path(qid):
    return TRACES / f"sens_{qid}.json"


def save(tr):
    TRACES.mkdir(exist_ok=True)
    path(tr["question"]["id"]).write_text(json.dumps(tr, indent=1, default=float))


def load(qid):
    f = path(qid)
    if f.exists():
        return json.loads(f.read_text())
    tr = run_policy(qid)
    validate(tr)
    try:
        save(tr)
    except OSError:
        pass
    return tr


if __name__ == "__main__":  # python -m llm.trace  -> (re)write traces/ for all 14 questions
    for qid in question_ids():
        tr = run_policy(qid)
        validate(tr)
        save(tr)
        print(qid, [c["label"] for s in tr["steps"] for c in s["claims"]])
