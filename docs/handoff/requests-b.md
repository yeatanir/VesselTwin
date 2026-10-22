# Track B requests to owners of files I do not own

## R1. Tube Tier 0 regime call (vessels/cvd_tube/__init__.py, Track A)
Why: scored held-out-style in `tier2/verification/b3_results.json`: base 26/40 = 65 %, new rule at the fixed, un-fitted threshold 1 gives 37/40 = 92.5 %
(half-split fitted threshold 97.9 +- 2.6 %, 5 seeds). The rule is designed with knowledge of the miss mechanism (see report), so treat it as a hypothesis scored against an agent-chosen CFD label.
Exact change in `tier0(p)`: replace
```
    Da = p["Sh"] * DM / d * np.pi * d * dx / Qf  # wall-uptake NTU between boat and substrate
```
by
```
    x = np.linspace(p["x_MoO3_cm"] / 100, (p["x_MoO3_cm"] + p["x_substrate_cm"] + p["substrate_length_cm"] / 2) / 100, 400)
    s = np.clip(1 - psat_MoO3(p, twall(p, x)) / float(psat_MoO3(p, p["T_boat_Mo_C"] + 273.15)), 0, None)  # wall takes up only where colder than the boat
    Da = p["Sh"] * DM / d * np.pi * d / Qf * np.trapezoid(s, x)
```
(`Da_wall` in `nums` then means Da_eff). Reference implementation and unit tests: `tier2/verification/tier0.py::tube_da_eff`, `tests/test_verification_b.py`.
Also: the existing `Sh = 3.66` was already in the old Da, so the miss was not the Sherwood number but the missing driving-force term.

## R2. Uncertainty band should include the discretisation error (core/, Track A/F)
Where Tier 2 `Passport` Dist values are built (`tier2/openfoam.py` is mine; the band widening for the dashboard/credibility is in core/):
for a Tier 2 quantity q with a GCI entry in `tier2/verification/gci.json` (match vessel + quantity), set
`p05 = p50*(1 - u)`, `p95 = p50*(1 + u)` with `u = max(gci_fine, existing relative half-width)`; if the entry has flag "unsteady" or "oscillatory", show the flag text next to it.
Ampoule f_CFD (D10 diffusion 0.0 %, D20 weak 0.5 %, D25 tilted 2.1 %, D40 strong 13 % unsteady) and tube quantities (0.8-13 %, mostly Fs = 3 fallbacks) are in the file.
Lookup is by case, not by arbitrary input, so apply it as a typical-band, not a per-input prediction.

## R3. tiers.json status text (Track F applies)
- tube Tier 0: "Tier 0 regime call re-derived with a wall-uptake driving-force term; agrees with the CFD convention on 37/40 sweep cases (was 26/40). The CFD label is an agent-chosen convention (63 % uptake), not measured."
- ampoule Tier 0: "81.7 % (threshold 1.1) / 75 % (1.2) agreement with the CFD f>1.1 / f>1.2 convention; the stratification fix adds nothing over no stratification term when scored held-out (see tier2/verification/b3_results.json)."
- surrogates: "multi-fidelity correction (GP on log10 CFD/Tier 1) does not reach 5 %: LOO median error 27-36 %; tube outputs span 3.5-6.6 decades of CFD/Tier 1 and are not learnable from 40 cases."
- mesh: "ampoule finest mesh done; GCI 0.0-2.1 % on 3 steady cases, 13 % (unsteady, not meaningful) on the strong-convection case; tube GCI 0.8-13 % mostly oscillatory."
- flask: "Tier 2 reachable via tier2.openfoam.write_case('flask', ...); Np_torque closure is a single-point value, see docs/flask_closure_np.json."

## R4. Flask Np closure wiring (core/ or wherever closures live)
`docs/flask_closure_np.json` holds the entry (value, GCI band, status "computed"). Not wired into vessels/flask Tier 1 (single point, not a curve; Tier 1 keeps Np_inf + Kp/Re).
If wired, it may only override Tier 1 Np inside the validity range recorded in the entry (one Re).

## R5. Surrogate wiring (app/dashboard.py, Track D/F)
New models: `surrogate/data/corr_*.json`, API `surrogate.correction.predict(path, values, tier1_value)` returning value, lo, hi, in_range. Old `surrogate/ampoule.py`, `surrogate/tube.py` are unchanged and still used by the dashboard.
Recommendation: show the corrected value only with its band and the label "LOO median error 27-36 %, target 5 % missed".
