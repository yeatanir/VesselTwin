# Track A results (scored once per docs/prereg/track-a.md; run 2, see note)

Generated from `bench/track_a/results.json` by `python -m bench.track_a_score --write`. Development set = s01-s14; held-out = j1-j3 (Jian 2019, one paper). Nothing here is tuned. n is tiny: one item is 11-33 points.

## Per-item calls (3-way)

| id | set | sweep | observable | label | model call (i=1,2,3 agree?) | blind | notes |
|---|---|---|---|---|---|---|---|
| s01 | dev | flow_sccm 10-160 | nucleation | increase | increase (i-robust) | increase |  |
| s03 | dev | flow_sccm 50-300 | domain | decrease | uncertain (i-robust) | non_monotonic |  |
| s04 | dev | flow_sccm 50-150 | coverage | increase | uncertain (i-robust) | non_monotonic |  |
| s05 | dev | m_MoO3_mg 10-30 | layers | class_change | no_change (i-robust) | increase | secondary: class_change non-shape |
| s06 | dev | m_S_mg 100-400 | domain | class_change | no_change (i-robust) | non_monotonic | secondary: class_change non-shape |
| s07 | dev | T_furnace_C 650-800 | coverage | class_change | increase (i-robust) | increase | secondary: class_change non-shape |
| s08 | dev | gap_mm 2-10 | layers | decrease | decrease (i-robust) | non_monotonic |  |
| s09 | dev | T_boat_Mo_C 200-400 | nucleation | increase | no_change (i-robust) | increase | zero_flux (no deposition at any sweep point); 200-300 C is an unverified extrapolation of the vapour-pressure law |
| s10 | dev | T_furnace_C 700-850 | nucleation | decrease | uncertain (i-robust) | decrease | range assumed; E_eff 0-2 eV synthetic |
| s11 | dev | T_boat_S_C 180-300 | shape | class_change | no_change | class_change |  |
| s13 | dev | T_furnace_C 750-850 | coverage | decrease | non_monotonic (i-robust) | decrease |  |
| s14 | dev | boat_area_MoO3_cm2 1-4 | coverage | increase | increase (i-robust) | increase | range assumed |
| j1 | heldout | T_boat_Mo_C 800-825 | domain | increase | no_change (i-robust) | increase | flux clamped at MoO3 melting point 1068 K in the vapour-pressure law |
| j2 | heldout | T_boat_Mo_C 825-850 | domain | decrease | no_change (i-robust) | decrease | flux clamped at MoO3 melting point 1068 K in the vapour-pressure law |
| j3 | heldout | T_boat_Mo_C 825-850 | nucleation | increase | no_change (i-robust) | increase | flux clamped at MoO3 melting point 1068 K in the vapour-pressure law |
| s02, s12 | dev | - | - | - | excluded | - | transverse substrate coordinate; model is 1-D along the tube; MoO3 film thickness: needs film area and MoO3 density (no sourced values) |

## Tables (n in each)

| table | system | n | correct | (i) acc, uncertain = wrong | (ii) acc on confident calls | abstain rate |
|---|---|---|---|---|---|---|
| T1 dev, primary items (s01 s03 s04 s08 s09 s10 s11 s13 s14) | call | 9 | 3 | 0.33 | 0.50 (n=6) | 0.33 |
| T1 dev, primary items (s01 s03 s04 s08 s09 s10 s11 s13 s14) | blind | 9 | 6 | 0.67 | 0.67 (n=9) | 0.00 |
| T1 dev, primary items (s01 s03 s04 s08 s09 s10 s11 s13 s14) | always_increase | 9 | 4 | 0.44 | 0.44 (n=9) | 0.00 |
| T2 original 8 (s01 s03 s04 s09 s10 s11 s13 s14) | call | 8 | 2 | 0.25 | 0.40 (n=5) | 0.38 |
| T2 original 8 (s01 s03 s04 s09 s10 s11 s13 s14) | blind | 8 | 6 | 0.75 | 0.75 (n=8) | 0.00 |
| T2 original 8 (s01 s03 s04 s09 s10 s11 s13 s14) | always_increase | 8 | 4 | 0.50 | 0.50 (n=8) | 0.00 |
| T2 original 8 (s01 s03 s04 s09 s10 s11 s13 s14) | old model (before) | 8 | 5 | 0.50 (4/8 with its 1 uncertain flag as wrong; 5/8 = 0.62 as published) | - | 0.12 |
| T4 HELD-OUT j1-j3 (one paper; too small for any claim) | call | 3 | 0 | 0.00 | 0.00 (n=3) | 0.00 |
| T4 HELD-OUT j1-j3 (one paper; too small for any claim) | blind | 3 | 3 | 1.00 | 1.00 (n=3) | 0.00 |
| T4 HELD-OUT j1-j3 (one paper; too small for any claim) | always_increase | 3 | 2 | 0.67 | 0.67 (n=3) | 0.00 |

T3 secondary (class_change on non-shape items, correct iff non_monotonic): s05 -> no_change (wrong); s06 -> no_change (wrong); s07 -> increase (wrong).

## Shape benchmark (14 cases; in_scope n=8), each configuration once

| configuration | n | accuracy | majority baseline (triangle) | accuracy with abstentions wrong | abstain rate | predicted classes |
|---|---|---|---|---|---|---|
| M0_default_synthetic (in_scope) | 8 | 0.50 | 0.50 | 0.38 | 0.12 | {'triangle': 8} |
| M0_default_synthetic (all) | 14 | 0.50 | 0.50 | 0.43 | 0.14 | {'triangle': 14} |
| M1_MACE_kink (in_scope) | 8 | 0.50 | 0.50 | 0.00 | 1.00 | {'triangle': 8} |
| M1_MACE_kink (all) | 14 | 0.50 | 0.50 | 0.00 | 0.86 | {'triangle': 14} |
| M2_A1_dft_rosen_Mo_MACE_S (in_scope) | 8 | 0.50 | 0.50 | 0.50 | 0.12 | {'triangle': 8} |
| M2_A1_dft_rosen_Mo_MACE_S (all) | 14 | 0.50 | 0.50 | 0.50 | 0.07 | {'triangle': 14} |

## Shape-map collapse (default tube, 40 positions)

| configuration | classes | boundary (cm from boat) |
|---|---|---|
| M0_default_synthetic | {'triangle_Mo': 29, 'triangle_S': 11} | 18.246794871794872 |
| M1_MACE_kink | {'triangle_Mo': 40} | nan |
| M2_A1_dft_rosen_Mo_MACE_S | {'triangle_Mo': 40} | nan |
| diagnostic_dft_rosen_Mo_synthetic_S | {'triangle_Mo': 29, 'triangle_S': 11} | 18.246794871794872 |

s11 (sulfur-boat T, class change): M0 = no_change; M1 = uncertain; M2 = no_change.

## Notes

- **Run 1 vs run 2.** The first full run used a ParamDef sigma on `dE_Mo_dft_eV` that added one RNG draw per Monte Carlo sample for every configuration, shifting the MC stream of M0/M1 (and the stored shape benchmark: `test_shape_bench` failed). I made the sigma a scoped switch (`wulff.with_sigma`) and re-ran. Sensitivity calls and M2 are identical in both runs; M0/M1 shape abstention rates differ (run 1: M0 in-scope 0.25, M1 0.00; run 2: M0 0.12, M1 1.00). Accuracy is 0.50 (= majority baseline) in every configuration in both runs. Run 1 is kept in `bench/track_a/results_run1_rng_artifact.json`. No method or threshold changed.
- **A1 diagnostic (not pre-registered).** Rosen Mo edge with the synthetic S edge gives the old default map (29 triangle_Mo, 11 triangle_S): the map is set by the synthetic S-edge and attachment constants, not by the DFT Mo edge. With the MACE S edge (0.008 eV) the map collapses to triangle_Mo.
- p_eq,Mo(1073 K) from the DFT numbers is ~1e2 Pa (mean of steps 0.5->1), comparable to the feed pS2; at 50 Pa and 1073 K the grand-potential minimum on the Mo edge is the 50 % S edge, not 100 %.
- j1-j3: the Tier 1 vapour-pressure law is clamped at the melting point (1068 K) so the model cannot respond to a 1073-1123 K boat; it calls no_change (changes ~1e-4 in ln). s09: undersaturated at the 750 C substrate, F = 0, no_change. A liquid-branch MoO3 vapour pressure with a source is the missing piece.
- s13 is called non_monotonic (a proxy peak in coverage vs T), wrong against the stored label `decrease`.
