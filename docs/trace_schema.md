# Reasoning trace schema (version 1)

One JSON file per question in `traces/` (`sens_<id>.json`), written by `python -m llm.trace` (scripted policy, offline, seeded) and rendered by the dashboard tab "Reasoning trace" (`app/trace_tab.py`). A real LLM tool loop replaces `llm.trace.run_policy` and must emit the same schema; `llm.trace.validate` is the contract check.

```
{ "schema_version": 1, "trace_id": "sens_s03",
  "policy": {"name": "scripted_v1", "kind": "scripted" | "llm", "llm": null | model id},
  "question": {"id": "s03" (key in bench/sensitivity/papers.json), "text": str, "benchmark": path},
  "seed": int, "n_mc": int,
  "steps": [ exactly 5, in order: extract_setup, literature, vessel_model, compare, briefs
    { "idx": 1..5, "name": str, "title": str,
      "tool_calls": [ {"name": str, "args": {...}, "result_summary": str}, ... ]   // at least one
      "claims": [ {"id": "c<step>.<n>", "text": str, "label": "hypothesis"|"uncertain"|"benchmarked",
                   "evidence": [ {"kind": <EVIDENCE_CAP key>, "ref": str, "quote"?: str (<= 40 words)} ]} ],
      "data": {...step-specific payload the tab renders (see llm/trace.py)} } ],
  "limits": {"sensitivity": str, "shape": str, "tiers": {"cvd_tube": str, "ampoule": str}} }
```

## Label rules (single source: `llm.trace.LABEL_RULES`, `EVIDENCE_CAP`)
Order: hypothesis < uncertain < benchmarked. A claim's label may not exceed the **minimum** cap over its evidence; no evidence means hypothesis.

| evidence kind | cap |
|---|---|
| benchmark_pass (item matched paper, not uncertain, no band overlap) | benchmarked |
| benchmark_pass_fragile, span_check, literature_quote | uncertain |
| benchmark_fail, benchmark_at_baseline (shape class), synthetic_model, paramdef_default, tier_status (cvd_tube misses its verification targets) | hypothesis |

`benchmarked` means one held-out comparison passed; it is not a skill claim (sensitivity benchmark 2/8 vs blind baseline 6/8). Because every vessel-model claim also carries `tier_status`, briefs and passport numbers are always `hypothesis`. Excerpts are verbatim, 40 words or fewer; "no evidence found" is shown when none exist.

`validate` also checks: `benchmark_pass` refs exist in `bench/sensitivity/predictions.json` with `match` true; any claim mentioning "shape class" is `hypothesis`.

## Recorded model runs (Track C)
`llm/agent.py` runs a tool-choosing loop (tools: extract_setup, solve, rank_calculations, lookup_parameter; max 8 steps; schema-checked) and writes `runs/traces/<timestamp>.jsonl`, one event per line: `meta` (model, backend, date, question), `prompt`, `model_output`, `schema_error`, `tool_call`, `tool_output` (inline, or sha256 + head if over 2000 chars), `final`, `stopped`; every model output and tool output has `seconds`. The dashboard lists complete runs with backend != "test" as "Recorded run · <model> · <date>"; with none recorded, the `traces/sens_*.json` policy is labelled "Scripted replay (not model-driven)". The final answer's label is set by code (`llm.agent.final_label`), never by the model. Record: `python -m llm.agent` (needs mlx-lm and a local model).
