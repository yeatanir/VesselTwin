# Track K progress (branch track-k from origin/polish b5f0ee2)

Files I will touch: vessels/cvd_tube/* (only if a defect is confirmed), bench/track_k/*, tests/test_track_k.py, docs/prereg/track-k.md, docs/track_k_results.md, docs/progress/track-k.md, docs/handoff/requests-k.md. No PIDs, no OpenFOAM, no Edison.

## Step 1 trace (read-only; bench/track_k/trace.py calls the unmodified `march`)
Defect candidates audited in code (vessels/cvd_tube/__init__.py `march`): no cache anywhere; no cap on MoO3_to_substrate_frac (it is an output, dep["Msub"]/NM_in); only clips are max(flux,0), min(ys,0.999), fsub clip to cell overlap; S2 supply does not enter the MoO3 rate; species basis consistent (NM in formula units, pM = Pt NM/Nt, Nsat = psat Nt/Pt, psat = total formula-unit pressure, boat uses psat/nol and multiplies by nol).
Observations (default tube, MoO3.psat_model = smolik_liquid_cc so the 1068 K clamp is out of the way; Track I's absolute flux 4.563e-6 is not reproduced here, mine is 3.977e-6, probably different base params; the insensitivity is reproduced):
- boat 800/825/850 C: NM_in 1.84e-7 / 2.86e-7 / 4.35e-7 mol/s; gas still carrying at substrate NM_sub 2.899e-9 / 2.900e-9 / 2.901e-9; pM_sub 3.949 / 3.950 / 3.950 Pa; flux 3.977e-6 / 3.978e-6 / 3.979e-6. With the default smolik_hsc law the 800-850 supply is clamped (1.69/1.71/1.74e-7) and the flux is identical to 4 digits.
- Where the supply goes: ~98 % is taken up by the wall in the first ~12 cm after the boat (wall at the boat 1022 K, psat 141 Pa, then the furnace ramp cools the wall and psat falls 141 -> 0.14 Pa over 12 cm). The gas at the substrate (wall 853 K, psat 0.028 Pa) is at 3.95 Pa = 139x supersaturated: it is the lag of a gas relaxing onto a steeply falling wall saturation curve, not memory of the boat. The inlet memory is exp(-NTU) with NTU between boat and substrate >> 1.
- Flow 50 / 100 / 200 sccm: flux 5.5e-7 / 1.09e-6 / 1.06e-6; frac_sub 0.021 / 0.037 / 0.034 (non-monotonic).
Conclusion so far: the insensitive step is the wall uptake (Sherwood/NTU), it saturates by the equations, no clip or cap is involved. Decision and criteria are pre-registered in docs/prereg/track-k.md.

## Done (Oct 21)
Verdict: intended physics; no model change. Results docs/track_k_results.md; tests tests/test_track_k.py (5). `make test`: first run 37 failures all in tests/test_vessel_view.py (passes alone, 28/28; flaky under load), second full run 267 passed, 6 skipped, 1 xfailed. Requests: docs/handoff/requests-k.md. Changed constants/equations: none.
