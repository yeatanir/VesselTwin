# MoS2 shape benchmark (first honest test of the kinetic-Wulff shape map)

> Superseded in part by `docs/track_a_results.md` (Track A, Oct 21): new proxies, handles and DFT Mo-edge option. This file documents the earlier run.

Run: `python -m bench.shape_score` (offline, ~2 s; `--write` refreshes `bench/shape/inputs.json` and `predictions.json`).
Tests: `tests/test_shape_bench.py` (scoring maths on a hand-made case; stored inputs reproduce stored predictions).

The shape rates in `vessels/cvd_tube/wulff.py` are synthetic and were tuned only so the default tube spans all classes. Nothing here
was tuned against these papers. No model parameter was changed to improve the score; suggestions are listed at the end, not applied.

## Data
`bench/shape/papers.json`: 14 cases from 13 open-access papers (CC BY, CC BY-NC, CC BY-NC-ND; PMC OA subset), with DOI, licence,
the verbatim methods excerpt used as input, the verbatim phrase giving the REPORTED shape, and an independent FIGURE label.
Of the 10 existing `real_*_cvd_tube` procedures, 7 are used (real_01, 02, 04, 07, 08, 09, 10). Excluded: real_03 (WS2, not MoS2),
real_05 and real_06 (the paper text does not report the flake shape of the growth). Six papers were added (Nano-Micro Lett. 2015,
Nanomaterials 2025, Sci. Rep. 2017, ACS AMI 2020, Nanoscale Adv. 2021, ACS Omega 2025). One paper (Nanomaterials 2025) contributes two
cases (Mo:S 1:15 triangle, 1:10 hexagon); the model cannot see the mass ratio, so both have identical inputs.

Labels: `triangle`, `truncated_triangle`, `hexagon`, `mixed`, `other` (round, star, dendritic, erect petals). The model can only
output the first three.
- REPORTED label: from the text, phrase stored verbatim (checked as a substring of the paper).
- FIGURE label: I viewed the paper's own growth figure (downloaded to a scratch directory) and classified it. **Figures are never
  stored or redistributed**: the repo holds only the label, the figure number and a short description of what was seen. Text and
  figure disagree for S04 (text "truncated triangles", figure erect curved flakes), S10 (mixed vs irregular triangles) and S12
  (mixed vs star-like). S02's figure is too low-magnification to classify (its label is null, excluded from the figure score).

Scope: 8 cases (7 papers) are "in scope": MoO3 powder plus sulfur boats, as the model describes. 6 cases use a different precursor or
promoter (MoO2, spin-coated liquid Mo, NaCl, KCl+PTAS, Au nanoparticles, Mo film). They are scored separately as "all" because the model has no such inputs.

## Inputs and completeness
`SetupSpec` from `llm.extract.extract` (`replay` of `bench/llm_runs/claude_agent` for real_*, except real_10 where replay was empty so `rules`; `rules`
for new papers), plus manual completion only for parameters the paper states and the extractor missed or got wrong; every manual item
carries a verbatim span (or "Table 1"), and `override` / `derived` flags (e.g. flow = Ar 17 + H2 10 sccm summed). Rules errors that I replaced:
carrier N2 for an Ar/H2 run (S04) and T_furnace 320 C instead of 700 C (S07). Everything else stays at the ParamDef default.
Completeness = known / 10 of {T_boat_Mo, T_boat_S, T_furnace, flow, carrier, tube_id, x_substrate, x_S_boat, x_MoO3, pressure}.
It ranges 0.1 to 0.8 (median 0.4). Only S08 (0.8, a full parameter table) is nearly complete. Boat positions (x_S_boat, x_MoO3) are never
known in absolute terms, so they are always defaults; substrate position is known in 5 of 14 cases, otherwise the default 12 cm is used
(prediction made at 12.5 cm from the MoO3 boat), which is a coin flip dressed as a prediction.

## Prediction
`wulff.shape_map` (the `extras['shape_map']` of `api.solve`, 40 points, 30 Monte-Carlo draws) at the substrate centre
(`x_substrate + length/2`). Triangle_Mo and triangle_S are merged into `triangle`. The model abstains if the centre is outside the map or the
p05..p95 band of the shape index spans two classes (it did so in 4 of 8 in-scope cases; the point class is still reported).

## Results (reported label as reference)
| | n | accuracy | majority baseline | defaults-only |
|---|---|---|---|---|
| in scope | 8 | 1/8 = 0.12 | triangle 4/8 = 0.50 | 0.12 |
| all cases | 14 | 3/14 = 0.21 | triangle 7/14 = 0.50 | 0.07 |

Against the figure labels: 1/7 (in scope), 3/13 (all), majority 0.43 / 0.54. Counting band-spanning predictions as abstentions
changes no accuracy (they were all wrong anyway); of the 4 confident in-scope predictions 1 is right (S03).
Per-case table: run the script (id, scope, completeness, reported, figure, predicted, abstain reason, position).

Confusion, in scope (rows reported, columns predicted):

| | triangle | truncated_triangle | hexagon |
|---|---|---|---|
| triangle (4) | 1 | 3 | 0 |
| truncated_triangle (1) | 1 | 0 | 0 |
| hexagon (1) | 0 | 1 | 0 |
| mixed (1) | 1 | 0 | 0 |
| other (1) | 1 | 0 | 0 |

The model never predicts hexagon here. It does not beat "always say triangle" (0.50), and the default input already scores the same as
the paper-specific inputs, i.e. the extracted conditions do not yet change the answer in a way that matches reality.

## Cases where the model cannot say
- Band spans classes: S01, S02, S05, S06 (and out-of-scope S10, S11): the truncated/triangle/hexagon boundary lies inside the
  parameter uncertainty at that position.
- Classes it has no output for: round/erect/star/mixed (S04, S07, S08, S12, S14; S10 partly). These are 5 of 14 cases (4 of 8 in scope).
- No boundary / position information: S05, S06 (no boat T, flow, position), S02, S11 (position not given).
- Inputs it does not have: precursor mass ratio (S05 vs S06), halide/seed promoters, MoO2 or film precursors.

## Limitations
Small n (8 in scope), one reference condition chosen per paper by me, multi-condition papers collapsed to a single label (S04 uses the
midpoint 11 cm of a 9-13 cm series), label noise (text vs figure disagree in 3 cases, the reported label is itself the authors'
wording), and publication bias toward clean triangles (the majority class is 50%). Missing absolute boat positions mean the model's
position axis is essentially unconstrained. The substrate temperature stated by papers is not the boat temperature in the model (S01, S08). SEM/AFM
figures at one magnification can hide the mixture. This benchmark can falsify the model; with n = 8 it cannot validate it.

## Suggestions (NOT applied; would be tuning to the benchmark unless justified independently)
1. Add an explicit "unresolved/mixed" output when the p05..p95 band spans classes, instead of a point class: it matches how papers
   report such positions ("mixed", "unusual shapes") and removes false confidence.
2. Triangle bias: 4 of 8 reported triangles were predicted truncated, i.e. the default feed ratio places the substrate near the
   truncation boundary. The synthetic S-edge/Mo-edge rate ratio (A_S = 15 vs A_Mo = 0.06 um/s/Pa, retuned Oct 18) should be re-anchored
   to measured edge energies/barriers (DFT/MLIP closures), not moved to fit these labels.
3. Add inputs for the missing physics before scoring more papers: precursor mass (boat supply), halide promoters, round/dodecagon
   shapes at low temperature (armchair edge channel).
4. Require substrate position, boat temperatures and boat spacing in the extractor's "must ask" list: completeness is the binding limit.
