# Track M progress (branch track-m from origin/polish 512e052)

Files I touch: vessels/cvd_tube/__init__.py, vessels/cvd_tube/growth.py, vessels/cvd_tube/reactive.py (new), bench/track_m/ (new), bench/track_m_score.py (new),
tests/test_track_m.py (new), docs/prereg/track-m.md, docs/track_m_results.md, docs/progress/track-m.md, docs/handoff/requests-m.md. Nothing else. No OpenFOAM, no API keys, no Edison credits, no processes started.

## Log
- Oct 21: read shared rules, status, Track K/L docs, track_l_score, tube model. Stored default reference captured BEFORE any model edit (bench/track_m/default_reference.json, 4 cases, full flux/pM arrays).
- Added reactive.py (switches substrate_uptake_model, wall_uptake_model + 6 synthetic ParamDefs), edited march (legacy path untouched, new general path) and growth.gap_flux. Default reproduces the stored reference bit-for-bit (test). 14 tests in tests/test_track_m.py pass.
- Next: commit pre-registration, then run flux_vs_distance and the single scoring run.
- Oct 21: pre-registration committed (02e103f). Then ran `python -m bench.track_m_score --flux --write` (M3, done, ~80 s) and started the single scoring run `--score --write`, PID 66007 (log /private/tmp/claude-501/score_m.log). Kill only PID 66007 if needed. Next: write docs/track_m_results.md from bench/track_m/results.json, run make test, push track-m.
- Oct 21: scoring done (PID 66007 finished), M3 file written, post-hoc diagnostic (PID 66722, finished) written to bench/track_m/posthoc.json; docs/track_m_results.md written. Next: make test, commit, push track-m.
