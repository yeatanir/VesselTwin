# Track A progress

## Files I will touch (declared before first edit)
- vessels/cvd_tube/__init__.py, vessels/cvd_tube/thermo.py, vessels/cvd_tube/wulff.py, vessels/cvd_tube/edge_data.json (+ new files under vessels/cvd_tube/)
- bench/sensitivity_score.py, bench/shape_score.py, bench/sensitivity/*, bench/shape/*, new files under bench/ (e.g. bench/track_a_score.py, bench/nucleation.py)
- vessels/cvd_tube/rosen_sbinding.py, vessels/cvd_tube/rosen_mo_edge.json, vessels/cvd_tube/growth.py (new; A1-A3 code). NOT editing atomistic/ (not mine)
- tests/test_wulff.py, tests/test_wulff_anchor.py, tests/test_tube_physics.py, tests/test_sensitivity_bench.py, tests/test_shape_bench.py, tests/test_edges.py, new tests/test_track_a_*.py
- docs/prereg/track-a.md, docs/handoff/requests-a.md, docs/progress/track-a.md
- docs/sensitivity_benchmark.md, docs/shape_benchmark.md, docs/wulff_reanchor*.md/json (regenerated outputs)
- presets for cvd_tube (presets/cvd_tube__*.json) if needed

## Log
- start: worktree ../vt-track-a on branch track-a from main ac9879f. PIDs: none.
- A4 done (see prereg s1): held-out = Jian 2019 j1-j3 only (n=3, one paper); Wang 2025, Kucuk 2024 etc excluded; Wang 2014 closed -> A5 abandoned.
- A1 data extracted: vessels/cvd_tube/rosen_sbinding.py + rosen_mo_edge.json (Table 2 reproduced). Theory source opened: Pimpinelli 2014 (alpha=i/(i+2)).
- Prereg written; committing before any scoring. Next: implement growth.py (A2/A3), wulff dft_rosen, bench/track_a_score.py, tests, then score once.

## FINAL REPORT (Track A, Oct 21)
Pre-registration commit: 925b072 (+ addendum A in 126aa74, both before the scoring run). Scoring run 1 had an RNG-stream side effect from a new ParamDef sigma (broke test_shape_bench); fixed with a scoped switch and re-run (run 2 reported; run 1 kept in bench/track_a/results_run1_rng_artifact.json). No method/threshold changed. Full tables: docs/track_a_results.md.

### What changed, file by file
- docs/prereg/track-a.md (new): pre-registration + addendum. docs/track_a_results.md, bench/track_a/results*.json (new): results.
- bench/track_a_score.py (new): scoring exactly per prereg. bench/sensitivity/blind_*.json (new): blind baselines (dev copy; held-out from fresh subagent given only the question).
- vessels/cvd_tube/growth.py (new): inventory (MoO3, S), vertical gap, Venables proxies. vessels/cvd_tube/rosen_sbinding.py + rosen_mo_edge.json (new): DFT Mo-edge S binding. vessels/cvd_tube/wulff.py: eq_model "dft_rosen", dE_Mo_dft_eV, with_sigma, GDEFS joined. vessels/cvd_tube/__init__.py: T_boat_Mo_C lower bound 300 -> 200 C.
- tests/test_track_a_growth.py (new, 6 tests: infinite inventory, t_dep linear in m, gap 1/gap and gap->0 Hertz-Knudsen limits, chi = i/(i+2), Rosen Table 2 reproduction + dG_r anchor, call-rule known answers). docs/sensitivity_benchmark.md, docs/shape_benchmark.md: pointer line only. docs/handoff/requests-a.md (captions etc.).

### Metrics (before -> after; n; prereg 925b072)
- Original 8 items, uncertain counted wrong: model 4/8 (5/8 as published) -> 2/8; blind 6/8; always-increase 4/8. Confident calls only: model 2/5 (abstain 3/8); blind 6/8; always-increase 4/8.
- Dev primary 9 items (adds s08 gap): model 3/9 (confident 3/6, abstain 3/9); blind 6/9; always-increase 4/9. Secondary non-shape class_change (s05, s06, s07): 0/3.
- Held-out j1-j3 (one paper, n=3, too small for any claim): model 0/3 (no_change; vapour-pressure law clamped at the 1068 K melting point), blind 3/3, always-increase 2/3.
- Shape benchmark (14 cases / 8 in scope): accuracy 0.50 = majority (always triangle) for M0 synthetic, M1 MACE, M2 DFT-Rosen Mo edge. Default map: M0 29 triangle_Mo + 11 triangle_S; M1 and M2 all 40 triangle_Mo (still collapsed). Diagnostic (not preregistered): DFT Mo edge + synthetic S edge reproduces the M0 map, so the map is set by synthetic S-edge constants.
- Handle added and works (s08 gap: correct decrease; the only newly modellable item scored). s05/s06 give no_change because supply is never inventory-limited at 10-400 mg with the model's evaporation rate.

### Failed / abandoned
- A5 (threshold fallback): not run; Wang et al. 2014 is closed access (Unpaywall closed, not in Europe PMC), so no sourced direction or calibration.
- S edge DFT mapping: no defensible mapping (Rosen Table 3 gives S adsorption on the S edge, not MoS2-unit kink energies); MACE E_kink_S and synthetic P_std_Mo stay.
- s02 (transverse position) and s12 (film thickness) stay unmodellable; lateral position was not mapped to the along-tube coordinate (wrong coordinate).
- A4: only Jian 2019 verified; Wang 2025 paywalled, Kucuk 2024 figure-read/NaCl/not mappable, others confounded. Edison credits used: 0.
- The model currently cannot beat the blind baseline; accuracy is below it on the dev set.

### New or changed constants with source tags
- Rosen Mo-edge dE_S (eV): -2.91 -2.37 -0.93 -0.21 -0.08 -0.36 (steps theta_S 0->1) = SI mos2_data.xlsx sheet E_Mo_edge col B rows 3-9 with Reference_species B2/B3 (E_H2 -6.7755, E_H2S -11.2255), eq 19; matches printed Table 2 theta_H=0 column (checked on the page image). Vibrational F from sheet S_vibrations_Mo_edge. Conversion to S2 vapour: NIST/JANAF Shomate (H2, H2S as copied in the SI sheet Tabulated_data; S2 from thermo.py, dfH 128.6003 kJ/mol); ASSUMPTIONS: H2S/H2/S2 gas equilibrium sets mu_S, theta_H = 0, harmonic, kink = mean of steps 0.5->1, sigma 0.25 eV (assumed). Result p_eq,Mo(1073 K) ~ 1e2 Pa.
- a(MoS2) = 3.16 A (quoted in Rosen 2018 p. 15320, experimental) -> n_ML 1.9e-5 mol/m2.
- chi = i/(i+2): Pimpinelli, Tumbek & Winkler, JPCL 5, 995 (2014), DOI 10.1021/jz500282t (alpha = i/(i+2), diffusion-limited). E_eff 0-2 eV: SYNTHETIC. T_boat_Mo_C range 200-300 C: unverified extrapolation. m_MoO3_mg, m_S_mg, gap_mm: user inputs (defaults unlimited / off).

### Requests left
docs/handoff/requests-a.md: captions (shape map, benchmark), tiers.json text, harness snapshot regen, liquid MoO3 vapour-pressure source, Wang 2014 library copy.
No processes started; no PIDs. Branch pushed: track-a.
