# Track O progress (branch track-o from origin/polish 35be0dc)

Files I touch: app/furnace_view.py (new), app/viz/furnace.py (new), app/dashboard.py (ONE hook: new tab 'Furnace and flow' in the Advanced group),
tests/test_furnace_view.py (new), docs/screens/CHECKLIST_furnace_view.md (new), docs/progress/track-o.md, docs/handoff/requests-o.md.
No OpenFOAM, no API keys, no Edison credits.

## Log
- Read shared rules, track N results, furnace docstring, vessel_view/viz, dashboard. Plan: plotly stacked subplots with shared x (cm from tube centre).
- Built app/viz/furnace.py (figures, takeaways, profile-text parser), app/furnace_view.py (tab, form with Update button, badges from bench/track_n/results.json, Details), dashboard hook, tests/test_furnace_view.py (11 pass), checklist. Rendered figures checked in headless Firefox at 1100 and 390 px. Update time about 1.1 s (n_mc=12).
- Design choices: four plotly figures with identical margins and x range (not one linked subplot) so takeaways sit under each; legacy mode shows legacy wall/gas, flow numbers still from the furnace calculation; pasted x measured from tube centre.
