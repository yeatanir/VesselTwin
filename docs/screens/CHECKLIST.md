# Dashboard visual checklist (Safari, by eye)

Start the app (from the repo root):

```
make dashboard
# or: /Users/yeatanir/miniconda3/envs/research/bin/python -m streamlit run app/dashboard.py
```
Open http://localhost:8501 in Safari. Switch theme with Streamlit menu (top right, three dots) > Settings > Theme: Light, then Dark.
Do the whole list once per theme. Mark `[x]` when fine; write what is wrong next to it otherwise.
The automated side (AppTest, no exceptions on any vessel/tier/trace question) runs in `make test`; this list covers only what a test cannot see.

## Every tab, both themes (Light [ ]  Dark [ ])
- [ ] Body text and captions readable (no grey-on-grey; the small "evidence:" and caption lines are legible)
- [ ] Coloured words (`synthetic`, `sourced`, `stated`, `default`, `edited`) readable on the background, and each also has a word, not colour alone
- [ ] No horizontal scrollbar on the page; no text running outside its box
- [ ] No chart clipped at the right edge or with cut-off axis titles; axis text readable
- [ ] No leftover loading skeletons / spinner after 10 s

## Header and sidebar
- [ ] Three dropdowns in a row: Vessel template, Chemistry set, Solver tier
- [ ] Orange "Highest tier available" line readable
- [ ] Sidebar: procedure box, Extract button, parameter groups open/close; each parameter shows a status badge line (synthetic / stated / sourced / default / edited)
- [ ] Number inputs are not truncated (value visible)

## Results tab (repeat for each of the 5 vessels: cvd_tube, ampoule, flask, sorbent, photoreactor)
- [ ] Regime metric with margin, and under it a status line: "synthetic inputs · computed, tier 0" (orange) or "sourced inputs · ..." (green)
- [ ] "tier0 number" table readable, with a status caption under it
- [ ] Tier 1: passport chart (blue bars with diamonds, symlog axis) not clipped; table below has a `status` column
- [ ] cvd_tube: three profile charts + dashed amber substrate line visible; shape-vs-position chart with band; knob table
- [ ] ampoule / flask: line chart present, title ends with orange "synthetic"
- [ ] sorbent: breakthrough curve present
- [ ] photoreactor: a "Model-declared plots" section with a bar chart (or the photon-flux-vs-depth line + band once Track E is merged) and notes underneath
- [ ] Tier 0 and Tier 2 selected: Tier 0 shows only the regime table; Tier 2 shows the info box or cached JSON

## Brief tab (cvd_tube and ampoule)
- [ ] Orange/yellow "SYNTHETIC" warning visible
- [ ] Conditions table and ranking table readable; ranking bar chart colours distinguish cheap / medium / expensive and are readable
- [ ] Download buttons (markdown, JSON) visible

## Reasoning trace tab (pick question s01, s03, s11 and one "not modellable", e.g. s02)
- [ ] Label line says "Scripted replay (not model-driven)" (or "Recorded run · <model> · <date>" if a recorded run exists); a replay is never worded as live
- [ ] Timeline: each step has a numbered circle with the step title, a dashed vertical connector between steps, circles/lines visible in dark theme
- [ ] Label pills (hypothesis / uncertain / benchmarked) readable, each with a different symbol
- [ ] Literature step: every excerpt has "verified excerpt" (blue) or "unverified excerpt" (orange) with the reason; the "N of M excerpts verified" line is present
- [ ] Vessel step: passport chart and knob-effect bar chart (blue bars, orange whiskers) not clipped
- [ ] Compare step: banner colours readable (red-orange disagree, orange fragile, blue agree). A SIGN FLIP banner never appears on stored data (it is only exercised in tests)
- [ ] Compare step: p05..p95 band chart present for modellable questions
- [ ] "Replay: show steps up to" slider hides later steps
- [ ] "What this does not show" box readable, quotes of tiers.json status visible
- [ ] If a "Recorded model runs" selector is present: step boxes show tool, args and output as code blocks, not clipped

## Credibility tab
- [ ] "Last make test" metric shows N / N passed
- [ ] Pivot and detail tables readable; PASS/FAIL words visible
