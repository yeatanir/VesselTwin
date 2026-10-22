# VesselTwin: status after the freeze (Oct 21, 2026)

Integration branch `integration` (from `main` ac9879f). Merged: track-b, track-a, track-e (squashed), track-c. Supersedes `docs/status/status_oct20.md` and `docs/status/problems_oct20.md`. Every number below is copied from the track reports (`docs/progress/track-*.md`); nothing new is claimed here. Pre-registration files: `docs/prereg/track-{a,b,c,e}.md`.

Test suite on the merged branch: 218 passed, 6 skipped, 1 xfailed (`make test`, about 3 min). `make dryrun`: 7 of 7 steps pass, 7.3 s compute.

## Metrics, before -> after

| Track | Metric | Before | After | n | Pre-reg commit |
|---|---|---|---|---|---|
| A | Sensitivity direction, original 8 items (uncertain counted wrong) | model 4/8 (5/8 as published) | model 2/8; blind no-tool 6/8; always-increase 4/8 | 8 | 925b072 (+ addendum 126aa74) |
| A | Same, confident calls only | - | model 2/5 (3 abstentions); blind 6/8; always-increase 4/8 | 8 | 925b072 |
| A | Dev primary set (adds s08 gap) | - | model 3/9 (confident 3/6); blind 6/9; always-increase 4/9 | 9 | 925b072 |
| A | Held-out j1-j3 (one paper, Jian 2019) | - | model 0/3 (vapour-pressure law stops at the 1068 K melting point); blind 3/3; always-increase 2/3. Too small for any claim | 3 | 925b072 |
| A | Shape accuracy (M0 synthetic, M1 MACE, M2 DFT-Rosen Mo edge) | below majority baseline in the Oct 20 status | 0.50 = always-triangle baseline for all three; maps still collapsed | 14 (8 in scope) | 925b072 |
| B | Tube Tier 0 regime agreement with CFD label | 26/40 = 65 % | 37/40 = 92.5 % (unfitted threshold 1); half-split fitted 97.9 +- 2.6 % (5 seeds). Rule designed after seeing the miss mechanism: not blind. CFD label is an agent-chosen convention | 40 | a060deb |
| B | Ampoule Tier 0 agreement (f > 1.1 / f > 1.2) | legacy 65.0 % / 71.7 % | shipped 81.7 % / 75.0 %; a model with no stratification term gets 80.0-81.7 % / 73-78 %, so the fix is mostly removal of a harmful term | 60 | a060deb |
| B | Surrogate LOO median error (target 5 %, missed everywhere) | Tier 1 alone: ampoule 31.6 %, tube 73-168 % | ampoule 26.8 % (post-fix baseline) / 30.7 % (pre-fix baseline); tube 24-36 % | 60 ampoule, 40 tube | a060deb |
| B | GCI, ampoule f_CFD | mesh study incomplete | diffusion 0.0 %, weak 0.5 %, tilted 2.1 % (medium-fine 3.4 %), strong 13 % (unsteady, not meaningful) | 4 points | a060deb |
| B | GCI, tube / flask | tube mesh change 3-8 % | tube 0.8-13 % (mostly oscillatory, Fs = 3); flask Np_torque 14.0 % (400 rpm, non-monotone) and 5.2 % (800 rpm) | - | a060deb |
| B | Flask Np closure (single points, status computed) | Tier 1 Np about 0.51 | CFD 0.956 (0.82-1.09) at Re 4636, 0.856 (0.81-0.90) at Re 9271; CFD/Tier 1 = 1.86 / 1.69 | 2 points | a060deb |
| B | Ampoule regression after solver changes | - | 0.000 % change in f_CFD (4 cases); finest-level ampoule runs were already complete | 4 | a060deb |
| C | Excerpt support rule: quotes verified | all 48 shown as matching on two shared words | 10 of 48 verified (own paper 9/19, sibling benchmark paper 1/6, Edison answer sentences 0/23) | 48 | 1e226cb |
| C | Tests | 153 passed / 5 skipped | 196 passed / 5 skipped (track-c branch alone) | - | - |
| E | Photoreactor predicted/measured actinometer slope (Saenz 2024) | no comparison existed | collimated 0.879 (MC 0.84-0.92), tolerance x1.25 pass; diffuse 0.688 (0.66-0.72), tolerance x1.5 pass. Two setups, one paper, one lab | 2 | 6685a36 (Part 1) |
| E | 13X breakthrough t50 error | -37.9 % (y = 0.15) / -39.1 % (y = 0.5) | Method 1 (registered): no root, not a pass. Method 2 (Amendment 1, chosen after seeing the grid): fit case -9.5 %, held-out -15.6 % (threshold 15 %, fail by 0.6 points). NOT adopted: `h_in` stays 4.0 | 2 flows | 50504c3, 941b772 |
| E | CO2/H2O competition (Wilkins Table 4.5) | EDSL CO2 -17 % / -41 %, H2O -1 % / -7 % | IAST CO2 -100 % / -100 %, H2O +36 % / +18 %: worse, model not switched | 2 points | 50504c3 |
| E | CALF-20 breakthrough | -3.3, +1.9, +9.8 % | unchanged | 3 | - |

Track E pre-registration hashes refer to the track-e branch history; the integration branch carries that work as one squashed commit (the branch history holds about 100 MB of accidentally committed pip wheels, which are not in the integration tree). The registered text is in `docs/prereg/track-e.md`.

## Applied during integration (wiring and captions only)

- `tiers.json`: status text for cvd_tube, ampoule, flask, sorbent, photoreactor from requests-a, -b (R3) and -e.
- Track B R1: tube Tier 0 `Da_eff` replacement in `vessels/cvd_tube/__init__.py` (exact change given; matches `tier2/verification/tier0.py::tube_da_eff` to full precision on default parameters; tests pass).
- Presets `presets/photoreactor__saenz2024_{QPB,IS}_cuvette.json` from `bench/photoreactor/setups.json` (Track E request).
- Stale claims replaced with Track A's pre-registered numbers: `llm/trace.py` label text and shape/sensitivity limit strings, `app/trace_tab.py` caption, `docs/trace_schema.md`, and the 14 stored traces (regenerated with `python -m llm.trace`, which also picks up the new Track A parameters).
- `PLAN.md`: COMSOL removed. `docs/harness_snapshot.json` regenerated (219 entries).

## Still synthetic or unvalidated

- Tube Wulff/edge rates: S-edge constants, attachment constants, E_eff (0-2 eV) are synthetic; the shape map is set by them. The DFT Mo edge (Rosen 2018) is an option only. `T_boat_Mo_C` 200-300 C range is an unverified extrapolation. `m_MoO3_mg`, `m_S_mg`, `gap_mm` are user inputs (default unlimited / off).
- Photoreactor: lamp power to irradiance, mixing cap (unsourced heuristic), temperature rise (upper bound), n_liq = 1.33 (assumption), wall indices and cutoffs, f_heat, eta_elec, h_cool.
- Sorbent: heat-transfer coefficients (13X `h_in` = 4.0, thesis value for one column; particle diameter 2 mm assumed).
- Flask Np: single points from a frozen-rotor, equal-volume-cylinder, wall-function CFD; not converged better than about 14 % at 400 rpm; not wired into Tier 1.
- Agent traces: no genuine model-driven run was recorded (no local LLM backend). The trace tab says "Scripted replay (not model-driven)".

## What failed or was abandoned

- Track A: the model does not beat the blind baseline (2/8 vs 6/8 on the original items); held-out 0/3; shape map still collapsed. A5 threshold fallback not run (Wang 2014 closed access). No defensible S-edge DFT mapping. s02 and s12 stay unmodellable; s05/s06 give no change because supply is never inventory-limited with the current evaporation rate.
- Track B: 5 % surrogate target missed on every output; two tube outputs not learnable from 40 cases. 2 % mesh target met for 2 of 4 ampoule points. Ampoule Tier 0 fix gains little over no stratification term.
- Track C: no real agent run; the sign-flip banner never fires on the 14 stored items (kept, proven by a constructed test); original flaky-test source frame not reproduced (defensive fix at display).
- Track E: no second independent photoreactor setup (others under-specified, in SI, or 403); 13X fit missed its threshold; IAST rejected. Open note: the shared sparsity-pattern cache `_PAT` in `vessels/sorbent` moves CALF-20 t50 errors by up to +2 points depending on whether a 13X case ran first.

## Requests not applied (need an owner)

- B R2: GCI-widened uncertainty band in core/ and the Tier 2 Passport (larger change, per-case lookup).
- B R4: wire `docs/flask_closure_np.json` into flask Tier 1 (single Re point; may only override inside its validity range).
- B R5: dashboard use of `surrogate.correction.predict` with the label "LOO median error 27-36 %, target 5 % missed".
- A: dashboard captions (shape map, sensitivity benchmark) in `docs/handoff/requests-a.md`; placement in `app/` not specified. Hide or relabel the new `m_*_mg` parameters (default 1e6 = unlimited).
- A: sourced liquid-MoO3 vapour-pressure branch above 1068 K (separate task, not done here); Wang 2014 library copy.
- E: 13X `h_in` adoption (decision: not adopted); `_PAT` cache keying.
- C: dashboard has not been viewed by eye; user does it from `docs/screens/CHECKLIST.md`. Re-run `python -m llm.agent` once an MLX or other backend works.

## Update after the polish pass (Oct 21, afternoon)

Tracks G-L were run on top of the integration branch. Numbers below are from each track's own report; all MoS2 benchmark items are development data.

| Track | What | Result |
| --- | --- | --- |
| G | Provider-agnostic LLM backend, sidebar settings, Dockerfile, Codespaces config | 227 tests; Dockerfile untested (no Docker here); static GitHub Pages build judged not feasible |
| H | Vessel view: schematics, Tier 1 profiles, stored Tier 2 CFD fields | 28 tests; not seen in a real browser |
| J | Visual-first Home page, 5 steps | 26 tests; not seen in a real browser |
| I | Liquid-MoO3 branch (optional) and Momeni/Cao equilibrium edge model | Neither beats its baseline; shape accuracy 0.25 vs 0.50 always-triangle (registered version); corrected version abstains |
| K | Why substrate flux ignores boat temperature | Intended physics (wall uptake NTU about 11); no code change |
| L | Sensitivity rescored with each paper's stated geometry | Model 1/9 strict vs blind 6/9 (was 3/9); input gap: substrate temperature offset not stated by papers |

Conclusion carried into the presentation: the physics model does not beat a no-tool baseline on this literature set; the tool's value is the visible evidence trail, the labels, and the abstention.

### Track M (Oct 21, evening): reactive substrate sink and wall bracketing

Pre-registered (02e103f), scored once. A reactive substrate sink (irreversible sulfurization; all constants synthetic) removes the exact-zero flux for a hot substrate but does not rescue the benchmark: structural-ensemble calls score 1/9 strict (blind 6/9). At the default 12 cm the boat-temperature response (800-850 C, liquid law) returns only with a reflecting wall (d ln F = 0.86); every other wall variant gives 0 to 0.08. The wall-uptake closure is therefore the controlling assumption, and the stored CFD used a similar wall law, so it is not independent evidence. Earlier statements that "the CFD shows the same saturation" should be read with that caveat.

### Tracks N and O (Oct 21, night): furnace and flow physics and its panel

Track N (pre-registered, scored once, n = 52 stored CFD cases): the optional furnace model agrees with the stored CFD on the gas side in 45 of 52 cases (legacy 35); median substrate bulk-T error 2.0 K vs 9.3 K. The CFD imposes the wall temperature, has no gravity and no radiation, so it tests only the gas side and is not independent. The model did not reproduce Momeni 2018's simulated gas temperature (+143 K; legacy +144 K; a simulation, not a measurement). No measured gas or substrate temperature could be opened; boat and substrate absolute temperatures, the quartz network and buoyancy are not validated. Track O adds the 'Furnace and flow' tab (schematic, stacked temperature/velocity/regime plots, editable zones, pasted measured profile). 343 tests pass on `polish`.
