# Track K results: why the substrate MoO3 flux does not follow the boat (pre-registered in docs/prereg/track-k.md, commit f344577)

**Verdict: intended physics of the Tier 1 equations, not a defect. No model change, no constant changed.** All numbers are development data from `bench/track_k/trace.py` (read-only call of the unmodified `march`; run with `MoO3.psat_model = smolik_liquid_cc` so the old 1068 K clamp does not mask the supply change). Track I's absolute 4.563e-6 is not reproduced (mine 3.977e-6, base parameters differ); the insensitivity is.

## Where the signal is lost
Boat 800/825/850 C: supply NM_in 1.84e-7 / 2.86e-7 / 4.35e-7 mol/s (x2.4), but ~98 % is taken up by the wall within ~12 cm of the boat. Wall at the boat is 1022 K (psat 141 Pa) and falls along the furnace ramp to 853 K at the substrate (psat 0.028 Pa). The gas that reaches the substrate carries 2.90e-9 mol/s at every boat T, p = 3.95 Pa (139x supersaturated): this is the lag of a gas relaxing onto a steeply falling wall saturation curve, with memory of the inlet exp(-NTU), NTU = 11.5 boat -> substrate. Flux 3.977e-6 / 3.978e-6 / 3.979e-6. With the default `smolik_hsc` law the 800-850 C supply is additionally clamped (1.69/1.71/1.74e-7) and nothing changes at all.

Audited and ruled out (D1-D3 of the pre-registration): no cache; `MoO3_to_substrate_frac` is an output (deposit on substrate / supply), not a cap; the only clips are max(flux, 0), ys <= 0.999 and the cell-overlap fraction; S2 supply does not enter the MoO3 balance; species basis consistent (formula units in NM, pM, Nsat, psat); mass-balance error < 1e-9.

## Memory test (elasticity e = d ln F / d ln NM_in, boat 800 -> 850 C)
| x_substrate (cm from boat) | NTU boat -> substrate | e |
|---|---|---|
| 0.5 | 1.20 | 1.64 |
| 1 | 1.65 | 1.62 |
| 2 | 2.76 | 1.43 |
| 4 | 4.38 | 0.50 |
| 8 | 7.90 | 0.004 |
| 12 (default) | 11.5 | 0.000 |
Flow 50 / 100 / 200 sccm at default geometry: NTU 21.6 / 11.5 / 4.3, e = 0.000 / 0.000 / 0.027. Pre-registered pass: e monotone decreasing in NTU (yes), e < 0.05 at default (yes), e > 0.5 for NTU < 1: vacuous, the smallest reachable NTU is 1.2 because uptake starts at the boat; e >= 0.5 up to NTU 4.4 (0.503, borderline). Verdict criterion met. Also note F is not monotone in x_substrate (the wall-temperature ramp, not a bug).

## Stored CFD (docs/tube_cfd_verification.json, no new runs)
Substrate p(MoO3) against boat supply, elasticity: CFD 650 -> 700: 0.52, 700 -> 750: 0.15, 750 -> 800: 0.001 (p 1.50045 vs 1.50052 Pa, the same 4-digit identity; supply only +4 % there because the CFD also used the clamped law). Tier 1: 0.69, 0.48, 0.10. Boat-uptake fraction in CFD 0.69, 0.90, 0.989. So CFD shows the same saturation, stronger than Tier 1 at 700-750. CFD/Tier 1 p ratio: boat 650 1.25, 700 0.80, 750 0.40, 800 0.33 (unchanged by this track). Tier 1 therefore over-predicts the plateau 2.5-3x and under-saturates in the middle; the cause named in the stored findings is the wall-uptake closure (uniform Sh = 3.66, no entrance effect; substrate 6 cm CFD/T1 2.86, 20 cm 0.008), i.e. a closure-accuracy limit, not a hidden cap.

## Consequences for the Track A/I items (no re-score; model unchanged so before = after, stored tables in docs/track_a_results.md and docs/track_i_results.md stand)
- j1-j3 (T_boat 800-850 C): not decidable by this model in the default geometry: the substrate is NTU ~ 11 from the boat, so its flux is set by the furnace ramp and flow, not the boat. Under the default law it is also clamped. Observables that respond to boat supply need the substrate within ~4 cm (NTU < ~4) or a lower wall uptake (colder boat than wall is not the case here: wall 1022 K vs boat 1073 K).
- s05/s06 (MoO3/S inventory): supply is never inventory-limited, and the substrate flux is insensitive to supply anyway.
- Flow items (s01, s03, s04): F changes through NTU and Q, not through supply; non-monotone in flow (5.5e-7, 1.09e-6, 1.06e-6 at 50/100/200 sccm).
Anything that would change this (axial diffusion, developing-flow Sherwood, re-evaporation, radial profile) is a model-extension task, listed in the module docstring as unresolved; not done here. Neither CFD nor the model supports "the model cannot respond to boat T" as a code bug.

## Tests added (tests/test_track_k.py, 5)
NTU -> 0 limit returns the supply; mass balance; F non-decreasing in boat T 700-900 C (liquid law); F rises > 1 % per 25 C with the substrate 1 cm from the boat; documented saturation (|dF/F| < 1 % for 800 -> 850 C at default geometry while supply more than doubles).

## Changed constants / equations
None. Source tags: n/a.
