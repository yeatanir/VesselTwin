# Track K pre-registration (written after the read-only trace, before any test, scoring or model change)

Question: is the substrate MoO3 flux insensitivity to boat supply (and to some Track A knobs) a defect or intended transport-limited physics of the Tier 1 equations?

## Definitions
DEFECT = any of: (D1) a hard-coded clip/cap/stale value that is not derived from the model's equations and changes F or pM at the substrate; (D2) a unit/species-basis inconsistency (formula units vs molecules) that breaks the limits below; (D3) F stays flat in boat supply even when the cumulative wall NTU between boat and substrate is < 1 (no memory loss to explain it).
INTENDED PHYSICS = the flat response is fully explained by the model's own wall-uptake equation N_out = Nsat + (N - Nsat) exp(-km fM A / Q) with cumulative NTU >> 1 between boat and substrate, the response returns when NTU is reduced with the same code, and the stored CFD shows the same sublinear trend.

## Method (all development data; no held-out set exists; no tuning)
1. Code audit (done, see progress file) for D1-D3 plus analytic known-answer tests of `march` wall uptake: NTU -> 0 returns the supply unchanged; NTU -> infinity returns Nsat.
2. Memory test: with `MoO3.psat_model = smolik_liquid_cc` (so boat 800-850 C is not clamped) compute cumulative NTU boat -> substrate centre and the elasticity e = d ln F / d ln NM_in (finite difference over boat 800 -> 850 C) for x_substrate_cm in {0.5, 1, 2, 4, 8, 12} and flow 50/100/200 sccm. Pass for "intended" if e is monotone decreasing in NTU, e > 0.5 where NTU < 1, and e < 0.05 at the default geometry.
3. Stored CFD (docs/tube_cfd_verification.json, no new runs): elasticity of substrate p_MoO3 against released supply for the boat 650 -> 700 -> 750 cases; CFD/Tier 1 p ratio for boat 650/700/750/800 (Tier 1 values as stored). "Same trend" = CFD elasticity between 700 and 750 C is < 0.5 with boat uptake fraction >= 0.9.
4. Unit test (tests/test_track_k.py): F(T_boat) is non-decreasing over 700..900 C for fixed other conditions with the liquid law, strictly increasing (> 1 %) per 25 C step when the substrate is within 1 cm of the boat; documented physical limit when NTU >> 1: relative change < 1 %.
5. Track A 3-way sensitivity tables (bench/track_a_score.py, same code/items): rerun only if the model changes. If no model change, before = after by construction and the stored tables in docs/track_a_results.md stand.

## Decision rule and fix
If none of D1-D3 holds: no model change; document why j1-j3, s05/s06 and flow items fail (the observable is not boat-limited in this tube geometry) in docs/track_k_results.md; add the tests.
If a defect is found: minimal fix at the location found, kept behind a new ParamDef switch (default = old behaviour unless the user decides), no constant fitted to any benchmark; report Track A tables, CFD/Tier 1 ratios and the new test before vs after, including any that get worse.
