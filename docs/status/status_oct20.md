> **Superseded by `docs/status_oct21.md` (Oct 21, post-freeze integration).** Kept for history; do not quote its numbers as current.

# VesselTwin: full project status (Oct 20)

Snapshot from earlier on Oct 20, exported from the Claude Docs version. Superseded in part by `problems_oct20.md` and later commits (photoreactor vessel, reasoning-trace tab, sensitivity benchmark, tube and ampoule CFD verification results, ampoule stratification fix, test count now 153 passed / 5 skipped). Where this file says an agent "is running" or a count is 139, the later document is correct.

## Summary

VesselTwin runs end to end and is well tested (139 tests pass at the time), but most of its chemistry numbers are still placeholders, and the first real test of the flagship shape prediction landed exactly on the majority baseline.

It reads a synthesis procedure, models the flow and heat in the vessel, and tells the experimentalist which variable matters and the simulation person which atomistic calculation to run. Four vessels share one core: MoS2 CVD tube, sealed ampoule, stirred flask and sorbent bed (a photoreactor was added later). The code is pushed to the private repo, and submission is Oct 22. The strongest honest pitch is the workflow and the verification harness, not a predictive claim.

## What is built

The shared core, four reduced-order vessel models, three OpenFOAM cases, an extractor, a ranking module and a dashboard all exist and run.

| Component | State |
| --- | --- |
| Contracts: SetupSpec, Passport, Closure | Done; every value carries a source, a status (stated, default, missing) and a synthetic tag |
| Tier 1 solvers: MoS2 tube, ampoule, flask, sorbent | Done; 2 ms to 0.3 s per solve, uncertainty as p05/p50/p95 |
| Editable parameters | Done; every dimension and knob has a unit, bounds, uncertainty and source; JSON schema, presets and a CLI for a future front end |
| Registry | Done; a new vessel file dropped into the folder appears in the dashboard, with a template and a guide |
| Extractor (procedure text to SetupSpec) | Offline rules backend and a replay backend work; Anthropic and local-MLX backends are written but never run |
| Brief and ranking for the simulation person | Done; ranks atomistic calculations by outcome change through Tier 1 |
| Tier 2 OpenFOAM v2512 | Tube, ampoule (custom solver with species buoyancy) and flask (rotating zone) cases run; Tier 2 results can be read back into a passport |
| Atomistic closures | MACE-MP-0 edge energies and kink energies for MoS2, as Closure objects; no barriers |
| Kinetic Wulff shape map | Done, with a re-anchored equilibrium term; see what fails below |
| Dashboard and tooling | Streamlit app with editable form, vessel, chemistry-set and tier dropdowns, Brief and Credibility tabs; README, requirements, CI workflow |
| Benchmarks | 33 real annotated procedures (extractor), 14-case MoS2 shape benchmark |

COMSOL was dropped by decision; everything runs on OpenFOAM.

## What is verified

139 tests pass with 5 skipped (OpenFOAM solver tests skip when the solvers are not on the path); the checks below are the ones with numbers.

| Check | Result |
| --- | --- |
| Sorbent: isothermal breakthrough vs analytic shock time | Within 3% |
| Sorbent: generic LDF-Langmuir reference column (arXiv 1907.00195) | Within 3%; mass balance under 0.2% |
| Sorbent: CALF-20 CO2/He breakthrough vs published | Mean breakthrough time off by -3%, +2%, +10% |
| Ampoule: OpenFOAM vs Tier 1, diffusion-limited cases | Within 2% |
| Ampoule: CFD convection scan (13 cases, two meshes) | Tier 1 enhancement refitted on 5 diameter points; held-out errors -41% to +46% |
| Flask: OpenFOAM vs Tier 1 | CFD stir-bar power number about 2x Tier 1 (about 1.0 vs 0.5 for water); mesh change about 30%, so a factor-of-2 flag |
| Tube: OpenFOAM vs Tier 1 (older constants) | Mo:S 0.048 vs 0.032; both within a factor of 2; superseded by the later tube verification |
| Extractor on 33 real procedures, stand-in model blind to gold | Precision 0.969, recall 0.832, 0 fabricated values |
| Extractor, rules backend | Precision 0.953, recall 0.726, 0 fabricated; tuned on this set, so not out-of-sample |
| Ranking: best of the top 3 beats the median random parameter | 0.96 to 1.00 over 50 seeds (all-parameter pool) |
| Fresh-copy install and tests | About 1 minute; dashboard dry run about 9.5 s of compute |

The stand-in model is a Claude agent, not the Anthropic API.

## What fails or is not yet real

The MoS2 shape prediction does not beat "always say triangle": 0.50 accuracy on 14 papers against a 0.50 majority baseline, because the model predicts a triangle for every case.

- **Shape map.** The Wulff rates are synthetic and were tuned so the default spans all shape classes. With the machine-learned kink energies applied, the map collapses to all Mo-edge triangles. The Mo-edge equilibrium pressure becomes about 5e6 Pa, because the potential binds sulfur at a kink by about 0.5 eV against about 1.15 eV needed.
- **Edge energies.** MACE-MP-0 numbers, not DFT; it over-binds MoS2 by about 0.4 eV per formula unit. Kink energies are end-state energies, not barriers.
- **Ampoule.** The model over-predicts published WO2 + HgX2 transport rates by about 1x to 38x; convection does not explain it. Diffusivity, agent loading and temperature dependence are suspects.
- **13X sorbent.** Breakthrough is off by about -38% (bed runs too hot); CO2/H2O competition is underpredicted by 17% and 41%.
- **Earlier tube numbers were wrong.** The "sourced" MoO3 vapour pressure came from an OCR'd page and was 30 to 60 times too low; it is replaced by the Smolik fit (about 53 Pa at 1000 K). Any tube result from before Oct 20 used the wrong number.
- **Mesh convergence.** The flask CFD changes about 30% on refinement and the ampoule convection about 4 to 16%; the tube was not checked at the time of writing.
- **Not built or not done.** Surrogates for the Tier 2 cases and the Tier 0 vs CFD regime agreement test (done later, targets missed); the 100-procedure benchmark (33 exist); any run of the real Anthropic backend; the 329-reaction supplement check; a stir-bar power-number source (none published).

## Literature tools for parameter generation

Two literature tools now feed the parameters: Edison Scientific's Literature agent, which reads papers and returns cited answers, and Valency, a semantic search over arXiv, PubMed and other preprint servers that returns papers but no numbers. Valency is a search tool, not an agent.

The loop is: a parameter is missing or weakly sourced, one literature question goes out, the cited value goes into the parameter's source tag, and anything the tools cannot find stays tagged synthetic. Edison ran 5 jobs, one each (plain Literature variant, ids saved in `docs/literature/jobs.json`, the key never stored); three more were run later (flow rate, substrate position, sulfur supply). The job cost field came back empty, so credits used are unconfirmed.

| Question | Edison Literature | Valency |
| --- | --- | --- |
| MoO3 vapour pressure | Found the [Smolik et al. 2000](https://doi.org/10.2172/752007) HSC fit (about 53 Pa at 1000 K) and Berkowitz 1957 points (about 2x higher); exposed the tube's earlier value as 30 to 60x too low | Returned gaseous ternary molybdates, the wrong species |
| Sulfur vapour pressure | Gave the [Rau et al. 1973](https://doi.org/10.1016/S0021-9614(73)80089-8) fit and a low-temperature fit; the tube's existing fit agrees within about 3 to 5% | One relevant hit, [Jackson, Tiana and Walsh](https://arxiv.org/abs/1509.00722), on sulfur chemical potential |
| MoS2 edge energies | No numbers (said it could not read the tables); corrected the Cao et al. reference to J. Phys. Chem. C and pointed to Rosen 2018 | Surfaced newer MoS2 growth papers (Mula 2020, Dong 2023, Kang 2024), abstracts unread |
| Stir-bar power number | Found no published bar-specific correlation | Context papers on magnetic stirring only |
| 329-reaction study | Identified the [Synlett paper](https://doi.org/10.1055/a-2384-7220) but could not see its supplement | Did not find it |

In short, Edison gives citable numbers and honest "not found" answers; Valency finds papers fast but its corpus lacks most chemistry journals. Edison's answers changed the model: the MoO3 default was replaced and the sulfur fit's source tag was upgraded. Both tools were used with explicit instruction not to quote numbers they could not read.

## Proposed: MolSSI xnn and LAMMPS

xnn would give the atomistic side one maintained interface to many machine-learned potentials, and LAMMPS would let the project run molecular dynamics for closures, but neither is built yet; both are proposals, not features.

According to its [project page](https://molssi-ai.github.io/xnn/), xnn is a PyTorch library of machine-learned interatomic potentials (version 0.1.0, pre-1.0, so interfaces may change). It reimplements MACE, NequIP, Allegro, AIMNet2 and others behind one interface, loads MACE and AIMNet2 foundation models with `from_pretrained()`, runs through ASE, can export TorchScript models to LAMMPS for MACE, NequIP, Allegro and AIMNet2 (among others), and can serve as a MolSSI Driver Interface engine. It also offers D3/D4 dispersion and long-range electrostatics add-ons. The page does not state the install command or the licence, so both need checking before any commitment.

**Where it would fit**

- Replace our MACE loader, which needed a runtime patch because the cached model files did not load with the installed e3nn 0.6, with one supported call.
- Add dispersion corrections, which the edge-energy work lacks.
- Run LAMMPS molecular dynamics through the TorchScript export for closures that single-point energies cannot give: attachment events at an edge, S2 adsorption and dissociation, hop rates.

**A small demo, honestly sized**

- Step 1 (about half a day): recompute the existing MoS2 edge and kink energies through xnn and ASE and compare with the current MACE numbers. This is checkable and shows xnn can be a drop-in.
- Step 2 (stretch, about a day, depends on a working LAMMPS build with ML support): a short NVT run of a MoS2 zigzag ribbon with an S2 molecule near the Mo edge, showing the path from MD to a Closure object.
- Do not use the foundation model for gas-phase diffusion in argon: it was trained mostly on crystals and will not describe dilute gases well, so that closure would not be defensible.

**Risks:** pre-1.0 software, unverified install and licence, the potential's known over-binding (about 0.4 eV per MoS2 formula unit), and little time before the Oct 22 submission. Do step 1 only if time allows and describe LAMMPS as the roadmap capability.

## Demo status

The demo is only partly done: a scripted dry run of the 90-second script passes through the dashboard's test harness, but nobody has run it by hand, and there is no recording.

| Item | State |
| --- | --- |
| 90-second script (README) | Written |
| Scripted dry run through the dashboard (`make dryrun`) | All 8 steps pass; about 9.5 s of compute cold; dashboard start-up 6.6 to 9.8 s against a 10 s budget |
| Run by a person in a browser, timed | Not done |
| Backup video and slides | Not done |
| Real LLM front door in the demo | Not done; the demo uses the offline rules extractor |
| xnn or LAMMPS demo | Not built (see the proposal above) |

The shape-versus-position step must be presented as a workflow and a direction, not a prediction; the dashboard caption now says the rates are synthetic and tuned, and the benchmark result should be stated on screen.

## Open items and next steps (as of this snapshot)

| Item | Owner | Notes |
| --- | --- | --- |
| Tube CFD verification: mesh, regime agreement, surrogate | Agent (since finished) | Targets missed; see `problems_oct20.md` |
| Ampoule CFD verification: regime agreement, mesh, surrogate | Agent (since finished) | Targets missed; see `problems_oct20.md` |
| Wire the flask Tier 2 case into the case writer; final full test run; commit and push | Claude | Flask wiring still open |
| Open the dashboard and run the 90-second demo by hand, twice, timed | User | Nobody has done this |
| Provide an API key for the real extractor backend | User | Then score it on the 33 real procedures; local MLX is the planned alternative |
| Rotate the Edison key | User | It was pasted into the conversation |
| Open the 329-reaction supplement; confirm COMSOL is out of the plan docs | User, Claude | Publisher blocks bots; COMSOL references still to be removed |
| Emails to van Duin, the Chen/Momeni group and 2DCC; OSI submission requirements; name and licence | User | Plan blockers, still open |
| Eject the OpenFOAM volume when CFD is finished | User | Still mounted |
| Decide: xnn step 1, or spend the time on slides, video and polish | User | Recommendation: polish first |

Housekeeping to know about: the dashboard agent force-reinstalled pyarrow in the `research` environment, and a few shared files (props tables, preset formats) were edited by agents beyond their original scope; the test suite covers them.

Sources opened for this document: the [xnn project page](https://molssi-ai.github.io/xnn/) and the [Edison client documentation](https://docs.edisonscientific.com/edison-client/quickstart); other citations are linked where used.
