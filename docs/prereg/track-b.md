# Track B pre-registration (committed before any scoring)

Written Oct 20 2026 (ET), branch `track-b`. Anything below is fixed; any later change gets a new pre-registration and both results are reported.
Data are the stored CFD results in `docs/ampoule_cfd_verification.json`, `docs/tube_cfd_verification.json`, scratch `ampoule2/mout_*.json`
(ampoule mesh study), and flask runs I make myself (B5). Tier 1 values are recomputed from the code at commit `ac9879f` (main) unless stated.
What I have already seen before writing this: the aggregate numbers in the docs (tube regime 65%, ampoule 81.7%/75%, surrogate errors), the 4 ampoule mesh
f_CFD values (3 levels each), and the flask Np values at cells/cm 4, 6, 9. I have NOT looked at per-case CFD/Tier 1 ratios, per-case Tier 0 labels, or any
quantity computed by the new methods below.

## CFD "ground-truth" regime labels (verbatim from the code that makes them)

These are conventions chosen by the earlier agents, not measured physics. B3 measures agreement with the convention.

**Tube** (`scripts/tube_cfd_verification.py::cfd_regime`, written by the tube agent on Oct 20, theta_c = 0.1 and f_c = 1 - 1/e set by that agent in the same
file, not taken from a source; the 63 % is chosen to equal NTU = 1):
```
th  = (T_wall - T_gas_at_substrate) / (T_wall - T_ends)            # T_ends default 25 C
fup = 1 - MoO3_at_substrate_mol_s / MoO3_released_mol_s            # fraction of boat MoO3 taken by walls before the substrate centre
label = heat_limited      if th > 0.1
        transport_limited if fup >= 1 - exp(-1)   (0.632)
        reaction_limited  otherwise
```
Stored per case as `regime_cfd`, `frac_upstream_uptake`, `theta_gas` in the `sweep` list (40 cases, all `ok`).

**Ampoule** (`scripts/ampoule_verification_build.py`, Oct 20, same agent): `convection_assisted` iff `f_cfd > th` with `th = 1.1` primary
(1.1 is the Tier 1 parameter `conv_threshold`, itself tagged synthetic) and `th = 1.2` secondary; otherwise `transport_limited` (diffusion). f_cfd = CFD sink flux /
dilute Fick diffusion-only flux, mean of the last quarter of the run. 60 cases, all `ok`.

## B2. Learned multi-fidelity correction

- Datasets: ampoule 60 sweep cases (5 inputs: D_mm, L_cm, dT_K, tilt_deg, agent_mg_per_cm3; output f); tube 40 sweep cases (5 inputs: flow_sccm, T_boat_Mo_C,
  T_furnace_C, tube_id_in, x_substrate_cm; outputs ratio_Mo_S, supersaturation_MoO3 at wall T, supersaturation at gas T, p_MoO3_Pa, p_S2_Pa). Cases with `ok` false are dropped (none expected).
- Target per case and output: y = log10(CFD / Tier 1). Tier 1 for the ampoule is `vessels.ampoule._core(p)["f"]` (current, post-stratification-fix) and, as a clean baseline,
  the same with the stratification line as in commit `aa4e98c` (pre-fix, fitted only to the 5-point tilt-0 scan). For the tube, Tier 1 is `scripts/tube_cfd_verification.tier1(v)`.
- Inputs: log for flows, sizes and loadings (flow, D, L, tube_id, x_substrate, agent loading), linear for temperatures, dT and tilt. Standardised inside each fold.
- Model: scikit-learn GaussianProcessRegressor, kernel `ConstantKernel(1,(1e-2,1e2)) * Matern(length_scale=ones(5),(0.05,50), nu=2.5) + WhiteKernel(1e-2,(1e-6,1))`,
  normalize_y=True, n_restarts_optimizer=10, random_state=0. Hyperparameters re-fitted in every fold.
- Evaluation: leave-one-out. Reconstruction = Tier 1 * 10^yhat. Metrics vs CFD (absolute relative error |pred/CFD - 1|): median, mean, fraction <= 5 %, fraction <= 20 %,
  for the corrected surrogate AND for Tier 1 alone. Also the fraction of LOO truths inside the predictive +-1 sigma and +-2 sigma band (in y). Spread of y (std, range in decades) per output;
  if the CFD/Tier 1 ratio spans > 3 decades, or flips regime sharply, that output is reported "not learnable from n cases".
- Leakage: ampoule cases "near the Tier 1 fit scan" = |tilt| <= 10 deg AND 12 <= L <= 18 cm (the scan was tilt 0, L = 15, D 10-60 mm). Metrics are reported on all cases,
  on non-near cases, for post-fix Tier 1 (the stratification fix was chosen after seeing all 60 sweep results, so every case is "seen" by it) and for pre-fix Tier 1 (sweep unseen). The all-cases post-fix Tier 1 baseline is optimistic.
  Tube: no Tier 1 constant is tagged as fitted to CFD (`grep` of `vessels/cvd_tube`); the earlier agreement runs (12 points) were seen by the Tier 1 author but none coincides with a sweep case. Reported as "no known leakage", not as proof.
- Pass threshold: surrogate LOO median error <= 5 % AND strictly lower than Tier 1 alone (plan target 5 %); the result is reported either way.

## B3. Tier 0 regime calls

Tube (40 sweep cases, label above).
- T0-base: current `vessels.cvd_tube.tier0` (NTU Da_wall >= 1 -> transport_limited, else reaction_limited; heat_limited if thermal entrance length > heated length).
- T0-new (primary): same heat_limited test. Otherwise Da_eff = (k_m pi d / Q_f) * integral over x from the MoO3 boat to the substrate centre of s(x) dx,
  k_m = Sh D_MoO3 / d_h with Sh = 3.66, D_MoO3 at the furnace temperature (as the current code), Q_f the volumetric flow at furnace T (as current),
  s(x) = max(0, 1 - psat_MoO3(T_wall(x)) / psat_MoO3(T_boat_Mo)), i.e. the wall only takes up where it is colder than the boat (the model's own uptake closure: a wall sink at its saturation pressure,
  with the gas bounded above by the boat saturation). Label transport_limited iff Da_eff >= 1 (no fitted parameter; this matches the NTU = 1 <-> 63 % convention of the CFD label).
  Sh = 3.66 is the fully developed laminar constant-wall-temperature Nusselt number carried over by the heat/mass analogy; entrance effects are not included
  (Hausen thermal-entry Nu = 3.66 + 0.0668 Gz/(1+0.04 Gz^(2/3)) raises it; reported as a sensitivity: Sh_mean via Gz = (d/L) Re Sc with L = boat-to-substrate distance, does not enter the primary call).
- T0-fit: if T0-new at threshold 1 is below 90 %, fit a single threshold on log10 Da_eff: stratified (by CFD label) random half split, fit on one half by maximum accuracy
  (ties -> midpoint of the tied interval), report agreement on the other half; seeds 0,1,2,3,4; mean +- sd (population sd over seeds). Same protocol for T0-base's Da_wall.
- Output: accuracy for full data (fixed-threshold variants), confusion matrices (rows CFD, columns Tier 0), held-out accuracy mean +- sd, and the largest-margin misses.

Ampoule (60 cases). Tier 0 call: convection_assisted iff f_T1 > 1 + c (c = threshold 0.1 default).
- Held-out measurement of the stratification fix: candidate set = stratification closure in {none (stab = 1), legacy L^3 scale (commit aa4e98c), duct-height H^4 scale (current)} x conv_threshold in {1.05, 1.1, 1.2}
  (9 candidates; f recomputed by `tier2/verification/tier0.py`, which must reproduce the shipped f for the current variant to 1e-9 as a unit test). For each of seeds 0-4: stratified half split on the CFD label (th = 1.1 and, separately, 1.2),
  choose the candidate with highest accuracy on one half (ties -> prefer the shipped candidate, then lower threshold), report its accuracy on the other half. Also report the three fixed-closure variants at the shipped threshold on both halves.
  The improvement is "held out" only in the sense that the closure family is chosen on a half; the specific H^4 variant was authored after seeing all 60 cases, and this is stated in the report.
- Confusion matrices at threshold 1.1 and 1.2 for each closure variant.

## B4. Grid convergence index (Roache)

Source opened: NASA Glenn WIND validation tutorial, https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html (attributes GCI to Roache; Fs = 1.25 for three or more grids, 3.0 for two; worked p = ln[(f3-f2)/(f2-f1)]/ln r, GCI = 1.25 |(f2-f1)/f1| / (r^p - 1)).
Roache, J. Fluids Eng. 116 (1994) 405 and the 1998 book/AIAA treatments were not opened; the ASME V&V 20 text was not opened.
- Per case with three meshes, f1 finest. r = constant refinement ratio (ampoule and tube: 2 by construction; flask: r from cell counts, r = (N_fine/N_coarse)^(1/3), mean of the two ratios, flagged if they differ by > 10 %).
- p = ln((f3-f2)/(f2-f1))/ln r when the differences have the same sign (monotone); GCI_fine = 1.25 |(f2-f1)/f1| / (r^p - 1).
- Non-monotone (sign change), or p outside (0.5, 2 p_formal), or |f2-f1| exactly 0: Fs = 3.0 with p = p_formal, flagged. p_formal = 2 for all (ampoule: linearUpwind/limitedLinear/Gauss linear; tube: stated first-order boat singularity is flagged, not used as the formal order; flask: linearUpwind).
- Unsteady cases (osc_last_quarter > 0.1 or drift_last_quarter > 0.05) are flagged "unsteady: GCI not meaningful".
- Quantities: ampoule f_CFD at 4 points (diffusion D10/tilt0, weak D20/tilt0, tilted D25/tilt30, strong D40/tilt90); tube p_MoO3, ratio_Mo_S, supersaturation (wall T), MoO3_released at 3 points (stored M1, M2, M3: r = 2); flask Np_torque and Np_dissip.
- Target replaced: GCI_fine reported with its flag, plus the old |change| medium to fine; the 2 % number is kept only as a reference column.
- Ampoule mesh levels: L0 3 cells/cm x 8, L1 6 x 16, L2 12 x 32 (stored in `mesh_*.json`); finished results are in the scratch `ampoule2/mout_*.json`.

## B1. Regression of the shared `_fv` change
Re-run the four coarse-level (L0) mesh-study cases with the current `tier2/openfoam.py` and compare f_CFD to the stored value (same values dict). Flag if any |change| > 1 %.
The decision rule: if a diffusion-limited case moves by > 1 % regenerate it; if only convective cases move and by amounts below that case's own L0->L1 change, report it and keep the data.

## B5. Flask Np closure
- Case: water, 25 C, 100 mL at fill 0.5, 25 mm bar, 400 rpm (Re = N d^2/nu = 4636), the shipped defaults of `tier2/flask.py`, kEpsilon with wall functions, MRF, 1500 SIMPLE iterations, steady stage only (no tracer).
  Meshes cells_per_cm 4, 6, 9 (existing) and 13.5 (new, r = 1.5 on target spacing), all rerun with the current code. GCI on the triplets (6, 9, 13.5) [fine triplet] and (4, 6, 9) [old triplet], quantity Np_torque (primary,
  power balance) and Np_dissip (cross-check). Iterative convergence: relative change of the torque over the last 100 iterations must be < 1 %, otherwise flagged.
- The closure entry is a single-point value at Re = 4636 with GCI band; status "computed". A second Re (water 800 rpm, Re = 9271, meshes 4, 6, 9) is added only if its triplet finishes; no curve, no extrapolation.
- Np(Tier 1) is compared as a ratio only.

## Process
Max 3 OpenFOAM processes at once (machine-wide); PIDs logged in `docs/progress/track-b.md`; no kill by name. Edison credits: 0.
