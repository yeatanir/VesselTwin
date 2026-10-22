# Track C progress

## Files I will touch (declared before first edit)
- app/dashboard.py, app/trace_tab.py, app/brief_tab.py, new app/*.py (dashboard)
- llm/trace.py, new llm/agent.py, new llm/excerpt_match.py (trace / agent loop / excerpt matching)
- docs/trace_schema.md (trace schema doc)
- tests/test_dashboard.py, tests/test_trace.py, new tests/test_agent.py, tests/test_excerpt_match.py
- traces/*.json (regenerated stored scripted traces), runs/traces/*.jsonl (recorded runs)
- docs/prereg/track-c.md, docs/screens/CHECKLIST.md, docs/handoff/requests-c.md, docs/progress/track-c.md

## Log
- [Oct 20] Worktree ../vt-track-c, branch track-c. Prereg for C3 committed (1e226cb) before matcher existed.
- C3 done: llm/excerpt_match.py; scored once on 48 unique (question, quote) excerpts: 10 verified (own paper 9/19, sibling 1/6, Edison sentences 0/23). Stored traces regenerated with `support` field; UI shows verified/unverified excerpt.
- C2 done: flip condition fixed (strictly +1 vs -1; flat is not a flip); never occurs on the 14 stored items; banner kept, proven by constructed-series test (patched predictions -> run_policy -> AppTest renders SIGN FLIP).
- C5: reproduced pyarrow ArrowInvalid on [1.0,'Ar'] column; fix = app/common.show_df casts mixed object columns to str; used for every dataframe in app/. Could not reproduce the original mid-edit failure (no current frame mixes types); defensive fix + test.
- C4 partial: app/common.py (extras plots, status badges); photoreactor draws sensitivity bars through generic extras renderer; AppTest over vessel x tier and 14 trace questions. TODO: CHECKLIST.md, requests-c.md, handoff requests from A/B/E.
- C1: no real backend yet (mlx_lm not installed; HF cache has only microsoft/skala-1.1; no ollama). Next: write llm/agent.py loop with pluggable chat callable, check backend again later. Running PIDs: none.
- [Oct 20] C1: agent loop + JSONL logger + recorded-run replay built and tested with a stand-in chat (backend "test", never shown in the dashboard). Backend check Oct 20: mlx_lm not importable in any env, HF cache holds only microsoft/skala-1.1, no ollama/LM Studio; no model installed by me. Therefore NO genuine run recorded; the trace is labelled "Scripted replay (not model-driven)" (label is derived from trace policy.kind, so recorded runs appear automatically once `python -m llm.agent` is run with a working backend). I could not wait until Oct 21 14:00 ET to re-check.
- `make test`: 196 passed, 5 skipped. Branch pushed. Running PIDs: none.

# FINAL REPORT (Track C)

## What changed, file by file
- llm/agent.py (new): 4 tools with JSON schemas, loop (max 8 steps, schema-checked, errors bounce back), JSONL logging to runs/traces/, loader, `final_label` (set by code), `mlx_chat` adapter, `python -m llm.agent` recorder.
- llm/excerpt_match.py (new): pre-registered support rule (alias + value within 2%, pint units).
- llm/trace.py: excerpts carry `support`; `is_sign_flip` (strict +1 vs -1; flat is not a flip).
- app/common.py (new): `show_df` (casts mixed-type columns), status badges, generic `extras` plots (default `plots` schema and Track E's `photon_flux_vs_depth` format).
- app/dashboard.py, app/brief_tab.py: safe dataframes, status badge on regime / tier-0 numbers / passport (+ status column), "Model-declared plots" section (photoreactor now has a plot).
- app/trace_tab.py: honest label ("Scripted replay (not model-driven)" / "Recorded run · model · date"), verified/unverified excerpt badge, "N of M verified", timeline rail rebuilt (old rail used height:100% inside a Streamlit column, which cannot stretch), recorded-run view.
- traces/sens_s01..s14.json regenerated (only new `support` fields differ). docs/trace_schema.md, docs/screens/CHECKLIST.md, docs/handoff/requests-c.md, docs/prereg/track-c.md.
- Tests: tests/test_agent.py, test_excerpt_match.py, extended test_trace.py and test_dashboard.py (+ small AppTest scripts in tests/).

## Metrics (pre-registration commit 1e226cb)
- Excerpt support rule: 10 of 48 unique (question, quote) excerpts verified (own paper 9/19, sibling benchmark paper 1/6, Edison answer sentences 0/23). Old rule showed all 48 as matching on two shared words. Scored once, no method change.
- Tests: 153 pass/5 skip (as documented) -> 196 pass/5 skip, `make test`.

## Findings
- Sign flip: the banner never fires on the 14 stored items (signs are all uniform; s11 has no series). Old condition also counted a flat series vs a rising one as a flip; fixed. The condition can occur with real MC bands in principle, so the banner is kept and proven by a constructed-series test (patched predictions -> run_policy -> AppTest shows "SIGN FLIP").
- Flaky test: reproduced the pyarrow error (ArrowInvalid on a [1.0, 'Ar'] column) at the Streamlit layer; fix is casting at display, no retries. I could not reproduce the original mid-edit failure, so the root source frame is unidentified; every dataframe in app/ now goes through the cast.
- AppTest passes for 5 vessels x tiers 0/1/2, all 14 trace questions, brief tab, and extras.

## Abandoned / not done
- C1 real run: no working local LLM backend on Oct 20 (see above); relabelled scripted. Re-run `python -m llm.agent` after MLX works; no model installed by me.
- requests-b R2 (GCI bands) and R5 (surrogate correction) not applied: depend on files not on main. Track E format already supported; its params are not on main yet.
- Dashboard not viewed by eye (user does it from docs/screens/CHECKLIST.md).

## Constants
None added.

## Requests left
docs/handoff/requests-c.md (extras plot schema for Track E; notes on B's R2/R5 and tiers.json text for Track F).
