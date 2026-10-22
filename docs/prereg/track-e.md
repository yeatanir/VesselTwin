# Track E pre-registration (photoreactor vs ferrioxalate actinometry)

Written and committed BEFORE the comparison script `bench/photoreactor/score.py` is run on these setups.
Disclosure: before writing this file I did a back-of-envelope hand calculation of the collimated case (about 0.89 with phi = 1.21) while reading the paper; the tolerances below were set from the error budget, not from that number.

## Method
- Model: `vessels/photoreactor.py` (flat slab, Beer-Lambert, Fresnel wall, phi x absorbed photons).
- Setups (inputs fixed in `bench/photoreactor/setups.json`, each tagged with its source):
  1. `saenz_qpb_cuvette`: Saenz et al., Heliyon 2024 (doi 10.1016/j.heliyon.2024.e31309), quasi-parallel 365 nm LED, quartz cuvette, 6 mM ferrioxalate, normal incidence.
  2. `saenz_is_cuvette`: same paper, same cuvette in an integrating sphere (isotropic illumination, four faces).
  Both come from one paper and one lab; they are two illumination geometries, not independent literature. A second independent paper was not found (see progress file for the candidates that were opened and rejected, and the three that returned 403).
- Inputs are taken from the paper's stated setup. Quantum yield and the absorption criterion come from Hatchard & Parker 1956 (Table 5, recommended 1.21 at 365/6 nm; p. 533 >= 99 % absorbed in 1 cm). Nothing is fitted to the measured slope.
- Observable: initial slope `a` of actinometer conversion X (in percent) against incident photon fluence H_p (umol m-2): Saenz Table 2, `a_QPB = 0.00161 +/- 0.00003`, `a_IS = 0.0078 +/- 0.0001` (percent per umol m-2). Predicted `a = 100 * (r0 / n0) / E_p` from the model's t = 0 rate r0, initial moles n0 = c0 V_total, and the photon irradiance E_p implied by the measured irradiance.
- Metric: ratio R = predicted / measured. The main uncertainty contributor is found by one-at-a-time +/- 1-sigma moves of phi (0.03), n_wall (0.04), n_liq (0.02), wall thickness (0.05 mm), eps_A (to 1500, the bound lifts f from 0.99 to ~1); p05-p95 of R from a 500-draw Monte Carlo (seed 0) over the same sigmas.
- Score once. Secondary sensitivity runs (not pass/fail): phi = 1.26 (Saenz's value), n_wall = 1.485 (Open Res. Europe Table 1).

## Pass thresholds
- Collimated case: pass if 1/1.25 <= R <= 1.25. Reason: every optical input is stated or measured; known error budget is phi 2-4 %, wall T 1 %, eps bound 1 %, paper's own tables differ by 5 %, statistical error 2 %; 25 % leaves margin for the unsourced n_liq.
- Diffuse case: pass if 1/1.5 <= R <= 1.5. Reason: the slab model has no lensing or edge entry for the cuvette corners; the paper itself finds an unexplained 21 % excess (eta = 1.21) over the geometric expectation.
- A failing comparison is reported with its ratio; its test is marked xfail with the ratio in the reason.

## Not tested (stays synthetic and labelled)
- Lamp power to irradiance (point/line source formulas, wall-plug efficiency): the Thorlabs M365LP1 datasheet could not be opened, and the LED is directional, so the isotropic point-source formula is not applicable to it. The measured-irradiance lamp mode bypasses it.
- Mixing-limit heuristic (no source found; relabelled as an unsourced heuristic) and the temperature rise (adiabatic-style upper bound with a synthetic h_cool): no measured data.


# Part 2: 13X sorbent bed (registered before any 13X change or IAST run)

Baseline (disclosure: `python -m vessels.sorbent.benchmark` on unchanged code was run once before this section to read the starting point):
13X CO2/He breakthrough t50 error -38 % (y = 0.15: model 469 s vs 757 s) and -39 % (y = 0.5: 169 s vs 278 s); peak temperature at 0.8 L model 95.9 / 112.6 C vs measured 68.5 / 79.0 C (Wilkins 2017 Fig. 4.11); CALF-20 breakthrough errors -3 %, +2 %, +10 % (-0.03, +0.02, +0.10); 13X competitive loadings (Wilkins 2017 Table 4.5) CO2 1.79 vs 2.16 (-17 %) and 1.44 vs 2.46 (-41 %) mol/kg, H2O 12.19 vs 12.35 and 13.37 vs 14.42.

## E6 wall heat transfer: option chosen = fit on one condition, test on the other
- Why not a published correlation: the 13X column runs at particle Reynolds number of order 0.3 (u_s about 0.019 m/s of He at 700 sccm in a 2.82 cm bore, d_p assumed 2 mm; computed in the scorer and reported); the packed-bed wall Nusselt correlations I know are fitted for Re_p of order 20 and above, and none that covers Re_p < 1 was found in an open-access full text this session. Citing one outside its validity range would be worse than an honest fit. The particle diameter (2 mm) is itself marked ASSUMED in the source data, so a correlation in d_p would inherit that uncertainty.
- Method: one parameter, the bed-to-wall coefficient `h_in` (W m-2 K-1), bounded [0.5, 300], found by bracketing root search so that the model t50 equals the measured t50 for y = 0.15 (flow 700 sccm). Everything else as in `vessels/sorbent/benchmark.py` (n_cells = 60, h_out = 10, K_z = 0.4, d_p = 2 mm assumed).
- Held-out test: y = 0.5 (350 sccm) is not used in the fit. Metrics: relative error of model t50 vs measured, and error of model peak temperature at 0.8 L vs measured, before (h_in = 4.0, Wilkins' thesis value for one column) and after.
- Pass threshold (held-out y = 0.5): |t50 error| <= 15 % (the baseline is -39 %). Secondary: if the fitted h_in exceeds 100 W m-2 K-1 the result is reported as an effective coefficient that absorbs other errors (d_p assumption, isotherm heat), not as a transport property.
- Seeds: none (deterministic). Reverse direction (fit on 0.5, test on 0.15) is reported as a robustness check, not used for the headline.
- CALF-20: rerun all three breakthrough errors; must stay within -3 % to +10 % (the CALF-20 column has its own h_in = 6.963 and is not touched, so the expected change is zero; the test asserts it).

## E7 CO2/H2O competition
- The model uses extended dual-site Langmuir (EDSL), not IAST (module docstring: IAST-equivalent only for equal capacities).
- Method: pyIAST 1.4.3 (installed into a scratch directory, not the shared environment). Pure-component isotherms = the model's own CO2 and H2O dual-site Langmuir isotherms at the measured temperature, sampled without noise and passed to `pyiast.ModelIsotherm(model="DSLangmuir")` (recovers the same parameters); no refit to mixture data. Mixture: the two Wilkins 2017 Table 4.5 conditions (RH 0.441 at 22.9 C and RH 0.611 at 22.7 C, total 102 kPa, y_H2O = RH p_sat / 102 kPa, rest CO2), identical to `competitive_13X()`.
- Metric: relative error of q_CO2 and q_H2O vs measured, EDSL (before) vs IAST (after). Report whatever comes out. IAST is called an improvement only if the mean |CO2 error| decreases; the model code is NOT switched to IAST unless it also does not worsen H2O by more than 5 percentage points, and pyIAST would then be an optional dependency (so by default only reported, in `bench/sorbent/`).

## Amendment 1 (E6), written after seeing that the first fit has no root
What happened: running the pre-registered fit raised "no sign change" (nothing was scored). A diagnostic grid of the y = 0.15 / 0.5 breakthrough error against h_in showed the t50 error never reaches zero within [0.5, 300]: it is -45 / -44 % at 0.5, -38 / -39 % at 4 (current), -17 / -25 % at 20, -10 / -16 % at 60, -8 / -14 % at 150, -7.5 / -12.5 % at 300 W m-2 K-1 (even a nearly isothermal bed stays about 8-12 % early, so something else in the model also contributes). Peak temperature at 0.8 L over the same grid: 103/119, 96/113, 80/97, 70/84, 65/75, 63/71 C. I have therefore seen these curves; the choices below are made with that knowledge.
- Method 1 (as registered, reported as is): h_in minimising |t50 error| on y = 0.15 within [0.5, 300] -> boundary value 300; errors reported for both flows. No root exists, so Method 1 cannot meet its own target; it is not a pass.
- Method 2 (new, registered now before running it): fit h_in on the measured peak temperature at 0.8 L for y = 0.15 (68.5 C, Wilkins 2017 Fig. 4.11c, bracketing root search in [0.5, 300]); the peak temperature is the direct thermal observable, less affected by isotherm or particle-size error than t50. Held out: y = 0.5 t50 and peak temperature (79.0 C). Pass: held-out |t50 error| <= 15 % and |T_peak error| <= 10 K. Also report y = 0.15 t50 after the fit. The reverse direction (fit T_peak on y = 0.5, test on y = 0.15) is a robustness check.
- The sorbent_data.json 13X h_in is changed only if Method 2 passes both held-out criteria; otherwise the fitted value is reported and not adopted.
- Both methods and the baseline are reported. Because Method 2 was chosen after seeing the grid, its pass is weaker evidence than a pass registered blind.
