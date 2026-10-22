# Track N progress (branch track-n from origin/polish 3de09fc)

Files I touch: vessels/cvd_tube/furnace.py (new), vessels/cvd_tube/__init__.py (minimal: import furnace, add FDEFS copies with sigma 0 plus the `thermal_model` switch, dispatch in `twall` and a one-line `apply` at the top of `march`/`tier0`),
bench/track_n/ (new), bench/track_n_score.py (new), tests/test_track_n.py (new), docs/prereg/track-n.md, docs/track_n_results.md, docs/progress/track-n.md, docs/handoff/requests-n.md.
Nothing else. No new OpenFOAM solver runs (only foamToVTK on stored cases, one at a time), no API keys, no Edison credits.

## Log
- Oct 21: read shared rules, status, Track K/M results, all of vessels/cvd_tube, tier2/openfoam.py tube builder. Findings: the stored CFD imposes the legacy twall profile as a Dirichlet inner-wall T, constant mu (at furnace T) and constant Pr, gravity (0 0 0) (no buoyancy in the CFD), boats and substrate as fixed-T walls. So CFD can test only the gas-side part (N3), not quartz/element coupling (N2/N4).
- extract_cfd (foamToVTK on stored cases, sequential) started, PID 71294, log /private/tmp/claude-501/n_scratch/extract.log
- Oct 21: tests (20) pass, score script written, prereg committed (d2d6c16). Next: run --score --write once, write docs/track_n_results.md, handoff, make test, push track-n.
- make test rerun started (PID of make printed above; pytest child to be killed only by that parent). dashboard crashed on a string ParamDef: wall_profile_table moved out of ParamDefs (extra values key).
- Oct 21: SCORED once (bench/track_n/results.json; Momeni re-run after the table move is identical). Results in docs/track_n_results.md. CFD 52 cases: energy_2d NIST 45 pass, const props 49, graetz_1d 29, legacy 35; Momeni FAIL +143 K (as predicted); no measured-data paper usable. Post-hoc matched-ramp diagnostic in bench/track_n/posthoc.json. Handoff requests written. Next: make test green, commit, push track-n.

## Final report (Track N)
- Files: vessels/cvd_tube/furnace.py (new), vessels/cvd_tube/__init__.py (import, thermal_model ParamDef + sigma-0 copies of FDEFS, dispatch in twall, hook at top of march and tier0), bench/track_n/ (capture_reference.py, default_reference.json, extract_cfd.py, cfd_extract.json, momeni_digitized.json, results.json, posthoc.json), bench/track_n_score.py, tests/test_track_n.py (20), docs/prereg/track-n.md, docs/track_n_results.md, docs/handoff/requests-n.md.
- Metrics (n = 52 stored CFD cases, pre-registration 851210c/d2d6c16): overall pass (bulk and centreline within 25 K, velocity within 15 %, both stations) legacy 35 -> furnace energy_2d 45 (49 with CFD constant properties; graetz_1d 29). Momeni 2018 simulated gas peak: furnace +143 K (fail), legacy +144 K (fail).
- Failed/abandoned: no measured in-tube gas or substrate T found and openable; quartz emissivity source not found (synthetic); wall_profile_table moved out of ParamDefs (dashboard crash on a string param).
- Constants and sources: see docs/track_n_results.md (sourced: quartz k, transmission, cutoff from GE 124 figures, NIST argon, Hausen/3.66, entrance lengths, Taylor-Aris, 20 K/min; everything else synthetic).
- Requests: docs/handoff/requests-n.md.
