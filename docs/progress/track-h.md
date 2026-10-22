# Track H progress (vessel view)
Branch track-h from origin/polish. Deadline Oct 21 17:00 ET. No solver runs started by this track.
Files I touch: app/vessel_view.py, app/viz/ (new), app/dashboard.py (one hook line), tests/test_vessel_view.py, scripts/export_fields.py, data/viz_cache/*, docs/screens/CHECKLIST_vessel_view.md, docs/handoff/requests-h.md, docs/progress/track-h.md
Source cases (read-only, existing results) live in the earlier session scratchpad; foamToVTK only.

## Done
- scripts/export_fields.py + data/viz_cache/*.npz (6 files < 0.5 MB each, from foamToVTK on copies of stored cases; foamToVTK ran 6 times, each finished in seconds, no long PIDs; the Firefox headless screenshot helper was PID 56554 and exited).
- app/viz/{schematics,profiles,fields}.py, app/vessel_view.py (render + render_vessel_hero), tests/test_vessel_view.py, docs/screens/CHECKLIST_vessel_view.md.
- dashboard.py: names list gains "Vessel view" (modified line) + one `with tabs["Vessel view"]` line (added).
- Redesigned after user feedback: picture-first, one line per panel, Details expanders closed.
