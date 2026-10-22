# Track B progress (branch track-b, worktree ../vt-track-b)

Scratch: /private/tmp/claude-501/-Users-yeatanir-OSI-Hackathon/9eda40b9-b622-4dd7-b227-9e90bef27ef6/scratchpad/trackB/
OpenFOAM: `source /Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc` (mounts /Volumes/OpenFOAM-v2512).
PID 29124 (leftover ampoule run) checked Oct 20 23:12 ET: not running. All 4 ampoule mesh points have L0/L1/L2 results in
scratchpad/ampoule2/mout_*.json (the "unfinished" note in docs/ampoule_cfd_verification.json is stale), so no duplicate run is needed.

## Files I will touch (declared before first edit)
- docs/progress/track-b.md, docs/prereg/track-b.md, docs/handoff/requests-b.md
- tier2/openfoam.py (flask wiring only; no change to _fv), tier2/verification/** (new: tier0.py, gci.py, gci.json, b1 regression, scoring scripts/results), tier2/run_flask.sh only if needed
- tier2/flask.py (only if a bug blocks Np extraction), tests/test_tier2.py, tests/test_tier2_flask.py, tests/test_verification_b.py (new)
- surrogate/** (new surrogate/correction.py; existing ampoule.py/tube.py kept), tests/test_surrogate_ampoule.py, tests/test_surrogate_tube.py
- vessels/ampoule/**, vessels/flask/** and their tests (only if needed; default: read-only)
- docs/flask_closure_np.json (new closure entry; wiring requested via handoff)

## Log
- 2026-10-20 23:15 ET: worktree created, solver ampouleBoussinesqFoam rebuilt. Read rules + code.
- 23:2x ET: B1 DONE. Re-ran the 4 coarse-level (L0) ampoule mesh-study cases (diffusion, weak, tilted, strong) with the current tier2/openfoam.py: f_CFD bit-identical to stored (0.000 % change). `_amp` has its own fvSchemes and never calls the shared `_fv`; ampoule data need no regeneration. (b1 output: scratchpad/trackB/b1/b1_result.json)
- Pre-registration committed a060deb (docs/prereg/track-b.md). Flask wired in tier2/openfoam.py (write_case/read_results dispatch + RUNNER map) with a test.
- Flask Np mesh study started 23:16 ET (steady stage only, tier2/verification/flask_np_run.sh), launcher wrapper PID 34176 (xargs -P3), solver PIDs 34674 34675 34678 (w400_c13.5, w800_c9, w400_c9); queue in scratchpad/trackB/flask/order.txt, each case writes run.pid. Kill only by PID.
- NEXT: write tier2/verification/{tier0,gci,b2,b3}.py, run scoring once, GCI json, closure file, handoff requests, tests, make test, push.
- 23:2x-00:xx ET: B2, B3 scored once after pre-registration a060deb; B4 GCI table written; flask Np mesh study (4 meshes x 2 Re) done; closure file written; handoff requests written. All OpenFOAM processes finished (none running). No process of mine is left.
  Flask runs: wrapper PID 34176, solver PIDs 34674 34675 34678 (first wave), then 34921 and the later queue entries; all exited.

# FINAL REPORT (Track B)

## What changed, file by file
- `tier2/openfoam.py`: flask dispatch in `write_case` / `read_results` + `RUNNER` map (`_fv` untouched).
- `tier2/verification/`: `tier0.py` (tube Da_eff rule, ampoule stratification variants), `gci.py`, `gci_run.py`, `gci.json`, `b1_regression.py`, `b2_score.py`, `b2_results.json`, `b3_score.py`, `b3_results.json`, `flask_np_run.sh`, `flask_np_collect.py`, `data/` (ampoule finest-level mesh results, flask Np raw).
- `surrogate/correction.py` (new multi-fidelity GP) + saved models `surrogate/data/corr_*.json` (old `surrogate/ampoule.py`, `tube.py` unchanged).
- `docs/prereg/track-b.md`, `docs/handoff/requests-b.md`, `docs/flask_closure_np.json`, this file.
- Tests: `tests/test_verification_b.py` (NASA/Roache worked example, exact-order GCI, f_variant reproduces shipped f, Da_eff limits), `tests/test_tier2_flask.py` (flask reachable through tier2.openfoam; blockMesh test skips without OpenFOAM).

## Metrics before -> after (pre-registration commit a060deb; scored once)
B1 regression (4 ampoule L0 cases re-run with current tier2/openfoam.py): 0.000 % change in f_CFD (bit-identical). `_amp` has its own fvSchemes and never uses `_fv`; no regeneration needed.
Also: PID 29124 was not running; the "unfinished" ampoule finest mesh level had already been completed (scratch results existed, stored docs JSON was stale). No duplicate run.

B2 surrogate, leave-one-out, abs rel error vs CFD (target median <= 5 %; MISSED everywhere):
| set | n | surrogate median / mean | <=5 % / <=20 % | Tier 1 alone median / mean | <=5 % / <=20 % |
| ampoule f, post-fix Tier 1 (optimistic: fix chosen after all 60 results) | 60 | 26.8 / 46.6 % | 10 / 37 % | 31.6 / 47.4 % | 25 / 38 % |
| same, cases not near the Tier 1 fit scan | 56 | 26.8 / 47.4 % | 11 / 38 % | 30.6 / 47.9 % | 25 / 39 % |
| ampoule f, pre-fix Tier 1 (aa4e98c, sweep unseen) | 60 | 30.7 / 36.5 % | 22 / 43 % | 23.6 / 46.7 % | 27 / 45 % |
| same, not near fit scan | 56 | 28.9 / 35.4 % | 23 / 46 % | 21.6 / 46.2 % | 27 / 46 % |
| tube Mo:S | 40 | 30.0 / 93 % | 5 / 40 % | 168 / 421 % | 0 / 2.5 % |
| tube supersat. (wall T) | 40 | 36.3 / 93 % | 12.5 / 20 % | 73 / 215 % | 2.5 / 15 % |
| tube supersat. (gas T) | 40 | 34.3 / 74 % | 7.5 / 30 % | 81 / 110 % | 0 / 5 % |
| tube p(MoO3) | 40 | 36.3 / 92 % | 10 / 22.5 % | 73 / 215 % | 2.5 / 15 % |
| tube p(S2) | 40 | 24.1 / 35 % | 12.5 / 45 % | 89 / 89 % | 2.5 / 7.5 % |
Reading: for the ampoule the correction adds essentially nothing (better on the post-fix baseline by ~5 points median, worse on the clean pre-fix baseline median); for the tube it cuts the median error 2-5x but is far from 5 %.
y = log10(CFD/Tier 1) range: ampoule 1.5-1.6 decades (learnable by the 3-decade criterion), tube Mo:S 3.5, supersat. wall 4.1, gas 6.6, p(MoO3) 4.0 decades (flagged NOT learnable from 40 cases), p(S2) 2.0. Predictive band calibration (LOO): +-1 sigma holds 55-63 % (ampoule) / 78-83 % (tube) of truths, +-2 sigma 78-90 % / 90-93 %. Leakage: ampoule 4 of 60 cases (s38, s43, s46, s51) lie in the Tier 1 fit-scan region (|tilt|<=10, 12<=L<=18); all-case post-fix Tier 1 is optimistic; no tube Tier 1 constant is tagged as fitted to CFD (not proof).

B3 Tier 0 regime agreement with the CFD label (agent-chosen conventions, see prereg: tube = >= 63 % of boat MoO3 taken by walls before substrate; ampoule = f_CFD > 1.1 or 1.2):
- Tube (n=40; CFD 17 transport, 23 reaction, 0 heat): base 26/40 = 65 % (confusion: 17/0 transport row, 14 reaction rows wrongly transport, 9 right); new Da_eff rule at the pre-set, unfitted threshold 1: 37/40 = 92.5 % (misses: 2 transport called reaction at Da_eff 0.90 and 0.94, 1 reaction called transport at 2.08). Fitted-threshold half split (5 seeds): base 69.5 +- 3.9 %, new 97.9 +- 2.6 % (fitted log10 thresholds about -0.1 to -0.3, i.e. near 1). Caveat: the Da_eff form was designed after reading that the 14 misses all went one way and the diagnosis (walls hotter than the boat take little up), so it is not blind; no parameter was tuned on the 40 cases. The old Da already used Sh = 3.66; the bias was the missing driving force, not Sh. Sh = 3.66 is the constant-wall-temperature Nusselt value carried by the heat/mass analogy (opened: ANSYS Innovation Space handout S1-LT4-C3-L2 for Nu = 3.66 and the Hausen entrance correlation; Wikipedia Sherwood number for the analogy); entrance effects not included.
- Ampoule (n=60): shipped (duct-height stratification, threshold 1.1) 81.7 % at CFD>1.1 and 75.0 % at >1.2 (reproduced). Legacy L^3 scale (pre-fix) 65.0 % / 71.7 %; no stratification term at all 80.0-81.7 % / 73-78 %. Held-out (5 seeds, closure+threshold chosen on one half): CFD>1.1: chosen 79.3 +- 4.9 % vs shipped 83.4 +- 2.6 %, legacy 68.3 +- 9.4 %, none 81.4 +- 2.8 %; CFD>1.2: chosen 75.9 +- 2.2 % vs shipped 71.7 +- 2.6 %, legacy 70.3 +- 4.7 %, none 69.7 +- 3.4 %. So the fix's gain over the old code is real in held-out halves, but it is mostly removal of a harmful term: a model with no stratification term does as well. Most remaining errors are Tier 0 predicting convection where CFD sees diffusion (10 false positives at 1.1). Confusion matrices in `b3_results.json`.

B4 GCI (`tier2/verification/gci.json`, Roache, Fs 1.25 / fallback 3.0):
- ampoule f_CFD, 3 meshes (r = 2): diffusion D10 p=2.04, GCI 0.0 %; weak D20 p=2.01, 0.5 %; tilted D25/30 deg p=1.6, 2.1 % (medium->fine change 3.4 %); strong D40/90 deg: unsteady (oscillation 0.75, drift 0.18 at fine), GCI 13 % not meaningful. The 2 % target is met for diffusion and weak, not for tilted (3.4 %) or strong.
- tube (stored M1-M3): 0.8-13 %, most oscillatory or p outside range so Fs = 3 (flagged); only the hot/low-flow point gives p ~0.5 (first order).
- flask Np_torque, water 400 rpm, cells/cm 4, 6, 9, 13.5 = 1.250, 0.987, 0.905, 0.956 (non-monotone): fine triplet GCI 14.0 % (Fs 3, flagged); the old triplet 4-6-9 alone would have said p=3.05, GCI 5.2 % (misleading). 800 rpm: 1.262, 0.958, 0.873, 0.856, GCI 5.2 % (p=4.2 out of range, Fs 3). Np_dissip does not converge (0.30 -> 0.70 with refinement), not used.

B5: flask Tier 2 reachable via `tier2.openfoam.write_case('flask', ...)`; closure `docs/flask_closure_np.json`: single-point values (not a curve) Np = 0.956 (band 0.82-1.09) at Re = 4636 and 0.856 (0.81-0.90) at Re = 9271; Tier 1 gives 0.515 / 0.508, so CFD/Tier 1 = 1.86 / 1.69. Geometry caveats in the file (frozen rotor, equal-volume cylinder, wall functions).

## Failed / abandoned
- Surrogate 5 % target missed on every output; two (tube Mo:S/supersat) are not learnable from 40 cases by the pre-set criterion.
- Mesh 2 % target: met only for 2 of 4 ampoule points; flask Np not converged to better than ~14 % at 400 rpm; tube first-order boat singularity unchanged (Track A's case).
- No tube or ampoule CFD regenerated (B1 showed no need). Tube Tier 1 not modified (not mine); wiring of new Tier 0 only requested.

## New or changed constants (source tags)
- Sh = 3.66 reused (existing ParamDef), source above (Nu = 3.66, constant wall temperature; analogy not verified for MoO3 in a mass-transfer text).
- GCI Fs = 1.25 / 3.0 per Roache via NASA Glenn WIND tutorial (opened); Roache's own papers and ASME V&V 20 were NOT opened.
- Ampoule leakage window (|tilt| <= 10, 12 <= L <= 18) is my convention. No physical constants added; flask Np values are computed (OpenFOAM), status "computed".

## Requests left: `docs/handoff/requests-b.md` (R1 tube tier0 change with exact code, R2 GCI in bands, R3 tiers.json text for Track F, R4 closure wiring, R5 surrogate wiring).
