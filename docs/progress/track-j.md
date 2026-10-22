# Track J progress (visual-first Home page)

Branch `track-j` from origin/polish. Deadline Oct 21 17:00 ET. No OpenFOAM, no keys, Edison credits 0.

## Files I will touch
- NEW app/home.py, app/ui_kit.py, tests/test_home.py, docs/screens/CHECKLIST_home.md, docs/handoff/requests-j.md
- EDIT app/dashboard.py: tab-order/hook lines only (outer Home/Advanced tabs, Home call, sidebar collapsed, top selector row moved inside Advanced)

## Final report
- app/ui_kit.py (new): HTML helpers (badge, status dot, chips, tiles, stepper, meter, rank dot, inline SVG icons), Okabe-Ito palette, translucent fills for light/dark.
- app/home.py (new): 5-step story (Procedure, Vessel, What matters, What to calculate, How far to trust), offline (rules extractor, Tier 1, stored traces). Calls Track H `render_vessel_hero` if importable, else a placeholder. Trust labels/counts from llm.trace (cap_of, LABELS); this setup's label is computed with cap_of (always hypothesis here). Bar chart: 5 knobs, one-at-a-time step, effect in output units, whiskers from p05/p95.
- app/home_data/*.json (new): committed snapshot of the 3 demo stories so the demo is instant (regenerate `python -m app.home`).
- app/dashboard.py: hook lines only (Home/Advanced outer tabs, selector row inside Advanced, sidebar collapsed, inner tabs keyed).
- tests/test_home.py, tests/home_app.py: 26 tests (all 5 steps x 3 scenarios, word limits, trust labels, tab order, snapshot freshness).
- docs/screens/CHECKLIST_home.md, docs/handoff/requests-j.md.
- Metrics: none scored; no new constants; no pre-registration needed. make test: 253 passed, 6 skipped, 1 xfailed.
- Not verified: no real browser screenshot was possible (headless Brave did not render Streamlit); layout fit at 1440x900 is by estimate; checklist covers it. Tab jump by session_state needs Streamlit tab state (1.66 ok).
- Scenarios: cvd_tube real_01, ampoule real_14, sorbent real_29 (no photoreactor procedure/rules exist). The tube headline output is the shape boundary (hypothesis-level model).
