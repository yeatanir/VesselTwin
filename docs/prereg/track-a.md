# Track A pre-registration (committed before any scoring)

Branch `track-a`. Written Oct 20-21 2026 after reading the code and the existing benchmark outputs, before running any new score. Code that implements this is committed with or after this file; the scoring run (`python -m bench.track_a_score`) is executed once, after this commit. If the method changes after seeing results, a new pre-registration is committed and both results are reported.

## 0. Status of the data (what has been seen)
- **Development set** = sensitivity items s01-s14 (`bench/sensitivity/papers.json`, unedited) and the 14 shape cases (`bench/shape/papers.json`). We already know which items the old model misses (s03, s04, s13) and A1-A3 were designed in response. Everything on these is labelled "development set", never "held-out".
- **Held-out set** = only items from the Edison q6-q8 answers that the model has never scored and that I verified against the opened source (A4). Result below.

## 1. A4 verification (done before this file)
Opened full text and read the sentences (not search summaries):
- **Verified, new:** Jian, Chang & Xu, *Materials* 12, 198 (2019), DOI 10.3390/ma12020198, open access (Europe PMC PMC6357088). Quotes: "The effect of the MoO3 temperature (1048 K, 1073 K, 1098 K, 1123 K) ... molybdenum source dosage of 0.02 g, a holding time of 30 min, a gas flow rate of 100 sccm, and a distance between the carrier and the molybdenum source of 4~5.5 cm" with S zone 453 K; "When the temperature of MoO3 is 1073 K ... the side length of the triangular MoS2 is approximately 30 um"; "When the temperature of MoO3 is 1098 K ... complete and independent triangular MoS2 crystals with a side length of approximately 100 um"; "When the temperature of MoO3 is 1123 K ... the size of MoS2 does not become larger but diminishes. However, the MoS2 crystal number increases". Three held-out items, all from one paper (not independent):
  - **j1** MoO3 source T 1073 -> 1098 K (800 -> 825 C), domain size: **increase**.
  - **j2** 1098 -> 1123 K (825 -> 850 C), domain size: **decrease**.
  - **j3** 1098 -> 1123 K, crystal number per area (nucleation density): **increase**.
  Blind no-tool baseline for j1-j3 was obtained from a fresh subagent given only the setup and the question (`bench/sensitivity/blind_heldout_jian.json`) before any model run.
- **Already in the development set (not new):** Xu 2018 flow series = s01 and position series = s02; Prasad & Singh arXiv 2206.14151 flow series (coverage 40/70/92 % at 50/100/150 sccm, size 80 -> 7 um) = s03/s04.
- **Excluded, not verifiable or confounded:** Wang et al. 2025 sulfur-temperature series (J. Phys.: Condens. Matter, DOI 10.1088/1361-648x/ae14c8): not open access, full text not retrievable; (same paper is already s11). Kucuk et al. 2024 sulfur position (Research Square preprint): text opened, but numeric coverages are read from a figure, NaCl additive, distance from furnace centre not mappable to `x_S_boat_cm`; qualitative only. Momeni 2018, Sitek 2020, Saenz 2016, Tummala 2022: other variables changed together (Edison's own caveats) or no numbers. Ganger thesis: no verified DOI.
- **Held-out n = 3 items from one paper.** Too few to support any claim; reported separately and never pooled.

## 2. Labels in the data and how each is scored
Labels present: `increase`, `decrease`, `class_change` (s05, s06, s07, s11). Labels `no_change` and `non_monotonic` occur in the scorer code but in **no** item. Several items' notes say the real response is non-monotonic beyond the labelled range; the label as stored is what is scored.
- `increase` / `decrease`: correct iff the model's confident call equals the label.
- `class_change`, shape item (s11, shape class vs sulfur-boat T): correct iff the model predicts a class change between the sweep ends (labels differ, neither end flagged band-spans-classes).
- `class_change`, non-shape items (s05 layer number, s06 domain size, s07 coverage/layer number): **excluded from the primary tables** (the label is a qualitative regime change in a quantity the one-proxy direction call cannot represent). Reported in a secondary table: correct iff the model call is `non_monotonic` (extremum inside the sweep) for >= 90 % of MC draws.
- `non_monotonic` / `no_change` labels would be scored: `non_monotonic` correct iff the model call is `non_monotonic`; `no_change` correct iff p05-p95 of the change lies within +-tol of zero.
- A model call outside {increase, decrease} on an `increase`/`decrease` item (`non_monotonic`, `no_change`, `class_change`) is a confident wrong call. `uncertain` is an abstention.
- **Excluded items (no model handle, reason):** s02 (paper's x is a *transverse* substrate coordinate; the prompt's suggestion to use the along-tube transport model would map a different coordinate; Edison's own summary calls it "transverse substrate coordinates, not distance from the MoO3 boat"); s12 (MoO3 film thickness: needs the film area and MoO3 density, no sourced values in repo). Layer number is given a handle (below) only through Mo delivered per monolayer.

## 3. Proxies (A2): formulas and direction rules
Theory: mean-field atomistic nucleation (Venables). Opened source: Pimpinelli, Tumbek, Winkler, *J. Phys. Chem. Lett.* 5, 995 (2014), DOI 10.1021/jz500282t (CC-BY, PMC3962253): "the island density N is a function of the substrate temperature T and of the deposition rate F", "N ~ F^alpha", and for diffusion-limited aggregation "alpha = i/(i+2)"; they state "A temperature-dependent coefficient has been omitted". The temperature factor of Venables, N proportional to exp(E_i/((i+2)kT)) with nu = nu0 exp(-E_d/kT), is **not in an opened source**; it is used only as a labelled assumption below.
Per MC draw d and sweep point x (parameters drawn once per draw, held across the sweep, so the change is paired):
- F = `flux_MoO3_mol_m2_s` at the substrate centre from the tube model (floored at 1e-300 before the log).
- Nucleation density: ln N = chi_i ln F + E_eff/(kT_sub), chi_i = i/(i+2), i in {1,2,3}; E_eff = (i E_d + E_i)/(i+2) is **synthetic, range 0-2 eV**, entering only when the swept parameter changes substrate temperature (`T_furnace_C`); the call is evaluated at both corners E_eff = 0 and 2 eV and the band is their union. No sourced E_d or E_i exist.
- Domain size at fixed coverage: ln L = -0.5 ln N.
- Coverage: ln theta = ln F + ln t_eff (sticking = 1, not in the model).
- Layer number: ln(F t_eff / n_ML), n_ML = 1/(A_cell) per MoS2 with A_cell = (sqrt3/2) a^2, a = 3.16 A (experimental value quoted in Rosen et al. 2018 p. 15320).
- t_eff = min(t_growth, t_dep,Mo, t_dep,S) (A3).
Direction rule per observable and per i: (1) if >= 90 % of draws have an interior reversal with both excursions > tol (5-point series) the call is `non_monotonic`; (2) otherwise take the paired change D = y_end - y_start over draws: `no_change` if max(|p05|,|p95|) < tol; else `increase` if p05 > 0; `decrease` if p95 < 0; else **`uncertain`** (the p05-p95 band crosses zero). tol = 0.05 (ln units, ~5 %). (3) If the three i values give different calls the final call is `uncertain`.
MC: 100 draws, seed 0, `core.uq.sample` over every ParamDef sigma, 5 equispaced sweep points. Defaults for unmentioned parameters are the repo defaults (growth time 10 min, inventories unlimited) except where an item states them (s05/s06: t = 5 min, m_S = 200 mg resp. m_MoO3 = 15 mg, from the Prasad series).

## 4. Model handles (A3, Tier 1 only), each with an analytic-limit test
- MoO3 and S amount: t_dep = m / (M * rate), rate from the existing Hertz-Knudsen boat; supply integrated over t_growth with the depletion cap.
- Vertical gap (face-down substrate above the boat): 1D diffusion across the gap in series with Hertz-Knudsen, F = dp / (1/k_hk + gap R T / D), D = model Fuller diffusivity; gap -> large gives F proportional to 1/gap.
- Lateral position: **not modelled** (see s02 above). Film thickness: not modelled. Layer number: Mo delivered relative to one monolayer (above).
- s09: `T_boat_Mo_C` lower bound 300 -> 200 C. The vapour-pressure law is an extrapolation below its data range (not verified); only the sign is tested and the item is flagged.

## 5. Sensitivity items scored (development set), with sweeps
| id | parameter, sweep | observable | label | scored |
|---|---|---|---|---|
| s01 | flow_sccm 10-160 | nucleation density | increase | yes |
| s03 | flow_sccm 50-300 | domain size | decrease | yes |
| s04 | flow_sccm 50-150 | coverage | increase | yes |
| s05 | m_MoO3 10-30 mg | layer number | class_change | secondary |
| s06 | m_S 100-400 mg | domain size | class_change | secondary |
| s07 | T_furnace_C 650-800 | coverage / layer number | class_change | secondary (coverage) |
| s08 | gap_mm 2-10 | layer number | decrease | yes (new handle) |
| s09 | T_boat_Mo_C 200-400 | nucleation density | increase | yes (bound extended) |
| s10 | T_furnace_C 700-850 | nucleation density | decrease | yes (range assumed) |
| s11 | T_boat_S_C 180-300 | shape class | class_change | yes (shape; 835 C Mo boat is not set, as before) |
| s13 | T_furnace_C 750-850 | coverage | decrease | yes |
| s14 | boat_area_MoO3_cm2 1-4 | coverage | increase | yes (range assumed; area stands in for nanoribbon density) |
| s02, s12 | - | - | - | excluded |
Held-out: j1 T_boat_Mo_C 800-825 C domain size; j2 825-850 C domain size; j3 825-850 C nucleation density.
Reported tables (n stated in each): (T1) primary dev items, model vs blind baseline vs always-increase on the same items, with (i) accuracy counting uncertain as wrong and (ii) accuracy on confident calls plus abstention rate; (T2) the original 8 modellable items (s01, s03, s04, s09, s10, s11, s13, s14) under the new model, next to the old model's 5/8 and baselines; (T3) secondary class_change items; (T4) held-out j1-j3 separately. The blind baseline's `non_monotonic`/`no_change` labels count as confident wrong calls on increase/decrease items. Differences of one or two items are not evidence.

## 6. Shape model (A1, A5) and the shape benchmark
- **A1 mapping (Mo edge only).** Rosen, Notestein & Snurr, *J. Phys. Chem. C* 122, 15318 (2018), DOI 10.1021/acs.jpcc.8b02524, SI workbook `mos2_data.xlsx`: sheet `E_Mo_edge` column B (theta_H = 0), rows 3-9, plus `Reference_species` B2/B3 and sheet `S_vibrations_Mo_edge`. Differential S adsorption energy vs H2S/H2, eq 19, reproduces the printed Table 2 column theta_H = 0 (-2.91 -2.37 -0.93 -0.21 -0.08 -0.36 eV; checked against the page image). Vibrational free energy added as in the authors' script. Conversion to S2 vapour: Dmu_S(S2, T, p) = [mu0_H2S - mu0_H2](T) - (E_H2S - E_H2) + dG_r(T) + 1/2 kT ln(p/1 bar), dG_r from NIST/JANAF for H2S = H2 + 1/2 S2 (no DFT). **Assumptions:** gas-phase equilibrium H2S/H2/S2 fixes mu_S; theta_H = 0 (no H on the edge; false for an H2 carrier); harmonic vibrations; the model's `kink` S-attachment step = mean of the three steps theta_S = 0.5 -> 1 (steps 4-6), chosen in advance and analogous to the MACE choice (50 -> 100 %); p_eq,Mo = 1 bar exp(2 (<dF_S>(T) - Dmu_S(T,1 bar))/kT); uncertainty sigma 0.25 eV on <dF_S> (assumed: spread of the three steps ~0.3 eV plus an assumed PBE-D3 error; not derived). The theta_S = 0.5 -> 1 steps are not independent: the grand-potential minimum at 50 Pa, 1073 K may be the 50 % edge.
- **S edge: no defensible mapping.** Table 3 gives S adsorption on the S edge, not MoS2-unit (Mo-feed) kink energies; the model's S-edge equilibrium needs E_kink,S relative to bulk MoS2 and P_std_Mo (MoO3 + S2 -> MoS2 + SO2 thermodynamics, not in repo). E_kink_S stays the **MACE** value (0.008 eV, labelled) and P_std_Mo_Pa stays **synthetic**. k_attach stays synthetic.
- **Configurations scored on the shape benchmark (14 cases, `in_scope` n = 8, all n = 14), each run once, no tuning:** M0 default synthetic constants; M1 MACE kink closures (E_kink_Mo 0.52, E_kink_S 0.008); M2 = A1: `eq_model="dft_rosen"` for the Mo edge + MACE E_kink_S + synthetic remainder. Per configuration: accuracy (abstention counted wrong) vs the majority baseline and always-triangle, abstention rate, and whether the default shape map collapses to one class (class composition over 40 positions). Collapse is an acceptable reported outcome; the mapping is not adjusted to remove it. All shape cases are development data; no held-out shape claim.
- **A5 (threshold fallback) is NOT run.** Condition: A1 collapses or scores <= baseline (decided from the A1 run) **and** the calibration paper can be opened. Wang et al., *Chem. Mater.* 26, 6371 (2014), DOI 10.1021/cm5025662, is closed access (Unpaywall: closed; not in Europe PMC; not OpenAlex-OA). Without the opened source the direction and the calibration data cannot be sourced, so no threshold is fitted. This is recorded as abandoned.

## 7. Pass thresholds
No claim of "better than baseline" is pre-registered as passing; the pass criteria are procedural: scoring executed once after this commit, all tables above reported including worse numbers, held-out set reported separately with n = 3 and the statement that it is too small to support any claim. A call counts as an improvement on the original 8 only if the new model's accuracy (uncertain wrong) exceeds the blind baseline's on the same 8 by >= 2 items (a one-item difference is not read as evidence).

## Addendum A (committed before the scoring run; method detail I had not pinned)
- s11 (shape class vs sulfur-boat T) is scored with the repo default Wulff constants (configuration M0). The same sweep under M1 and M2 is reported as a secondary row only. Call: `uncertain` if the shape band at either sweep end spans two classes (existing `bench.shape_score.predict` rule), else `class_change` if the end classes differ, else `no_change`.
- The band for items whose swept parameter changes substrate temperature is the union over the two E_eff corners: p05 = min of the corner p05, p95 = max of the corner p95.
- `observed zero flux`: when the tube model gives F = 0 over the whole sweep (undersaturated, no deposition) the proxies are equal across the sweep and the rule yields `no_change`; such items are flagged `zero_flux` in the tables and scored as `no_change`, not dropped.
- The shape benchmark uses `bench.shape_score.build_inputs` unchanged; configuration constants are merged over the extracted values.
- Old-model numbers for T2 are read from `bench/sensitivity/predictions.json` as committed (5/8; 4/8 uncertain-wrong).
