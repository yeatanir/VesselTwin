"""Tool-choosing agent loop (Track C1). A chat backend picks the next tool each step; every call is schema-checked, executed by thin
wrappers over existing code, and logged to runs/traces/<timestamp>.jsonl. Max 8 steps; stops on a final-answer object.
`chat(messages) -> str` is any callable with attributes .model and .backend; backends are built by llm.backends.make_chat (any provider). A scripted policy is never logged here: see llm/trace.py."""
import datetime as dt, hashlib, json, pathlib, re, time
from jsonschema import Draft202012Validator
from core import api
from core.registry import load_all
from llm.extract import extract, detect_vessel

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "traces"
MAX_STEPS = 8
_STATE: dict = {}  # run_id -> {"vessel", "values", "tier"}; per process


def _wrap_extract(text):
    v = detect_vessel(text)
    spec = extract(text, v, "rules")
    st = {k: {"value": f.value, "unit": f.unit} for k, f in spec.params.items() if f.status.value == "stated"}
    return {"vessel": v, "stated": st, "n_not_stated": len(spec.params) - len(st)}


def _wrap_solve(vessel, spec, tier):
    if vessel not in load_all():
        return {"error": f"unknown vessel {vessel!r}; choose one of {sorted(load_all())}"}
    bad = [k for k in spec if k not in load_all()[vessel].params]
    if bad:
        return {"error": f"unknown parameter(s) {bad} for {vessel}"}
    if tier == 2:
        f = ROOT / "cache" / "tier2" / f"{vessel}.json"
        return json.loads(f.read_text()) if f.exists() else {"error": f"no cached Tier 2 result for {vessel}; Tier 2 is never run by the agent"}
    try:
        r = api.solve(vessel, spec, n_mc=2 if tier == 0 else 30, seed=0)
    except Exception as e:  # validation bounce (bounds, units, choices) goes back to the model
        return {"error": f"{type(e).__name__}: {e}"}
    rid = hashlib.sha256(json.dumps([vessel, spec, tier], sort_keys=True, default=str).encode()).hexdigest()[:10]
    _STATE[rid] = {"vessel": vessel, "values": spec}
    d = {k: round(v["p50"], 4) for k, v in r["passport"]["derived"].items() if v["p50"] is not None}
    return {"run_id": rid, "regime": r["regime"], "tier": tier, "synthetic": r["passport"]["synthetic"], "derived_p50": d}


def _wrap_rank(run_id, outcome=None):
    from atomistic import brief as B
    s = _STATE.get(run_id)
    if s is None:
        return {"error": f"unknown run_id {run_id!r}; call solve first"}
    try:
        b = B.make_brief(s["vessel"], s["values"], n_mc=20, seed=0, outcome=outcome)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    return {"synthetic": b["synthetic"], "ranking": [{k: r[k] for k in ("rank", "calc", "param", "cost", "delta")} for r in b["ranking"][:3]]}


def _wrap_lookup(name):
    """Cached literature only (docs/literature/*.json, bench/sensitivity/papers.json): no network, no Edison call."""
    out, q = [], name.lower()
    for f in sorted((ROOT / "docs/literature").glob("edison_*.json")):
        for s in re.split(r"(?<=[.!?])\s+", re.sub(r"[*#\n]+", " ", json.loads(f.read_text())["answer"])):
            if q in s.lower() and len(s.split()) <= 40:
                out.append({"source": f.name, "excerpt": s.strip()})
    for p in json.loads((ROOT / "bench/sensitivity/papers.json").read_text()):
        if q in (p["parameter"] + " " + p["quote"]).lower():
            out.append({"source": "papers.json:" + p["id"], "excerpt": p["quote"][:300], "doi": p["doi"]})
    return {"found": len(out), "excerpts": out[:3]} if out else {"found": 0, "note": "nothing cached; no new literature call is made"}


S = {"type": "object", "additionalProperties": False}
TOOLS = {
    "extract_setup": ({**S, "required": ["text"], "properties": {"text": {"type": "string"}}}, lambda a: _wrap_extract(a["text"]),
                      "Read a procedure text: returns the vessel and the parameters it states."),
    "solve": ({**S, "required": ["vessel", "spec", "tier"], "properties": {"vessel": {"type": "string"}, "spec": {"type": "object"}, "tier": {"enum": [0, 1, 2]}}},
              lambda a: _wrap_solve(a["vessel"], a["spec"], a["tier"]),
              "Run the vessel model. spec = {param: value} in canonical units (use stated values from extract_setup). Returns run_id."),
    "rank_calculations": ({**S, "required": ["run_id"], "properties": {"run_id": {"type": "string"}, "outcome": {"type": "string"}}},
                          lambda a: _wrap_rank(a["run_id"], a.get("outcome")), "Which atomistic calculations most change the outcome of a solved run."),
    "lookup_parameter": ({**S, "required": ["name"], "properties": {"name": {"type": "string"}}}, lambda a: _wrap_lookup(a["name"]),
                         "Cached literature excerpts mentioning a parameter name. Read-only."),
}
FINAL = {**S, "required": ["answer", "change_first", "atomistic_priority", "caveats"],
         "properties": {k: {"type": "string"} for k in ("answer", "change_first", "atomistic_priority", "caveats")}}
ACTION = {"oneOf": [{**S, "required": ["tool", "args"], "properties": {"tool": {"enum": list(TOOLS)}, "args": {"type": "object"}}},
                    {**S, "required": ["final"], "properties": {"final": FINAL}}]}


def system_prompt():
    tools = "\n".join(f"- {n}: {d}\n  args schema: {json.dumps(s)}" for n, (s, _, d) in TOOLS.items())
    return ("You are the reasoning layer of VesselTwin. Answer the user's question about a synthesis procedure by calling tools, one per turn. "
            f"Reply with exactly one JSON object and nothing else: either {{\"tool\": <name>, \"args\": {{...}}}} or, when done, "
            f"{{\"final\": {json.dumps(FINAL)}-shaped object}}. You may take at most {MAX_STEPS} steps. Never invent numbers; "
            f"every number in your answer must come from a tool output.\nTools:\n{tools}")


def _hash(o):
    s = json.dumps(o, default=str)
    return s if len(s) <= 2000 else {"sha256": hashlib.sha256(s.encode()).hexdigest(), "bytes": len(s), "head": s[:300]}


def _parse(raw):
    try:
        return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return None


def run_agent(question, chat, runs_dir=RUNS, max_steps=MAX_STEPS):
    """Returns (final_answer_or_None, path_to_jsonl). Every prompt, model output, tool call and tool output is logged."""
    pathlib.Path(runs_dir).mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc)
    path = pathlib.Path(runs_dir) / (now.strftime("%Y%m%dT%H%M%S") + ".jsonl")
    log = lambda **e: open(path, "a").write(json.dumps({"t": round(time.time(), 3), **e}, default=str) + "\n")
    log(kind="meta", model=chat.model, backend=chat.backend, date=now.date().isoformat(), question=question, max_steps=max_steps)
    msgs = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": question}]
    check = Draft202012Validator(ACTION)
    final = None
    for step in range(1, max_steps + 1):
        log(kind="prompt", step=step, messages=msgs)
        t0 = time.time()
        raw = chat(msgs)
        log(kind="model_output", step=step, raw=raw, seconds=round(time.time() - t0, 3))
        act = _parse(raw)
        errs = ["not a JSON object"] if act is None else [e.message for e in check.iter_errors(act)]
        msgs.append({"role": "assistant", "content": raw})
        if errs:
            log(kind="schema_error", step=step, errors=errs[:3])
            msgs.append({"role": "user", "content": "Invalid action: " + "; ".join(errs[:3]) + ". Reply with one valid JSON object."})
            continue
        if "final" in act:
            final = act["final"]
            log(kind="final", step=step, final=final)
            break
        name, args = act["tool"], act["args"]
        ev = Draft202012Validator(TOOLS[name][0])
        errs = [e.message for e in ev.iter_errors(args)]
        log(kind="tool_call", step=step, name=name, args=args, schema_errors=errs)
        t0 = time.time()
        out = {"error": "arguments violate the tool schema: " + "; ".join(errs[:3])} if errs else TOOLS[name][1](args)
        log(kind="tool_output", step=step, name=name, output=_hash(out), seconds=round(time.time() - t0, 3))
        msgs.append({"role": "user", "content": "Tool output: " + json.dumps(out, default=str)})
    else:
        log(kind="stopped", reason=f"no final answer within {max_steps} steps")
    return final, path


def load_run(path):
    """JSONL -> {model, backend, date, question, steps: [{step, tool, args, output, seconds}], final, complete}."""
    ev = [json.loads(l) for l in pathlib.Path(path).read_text().splitlines() if l.strip()]
    meta = next(e for e in ev if e["kind"] == "meta")
    outs = {e["step"]: e for e in ev if e["kind"] == "tool_output"}
    steps = [{"step": e["step"], "tool": e["name"], "args": e["args"], "output": outs.get(e["step"], {}).get("output"), "seconds": outs.get(e["step"], {}).get("seconds")}
             for e in ev if e["kind"] == "tool_call"]
    fin = next((e["final"] for e in ev if e["kind"] == "final"), None)
    return {**{k: meta[k] for k in ("model", "backend", "date", "question")}, "steps": steps, "final": fin, "complete": fin is not None}


def recorded_runs(runs_dir=RUNS):
    """Complete runs from a real model backend only (backend 'test' is never shown in the dashboard)."""
    out = []
    for f in sorted(pathlib.Path(runs_dir).glob("*.jsonl")):
        try:
            r = load_run(f)
        except Exception:
            continue
        if r["complete"] and r["backend"] != "test":
            out.append({**r, "file": f.name})
    return out


def final_label(run):
    """The model never picks its own evidence label: any solve in the run carries the vessel tier/synthetic limits, so 'hypothesis'."""
    solved = [s for s in run["steps"] if s["tool"] == "solve"]
    return "hypothesis" if solved else "uncertain"


from llm.backends import make_chat, mlx_chat, anthropic_chat  # noqa: E402,F401  (re-exported; one implementation)


if __name__ == "__main__":  # python -m llm.agent --provider openai_compatible --base-url https://host/v1 --model NAME [--extra-headers JSON] [procedure.json ...]
    import argparse                # key: env VT_LLM_API_KEY only (never a CLI argument, so it cannot land in shell history)
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--provider"), ap.add_argument("--base-url"), ap.add_argument("--model"), ap.add_argument("--extra-headers")
    ap.add_argument("--anthropic", action="store_true", help="alias for --provider anthropic")
    a = ap.parse_args()
    chat = make_chat("anthropic" if a.anthropic else a.provider, a.base_url, None, a.model, a.extra_headers)
    if chat.backend == "rules":
        raise SystemExit("no chat backend: pass --provider (openai_compatible | anthropic | mlx) or set VT_LLM_PROVIDER")
    files = a.files or [str(ROOT / "bench/procedures" / f) for f in ("real_01_cvd_tube.json", "real_11_ampoule.json")]
    for f in files:
        text = json.loads(open(f).read())["text"]
        final, path = run_agent("Here is a synthesis procedure:\n" + text + "\nWhich variable should the experimentalist change first, and which atomistic calculation matters most?", chat)
        print(path, "final" if final else "NO FINAL ANSWER")
