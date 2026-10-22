# Track L results: sensitivity benchmark rescored with each paper's own stated geometry (pre-registered in docs/prereg/track-l.md, commit 903cc2a)

Scored once (`python -m bench.track_l_score --write` -> `bench/track_l/results.json`). **All items are development data**; the paper-geometry rule was introduced after seeing the default-geometry results (Tracks A, I, K), so this is a corrected input specification, not a held-out test. No model equation or constant changed. n is tiny; one item is 8-33 points; differences of one or two items are not evidence. Setup extraction with page/section, printed value, conversion and a verbatim quote (<=40 words) per parameter: `bench/track_l/items.json`.

**Outcome: the model gets worse, not better, under paper geometry, with either vapour-pressure law.** Strict accuracy (uncertain wrong) on the 9 primary dev items 3/9 -> 1/9 (both laws); on the original 8, 2/8 -> 1/8; j1-j3 stay 0/3 (calls move from confident no_change to uncertain). Blind agent 6/9, 6/8, 3/3; always-increase 4/9, 4/8, 2/3. The "before" rerun reproduces the stored Track A calls for all 15 items (default law).

## Geometry actually used (what changed)
Rules: substrate face-down on the source boat -> x_substrate = 0 (R-Pos); source at the furnace/zone centre -> boat T = furnace T (R-T); ranges -> midpoint; unstated -> default. Per item: s01 (Xu 2018: 0.1 mg MoO3, 10 mg S, 700 C, 180 C S boat 24 cm upstream, 23 min, Ar, substrate on boat); s03-s06 (Prasad & Singh: 4.5 cm tube, 750 C, 5 min, 15 mg/200 mg, S 19 cm upstream, substrate on boat); s07, s08 (Tummala: 1 mg MoO3, 200 mg S, S 24 cm upstream, substrate on crucible; s08 sweeps the stated 2-10 mm gap); s11 (Wang 2025: 835 C, 20 sccm N2, 1 mg/120 mg, substrate 0.5 cm downstream, 5 min); s13 (Withanage: 10 sccm, 10 min, 600 mg S, 23.5 cm, gap 3-4 mm -> 3.5, 1 in tube, Tsub = Tboat = Tfurnace swept); s14 (Najmaei: 850 C, 200 sccm N2, S 1000 mg midpoint, 12.5 min; substrate position only "close to each other", default kept); j1-j3 (Jian: 20 mg MoO3, 100 sccm Ar, 30 min, S 453 K 15 cm upstream, substrate 5 cm, boat T = furnace T swept). **s09, s10 (Wang 2016) not opened (not open access): geometry not verified, default kept.** s02, s12 stay excluded.

## Per-item calls (3-way; Y correct, n wrong, abst = uncertain)
| id | label | blind | default psat: before -> after | liquid psat: before -> after | x_sub cm | zero flux (after) |
|---|---|---|---|---|---|---|
| s01 | increase | increase | increase (Y) -> uncertain (abst) | increase (Y) -> uncertain (abst) | 0.0 | False / False |
| s03 | decrease | non_monotonic | uncertain (abst) -> no_change (n) | uncertain (abst) -> uncertain (abst) | 0.0 | False / False |
| s04 | increase | non_monotonic | uncertain (abst) -> no_change (n) | uncertain (abst) -> uncertain (abst) | 0.0 | False / False |
| s05 | class_change | increase | no_change (n) -> no_change (n) | no_change (n) -> no_change (n) | 0.0 | True / False |
| s06 | class_change | non_monotonic | no_change (n) -> no_change (n) | no_change (n) -> no_change (n) | 0.0 | True / False |
| s07 | class_change | increase | increase (n) -> uncertain (abst) | increase (n) -> uncertain (abst) | 0.0 | True / True |
| s08 | decrease | non_monotonic | decrease (Y) -> uncertain (abst) | decrease (Y) -> uncertain (abst) | 0.0 | False / False |
| s09 | increase | increase | no_change (n) -> no_change (n) | no_change (n) -> no_change (n) | 12 (default) | True / True |
| s10 | decrease | decrease | uncertain (abst) -> uncertain (abst) | uncertain (abst) -> uncertain (abst) | 12 (default) | False / False |
| s11 | class_change | class_change | no_change (n) -> uncertain (abst) | uncertain (abst) -> uncertain (abst) | 0.5 | False / False |
| s13 | decrease | decrease | non_monotonic (n) -> increase (n) | non_monotonic (n) -> increase (n) | 12 (default) | False / False |
| s14 | increase | increase | increase (Y) -> increase (Y) | increase (Y) -> increase (Y) | 12 (default) | False / False |
| j1 | increase | increase | no_change (n) -> uncertain (abst) | no_change (n) -> uncertain (abst) | 5.0 | True / True |
| j2 | decrease | decrease | no_change (n) -> uncertain (abst) | no_change (n) -> uncertain (abst) | 5.0 | True / True |
| j3 | increase | increase | no_change (n) -> uncertain (abst) | no_change (n) -> uncertain (abst) | 5.0 | True / True |

**default smolik_hsc** (correct/n, uncertain wrong; confident acc; abstain)

| table | n | model before | model after | blind | always-increase |
|---|---|---|---|---|---|
| T1_dev_primary_s | 9 | 3/9 (conf 3/6, abst 0.33) | 1/9 (conf 1/5, abst 0.44) | 6/9 | 4/9 |
| T2_original8 | 8 | 2/8 (conf 2/5, abst 0.38) | 1/8 (conf 1/5, abst 0.38) | 6/8 | 4/8 |
| T4_j1_j3 | 3 | 0/3 (conf 0/3, abst 0.00) | 0/3 (conf 0/0, abst 1.00) | 3/3 | 2/3 |
| T5_all_primary_incl_j | 12 | 3/12 (conf 3/9, abst 0.25) | 1/12 (conf 1/5, abst 0.58) | 9/12 | 6/12 |

**smolik_liquid_cc** (correct/n, uncertain wrong; confident acc; abstain)

| table | n | model before | model after | blind | always-increase |
|---|---|---|---|---|---|
| T1_dev_primary_s | 9 | 3/9 (conf 3/5, abst 0.44) | 1/9 (conf 1/3, abst 0.67) | 6/9 | 4/9 |
| T2_original8 | 8 | 2/8 (conf 2/4, abst 0.50) | 1/8 (conf 1/3, abst 0.62) | 6/8 | 4/8 |
| T4_j1_j3 | 3 | 0/3 (conf 0/3, abst 0.00) | 0/3 (conf 0/0, abst 1.00) | 3/3 | 2/3 |
| T5_all_primary_incl_j | 12 | 3/12 (conf 3/8, abst 0.33) | 1/12 (conf 1/3, abst 0.75) | 9/12 | 6/12 |

T3 (secondary, class_change non-shape; correct iff non_monotonic): s05 no_change, s06 no_change (both unchanged, wrong), s07 increase -> uncertain (wrong either way). Both laws.

## Notes per item (model insensitivity by construction)
- Substrate farther than ~4 cm from the boat (Track K: boat-temperature response needs NTU < ~4): **s09, s10 (default 12 cm, geometry unverified), s14 (12 cm default; paper says only "close"), j1-j3 (5 cm, borderline: Track K elasticity 0.50 at 4 cm)**. For s13 and s08 the face-down gap model is used, not the tube march.
- **Why j1-j3 and s07 get zero flux (post-hoc probe, not pre-registered):** with R-T the substrate sits at the wall temperature, which equals the boat temperature (T_sub 1066-1116 K vs boat 1073-1123 K), so the gas is saturated at the boat and never supersaturated at an equal-temperature substrate: F = 0 at every sweep point (checked at 5 cm and 0.5 cm). The remaining "uncertain" is the E_eff/kT term alone (two-corner union straddling zero). In Jian's experiment the substrate is cooler than the MoO3 source in a two-zone furnace; the model has no separate substrate temperature unless `T_substrate_offset_K` is set, and the paper does not state one, so it stays 0 (unstated -> default). This is an input-specification gap, not evidence about the physics.
- Items that moved: s01 Y -> abst, s08 Y -> abst (the gap/flow signal now lies within the p05-p95 band), s03/s04 abst -> no_change (wrong, default law only), s13 non_monotonic -> increase (wrong either way), s11 no_change -> uncertain, s07 increase -> uncertain. Better: none. s14 unchanged (increase, correct; the only correct call after the change).
- Liquid law ("smolik_liquid_cc") changes almost nothing relative to the default law under paper geometry; reported side by side, no choice made, default stays `smolik_hsc`.

## Not done / caveats
Wang 2016 (s09, s10) unopened; Prasad & Singh 19 cm read as S-to-MoO3 (ambiguous); Najmaei substrate distance and S temperature (~600 C, outside the model range) default. No substrate-temperature offset is stated by any paper, so none was set. No held-out set exists. No constant was tuned.
