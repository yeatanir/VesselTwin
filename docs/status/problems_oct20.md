> **Superseded by `docs/status_oct21.md` (Oct 21, post-freeze integration).** Kept for history; do not quote its numbers as current.

# VesselTwin: problems and open risks

Oct 20, 2026. Exported from the Claude Docs version; this file is now the source of truth.

## Summary

VesselTwin runs end to end, but it has not yet shown that it gives better answers than a chemist's prior knowledge. The submission is Oct 22, so the next two days should go to evidence and polish, not new features.

1. **No demonstrated advantage.** On 8 modellable held-out MoS2 CVD observations the model scored 5/8, a blind no-tool baseline scored 6/8, and always guessing "increase" scored 4/8.
2. **Morphology prediction is at baseline.** The MoS2 shape map scores 0.50, equal to the majority class, and its rates are synthetic.
3. **Every CFD verification missed its target.** Tube: mesh 3-8% (target <2%), regime 65% (90%), surrogate error 94% (5%). Ampoule: regime 75-82% (90%), surrogate error 56% (5%), mesh study unfinished.
4. **Much of the physics rests on assumed numbers.** Lamp power, absorptivities, Wulff rates, heat-transfer coefficients and several sigmas are synthetic or recalled.
5. **The LLM part is not measured.** No real model backend exists; the extractor score and the agent loop come from stand-ins.
6. **Demo is unrehearsed.** No human run, no video, dashboard visuals unchecked.

## Evidence problems

The central question is whether VesselTwin tells a scientist something they could not get faster or better another way. Today the benchmarks do not show that.

| Test | Result | Problem |
| --- | --- | --- |
| Sensitivity direction vs 14 held-out papers | Model 5/8 on 8 modellable items; blind baseline 6/8; always-increase 4/8 | n is 8, one item is 12.5 points, so the model is neither better nor worse than the baseline |
| Same test, uncertain calls counted wrong | Model 4/8 | Only s11 is flagged uncertain |
| Items the model cannot express | 6 of 14 not modellable | Layer number, sulfur amount, MoO3 amount, MoO3 film thickness, vertical gap, lateral position have no model handle |
| MoS2 shape class vs 13 open-access papers | 0.50 accuracy, equal to majority baseline | Model predicts triangle for every case; Wulff rates are synthetic and were tuned to span classes |
| Ranking of atomistic calculations | Top-3 beats median random 0.96-1.00 | Benchmark is self-consistent (checked against our own model), not against experiments |
| Extractor on 33 real procedures | Stand-in precision 0.969, recall 0.832, 0 fabricated | Stand-in is a Claude subagent; the real backend is unscored; rules were tuned on this set |

Three weaknesses sit under these numbers.

- **Proxy choices are assumptions.** Nucleation density is mapped to MoO3 supersaturation, domain size to minus supersaturation, coverage to MoO3 flux. Three misses (s03, s04, s13) come out non-monotonic and may reflect the proxy, not the physics.
- **Fragile matches.** s09 was clipped to 300-400 C because the model's lower bound is 300 C but the paper used 200-400 C. s11 rests on one sweep point; s10 and s14 sweep ranges were assumed.
- **No test of the full claim.** Nothing yet shows that following VesselTwin's recommended knob or DFT calculation improves a decision.

## Per-vessel physics problems

All five vessels run at Tier 1; none is validated well enough to be called a predictor.

| Vessel | What is wrong | Numbers |
| --- | --- | --- |
| MoS2 CVD tube (flagship) | Morphology not predicted; Wulff rates synthetic; MACE kink energies over-bind MoS2 and collapse the map to all triangle_Mo; boat modelled as a disk, CFD gives a full ring; wall-uptake closure disagrees with CFD with position | Shape accuracy 0.50 = baseline; CFD/Tier 1 p(MoO3) median 0.92 but range 0.01-3.2; Mo:S ratio median 0.13 (range 0.005-0.44); MoO3 supply 2.9x; p(S2) 6.5x |
| Sealed ampoule CVT | Over-predicts published WO2+HgX2 rates; convection fit calibrated on a laminar sweep; positive-tilt small-diameter cases still wrong; stratification fix was chosen after seeing the CFD | Over-prediction 1x to 38x; convection fit held-out errors -41% to +46%; six +tilt cases Tier 1 2-4 vs CFD ~1 |
| Stirred flask | Stir-bar power number is a placeholder; CFD says Tier 1 underestimates power ~2x but CFD is not mesh-converged; Tier 2 not wired into tier2/openfoam.py | CFD Np ~1.0 vs Tier 1 ~0.5; ~30% change medium to fine mesh; no published stir-bar Np(Re) found |
| Sorbent bed | 13X breakthrough runs too hot; CO2/H2O competition underpredicted; heat-transfer coefficients synthetic | 13X -38%; CO2 -17%, H2O -41%; CALF-20 within -3% to +10% |
| Photoreactor (new) | Benchmark checks bookkeeping and analytic limits only; no measured photon flux compared; mixing-limit heuristic has no source; temperature rise is an upper bound | Lamp power, efficiency, heat fractions, absorptivities, wall indices are synthetic or recalled; Hatchard & Parker 1956 paper not opened when this was written (PDF now supplied) |

Two problems cut across vessels.

- **Passports are flagged synthetic.** Dashboard labels reflect this, so the headline numbers cannot be presented as predictions.
- **Tier 0 regime calls are unreliable.** They disagree with CFD in 18-35% of tube and ampoule cases, so Tier 0 should not be shown as a trusted triage step.

## Verification and CFD problems

The plan set three targets for each CFD-verified vessel: mesh change under 2%, Tier 0 regime agreement of at least 90%, and a surrogate within 5%. None was met.

| Target | Tube | Ampoule |
| --- | --- | --- |
| Mesh change, medium to fine (<2%) | 3-8% across three operating points; boat release drifts 2-5% per level | Coarse to medium 0.03% (diffusion), 4.8% (weak), 10.1% (tilted); finest level not finished |
| Tier 0 regime agreement (90%) | 65% of 40 cases; all 14 misses are Tier 0 transport-limited vs CFD reaction-limited | 81.7% at threshold 1.1, 75.0% at 1.2 (was 65.0% / 71.7%) on 60 cases |
| Surrogate held-out error (5%) | Mo:S mean 94%, median 31% | Mean 56%, median 40%; 20% of cases within 5% |

Other problems.

- **The ampoule improvement is not held out.** The fix to the stratification scale was chosen after seeing the CFD discrepancy.
- **Surrogates are too small.** 60 ampoule cases and 40 tube cases in 5 dimensions cannot learn outputs that span 5-25 orders of magnitude or switch sharply between regimes.
- **CFD scope is narrow.** Ampoule sweep is laminar, uses default thermodynamics and fixes the sink at 800 C; tube mesh was tested on three points; flask is a rotating-zone model at about 7k cells.
- **Shared-code risk.** The tube agent changed the shared `_fv` in `tier2/openfoam.py`; the ampoule CFD data predate that change.
- **Flask Tier 2 is not wired in.** The case writer exists but is not exposed through `tier2/openfoam.py`.
- **COMSOL remains in PLAN.md** although the project is OpenFOAM-only.

## Data and literature problems

A sourced constant was wrong by 30-60x until a literature check caught it, so every other "sourced" value deserves the same suspicion.

- **Past error.** The MoO3 vapour pressure came from an OCR'd Simnad and Spilners fit and was 30-60x too low. Edison found Smolik et al. (HSC fit, about 53 Pa at 1000 K); Berkowitz 1957 points sit about 2x higher. All tube results before Oct 20 are invalid.
- **Still synthetic.** Wulff edge rates, the photoreactor's lamp and absorptivity values, sorbent heat-transfer coefficients, and many Monte Carlo sigmas.
- **MLIP limits.** MACE-MP-0 over-binds MoS2 by about 0.4 eV per formula unit; no DFT or published edge-energy table was found at the time (Rosen et al. 2018, DOI 10.1021/acs.jpcc.8b02524, with SI data, has since been supplied). E_kink_Mo = 0.52 +/- 0.21 eV and E_kink_S = 0.008 +/- 0.18 eV rest on an assumed 0.15 eV floor, and a +/-0.3 eV shift in the chemical-potential offset moves the map by about 13 e-folds.
- **Sensitivity benchmark sources.** Most quotes (s01-s08, s12, s13) passed through a page summariser and are not checked verbatim; s04's 40% value is unverified; DOIs for s09, s10 and s14 came from memory; the Wang/Warner licence is unknown. Four candidate papers returned 403 or login redirects.
- **Gaps nobody filled.** No clean sulfur-boat-position study, no powder-CVD source-to-substrate distance study, no tube-diameter study, no measured Mo:S ratio, no published stir-bar Np(Re).
- **Tool limits.** Valency returns papers and no numbers, and its corpus lacks most chemistry journals. Edison gives cited numbers and honest "not found", but every job costs a credit and answers need checking against the source. The three newest Edison answers (flow rate, substrate position, sulfur supply) are saved in `docs/literature/` but not yet merged into the benchmark.
- **Licensing.** Only open-access excerpts may be committed; no figures from papers.

## LLM, demo and product problems

Judges score a scientific-intelligence workflow, and the language-model parts are the least measured.

- **No real LLM backend.** There is no Anthropic API key and no budget for one. The extractor numbers and the agent timeline come from stand-ins: a blind Claude subagent and a scripted policy. The real backend (local MLX) is untested.
- **Reasoning trace is scripted.** The five-step timeline replays a fixed policy; it does not choose tools. Its sign-flip banner never fires on the stored data, and some literature excerpts match only loosely (two shared content words).
- **Dashboard visuals unchecked.** The only browser available to the agent was headless Brave and captured loading skeletons. Light and dark readability, the timeline rail and chart appearance are unverified. The user will check by eye in Safari.
- **Demo unrehearsed.** The scripted dry run passes 8 steps in about 9.5 s cold compute, but no human has run it, no one has timed it, and there is no video or slides.
- **Submission format is unconfirmed.** A reviewer cites 8:00 PM Eastern on Oct 22, a four-minute video and a one-page write-up. Our plan says two minutes. Check the event Slack.
- **Scope.** Five vessels, two literature tools, two CFD tiers and a dashboard are too many threads. The strongest story is the evidence trail and flagged uncertainty, not predictive accuracy.
- **Unbuilt ideas.** MolSSI xnn and LAMMPS integration is only a proposal; no code exists. Photoreactor has no dedicated plot because the dashboard does not render `extras`.

## Process and hygiene problems

- **Edison key exposure.** The key was pasted into the chat twice, so it sits in the transcript. It has only been passed inline as an environment variable and is not in any repo file (scanned before each push). Rotate it once the literature work is done. It is meant for Literature jobs only, one credit each.
- **Git history.** A 2 MB compiled OpenFOAM `.o` file was pushed in commit da8335d and untracked later; it stays in history until the history is rewritten.
- **Agent mistakes.** The tube agent ran a blanket `pkill -f buoyantPimpleFoam`, which killed its own cases and could have hit another agent's runs. The permission classifier has denied several shell calls; none were worked around.
- **Shared-code edits.** The tube agent changed the shared `_fv` in `tier2/openfoam.py`, which affects the ampoule builder.
- **Rate limits.** Agents were interrupted several times by usage limits and resumed, so work was split across sessions.
- **Flaky dashboard test.** `test_app_loads` failed once on a vessel that was mid-edit (pyarrow could not convert 'Ar') and passed on rerun. The cause is not pinned.
- **Stale docs.** The earlier status document is out of date, `PLAN.md` still mentions COMSOL, and `docs/harness_snapshot.json` must be regenerated before each final commit.
- **Tests are green but narrow.** 153 pass and 5 skip; many tests check bookkeeping or analytic limits, not agreement with experiments.
- **Residual unknowns.** The OpenFOAM volume must stay mounted for Tier 2; name and licence are undecided; OSI submission requirements are unconfirmed.

## Recommended order of work and decisions needed

Fix the story before adding features: show evidence and flagged uncertainty, label everything, and rehearse the demo.

1. **Confirm the submission format** (deadline, video length, write-up length) in the event Slack.
2. **Merge the three Edison answers** into the sensitivity set after checking each excerpt against its source; rescore model and blind baseline on the larger set. Treat s01-s14 as a development set and the verified Edison items as the only held-out set.
3. **Check the dashboard by eye**: open the Reasoning trace tab in light and dark, fix the timeline rail and chart problems.
4. **Change the headline**: lead with the evidence trail and labelled uncertainty; keep the shape map as a hypothesis and show the 5/8 vs 6/8 result openly.
5. **Run the demo by hand twice with a stopwatch**, then record the video.
6. **Clean up**: remove COMSOL from PLAN.md, wire or drop the flask Tier 2 case, regenerate the harness snapshot, run the full tests, push.
7. **Rotate the Edison key.**

Decisions for the user:

- Whether to spend more Edison credits (one per Literature job) on the gaps above.
- Whether the stand-in numbers are labelled as stand-in in the submission, given no Anthropic API key.
- Whether to rewrite git history to drop the compiled files.
- Whether to pursue the xnn and LAMMPS demo after the polish pass, or drop it.
- Whether the photoreactor stays in the demo given its weak benchmark.
