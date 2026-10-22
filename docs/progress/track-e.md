# Track E progress
Worktree: /Users/yeatanir/OSI Hackathon/vt-track-e  branch track-e
## Files I will touch
- vessels/photoreactor.py, tests/test_photoreactor.py
- vessels/sorbent/* (module), tests/test_sorbent_physics.py
- bench/photoreactor/*, bench/sorbent/*
- docs/prereg/track-e.md, docs/progress/track-e.md, docs/handoff/requests-e.md
(no presets/ edits: setups live in bench/photoreactor/setups.json)
## Log
- worktree created from main ac9879f
- E1 literature: H&P 1956 PDF read as page images (Table 5 p.526, text p.533 verified on images). Candidate setups opened:
  USED: Saenz et al., Heliyon 2024, doi 10.1016/j.heliyon.2024.e31309 (PMC11145495 full text; QPB cuvette + integrating-sphere cuvette).
  REJECTED after opening: Riddell 2022 RSI doi 10.1063/5.0087107 (actinometer conc., LED power, vessel size not stated);
  Open Res Europe 2024 doi 10.12688/openreseurope.16812.2 (16-LED array in reflective aluminium fixture + quartz tube: not a slab, model cannot represent it; only n_quartz used);
  Li et al. BJOC 2024 doi 10.3762/bjoc.20.9 (LED power/geometry in SI, not opened); Schuurmans RCE 2025 (flux from ray tracing, not independent).
  BLOCKED (403, not opened, not used): Wiley ChemPhotoChem doi 10.1002/cptc.202200044, RSC Photochem Photobiol Sci c7pp00401j, Thorlabs M365LP1 datasheet.
- Model edits done in vessels/photoreactor.py (measured-irradiance lamp mode, diffuse illumination, n_wall, V_total); old tests pass.
- NEXT: commit prereg + setups + scorer BEFORE running scorer; then score; tests; extras plot; push. make test takes >2 min (run in background).
- MISTAKE: `pip download pyiast` run inside the worktree dropped ~100 MB of wheels (numpy, scipy, pandas, matplotlib, pillow, ...) that `git add -A` committed and pushed to origin/track-e in commit 6685a36..941b772. Removed in a follow-up commit; they remain in history. A history rewrite (git filter-branch + force push of track-e) was blocked by the permission classifier; needs the user's decision. pyiast itself is installed only in the scratch dir (scratchpad/trackE/pylib), never in the shared env.
- Part 1 pushed (photoreactor scored: QPB ratio 0.879, IS ratio 0.688). make test: 157 passed, 5 skipped at that point.

# FINAL REPORT (Track E)

## What changed, file by file
- `vessels/photoreactor.py`: new lamp mode `lamp_geom="measured"` (+ `E_meas_mW_cm2`); `illum` collimated/diffuse (exact unpolarised Fresnel + Snell, cosine-weighted quadrature); `n_wall` override; `V_total_cm3`; quartz n 1.46 -> 1.485 (sourced); mixing-cap parameter relabelled UNSOURCED heuristic; `extras` now has `photon_flux_vs_depth` (p05/p50/p95) and `notes` (mixing UNSOURCED, dT upper bound, what was validated). Defaults otherwise unchanged.
- `tests/test_photoreactor.py`: +4 tests (two known-answer comparisons with pre-registered tolerances, diffuse/measured-mode analytic checks, extras band).
- `bench/photoreactor/{setups.json,score.py,results.json,__init__.py}`: sourced setups, scorer, result.
- `bench/sorbent/{score.py,iast_check.py,results.json,__init__.py}`; `tests/test_sorbent_physics.py` +4 tests (IAST limit, IAST vs EDSL, CALF-20 unchanged, 13X hold-out xfail). `vessels/sorbent/*` not changed.
- `docs/prereg/track-e.md` (Part 1 + Part 2 + Amendment 1), `docs/handoff/requests-e.md`, this file.

## Metrics, before -> after (pre-registration commits: Part 1 6685a36; Part 2 50504c3; Amendment 1 941b772)
Photoreactor, predicted/measured initial actinometer slope (Saenz 2024 Table 2), n = 2 setups (one paper, one lab), before: no comparison existed.
- collimated QPB cuvette: ratio 0.879 (MC p05-p95 0.84-0.92), tolerance factor 1.25 -> PASS. Main uncertainty: quantum yield (1.21 H&P vs 1.26 used by the paper gives 0.915). wall T 0.945 vs paper 0.947.
- integrating-sphere (diffuse) cuvette: ratio 0.688 (0.66-0.72), tolerance 1.5 -> PASS. Model under-predicts because it has no lensing/edge entry; the paper itself reports an unexplained eta = 1.21.
- Only two geometries from one paper: the ">= 2 measured photon fluxes" criterion is met formally, not independently. Lamp power -> irradiance is NOT validated (measured irradiance used).
13X (Wilkins 2017 Fig 4.11a, n = 2 flows, deterministic):
- baseline t50 error -37.9 % (y=0.15) / -39.1 % (y=0.5); T_peak 95.9/112.6 C vs 68.5/79.0 C.
- Method 1 (registered: fit t50 error to zero): no root in [0.5, 300]; boundary h_in = 292 gives -7.5 / -12.5 %. Not a pass.
- Method 2 (Amendment 1, chosen after seeing the t50 grid: fit h_in = 72.86 W/m2/K on the y=0.15 peak temperature): fit case t50 -9.5 %; HELD-OUT y=0.5: t50 -15.6 % (threshold 15 %: FAIL by 0.6 points), T_peak 81.8 vs 79.0 C (threshold 10 K: pass). Reverse (fit on y=0.5, h_in 95.4): held-out y=0.15 t50 -8.8 %. Not adopted into the model (adoption rule), requests-e.md says how to adopt.
- Re_p of the 13X column is 0.16-0.33 (d_p = 2 mm ASSUMED in source data); no open-access wall-Nu correlation covering Re_p < 1 was found/opened, so no correlation was used.
- CALF-20 unchanged (not touched): -3.3, +1.9, +9.8 % from a clean state.
CO2/H2O competition (n = 2 points, Wilkins 2017 Table 4.5): EDSL CO2 -17 % / -41 %, H2O -1 % / -7 %. IAST (pyIAST 1.4.3; confirmed by an independent scipy IAST in bench/sorbent/iast_check.py): CO2 -100 % / -100 % (0.001 vs 2.16, 0.000 vs 2.46 mol/kg), H2O +36 % / +18 %. Worse; model not switched. No isotherm refit.

## Failed / abandoned
- No second independent literature setup (Riddell 2022 under-specified; Open Res Europe 2024 is a reflector array around a tube; Li 2024 BJOC needs SI; Wiley/RSC/Thorlabs pages 403).
- Method 1 13X fit had no root; Method 2 missed its threshold marginally. Wall correlation not used (validity range).
- Mixing-limit heuristic: no source found, relabelled. Temperature rise: kept, labelled upper bound (adiabatic-style, synthetic h_cool).
- MISTAKE: a `pip download` in the worktree committed ~100 MB of wheels to the branch history (commits 6685a36-941b772); removed in ef1008d but still in history. History rewrite was blocked by the permission classifier; user decision needed (git filter-branch + force-push of track-e only, or squash when merging).

## New or changed constants and sources
- phi(365/6 nm) = 1.21: Hatchard & Parker 1956 (doi 10.1098/rspa.1956.0102) p.526 Table 5, 'recommended value' column, read from page image; alt 1.26 (same table, thermopile column; equals Saenz's value).
- eps_A >= 333 M-1cm-1 (1 cm, 6 mM absorbs >= 99 %): H&P p.533 text, image-verified; derived bound, H&P prints no eps table. Fe2+/phenanthroline: 1.81e-6 mol per 20 mL -> OD 1.0/cm (p.533), eps510 = 11050 (derived), not needed for scoring.
- Saenz et al. 2024 (doi 10.1016/j.heliyon.2024.e31309, PMC11145495): LED 365 nm FWHM 9 nm; quartz cuvette 10x10 mm, 1.25 mm wall, n = 1.56, T = 0.947; V = 4.50 cm3, S = 3.375 cm2 (QPB) / 13.50 cm2 (IS); 6 mM; slopes a_QPB 0.00161 +/- 0.00003, a_IS 0.0078 +/- 0.0001 %/(umol m-2) (Table 2).
- quartz n = 1.485 default: Open Res. Europe 2024 Table 1 (doi 10.12688/openreseurope.16812.2). n_liq = 1.33 is an assumption (no opened source). All other wall indices/cutoffs, f_heat, eta_elec, h_cool, mix_revs remain synthetic/recalled.
- 13X h_in: unchanged (4.0, Wilkins 2017 thesis value for one column); fitted 72.86 reported only.

## Requests left
See `docs/handoff/requests-e.md` (Track C plot schema, Track F presets + tiers.json text, sorbent adoption decision and the `_PAT` cache note).
