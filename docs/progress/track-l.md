# Track L progress
Files I will touch: bench/track_l/ (items.json, results), bench/track_l_score.py, tests/test_track_l.py, docs/prereg/track-l.md, docs/track_l_results.md, docs/progress/track-l.md, docs/handoff/requests-l.md.
Branch track-l from origin/polish, worktree ../vt-track-l. No PIDs.
- Step 1: read context; next: open the 8 papers (Xu 2018, Prasad 2023, Tummala 2020, Wang 2016, Wang 2025, Withanage 2018, Najmaei 2013, Jian 2019) and fill bench/track_l/items.json.
- Step 2 done: items.json from 7 opened papers (Wang 2016 not retrievable); prereg + code committed 903cc2a before scoring; scored once (both psat laws); results in docs/track_l_results.md. Next: make test, push track-l. No PIDs.
## Final report
See docs/track_l_results.md. Metrics before -> after (n, prereg 903cc2a): T1 dev primary 3/9 -> 1/9 (both laws; blind 6/9, always-increase 4/9); T2 original 8: 2/8 -> 1/8 (blind 6/8, 4/8); j1-j3: 0/3 -> 0/3 (all abstain now; blind 3/3, 2/3); T5 3/12 -> 1/12 (blind 9/12). No constants changed. Requests: docs/handoff/requests-l.md.
- make test: 298 passed (an earlier full run had 38 streamlit app-test failures under machine load, not reproduced on rerun).
