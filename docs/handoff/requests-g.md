# Requests from Track G
1. app/dashboard.py (Extract button, optional): `ex = extract_and_solve(st.session_state.proc)` could pass the session model with
   `extract_and_solve(st.session_state.proc, backend=lambda t, v: llm_backend(t, v, chat))` where `chat = app.llm_settings.get_chat()` (None -> keep "rules").
   Not applied: the extractor stays on `rules` unless this is wired.
2. Process note: any partial `pytest` run overwrites cache/harness.json with a subset (no `vessel` column), after which the dashboard Credibility tab raises KeyError 'vessel' (also affects tests/test_dashboard.py in a fresh worktree). Suggest the harness plugin only write on a full run, or the tab fall back to the snapshot when columns are missing.
3. requirements.txt: comment mentions `anthropic` extra; harmless. jsonschema and scikit-learn are imported by llm/agent.py and surrogate/* but not listed; the dashboard loads without them, `make test` needs them (conda env has them). Consider adding both.
