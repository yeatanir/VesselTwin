# VesselTwin: detailed project status (Oct 21, 2026, afternoon)

Branch `polish` (everything merged: tracks A, B, C, E, G, H, I, J, K, L on top of `main`). Last full test run: 298 passed, 6 skipped, 1 expected failure (about 4 min). Supersedes `status_oct20.md`, `problems_oct20.md` and the earlier part of `docs/status_oct21.md`. All numbers are copied from the track reports in `docs/progress/` and the results files in `docs/`; nothing here is a new claim. Every benchmark item for MoS2 is development data (we have seen all of it), so none of it is a held-out test.

## 1. Bottom line

VesselTwin works as a framework and a verification harness. It does not work as a predictor of MoS2 growth outcomes. Both statements are measured, not opinions.

- **Works:** the pipeline from procedure text to a vessel model, an uncertainty band, a ranked list of atomistic calculations, and a trust label on every number; five vessel models; three OpenFOAM cases; a visual dashboard; an LLM backend that works with any provider; a test suite that has caught real errors.
- **Does not work:** direction-of-change predictions for MoS2 CVD knobs (the model scored 1/9 to 3/9 against a blind no-tool agent's 6/9); MoS2 shape-class prediction (0.50, the same as always answering triangle); surrogate models at the 5 % target; Tier 0 regime calls at the 90 % target everywhere except the tube against an agent-chosen label.
- **What the failures mean:** most failures are of the model, and some are of the benchmark inputs (papers do not state everything the model needs). The verification process did what it was built to do: it told us, with numbers, which outputs not to trust.

## 2. What works, with evidence

| Area | Evidence | Caveat |
| --- | --- | --- |
| Contracts and editable parameters | SetupSpec, Passport, Closure; every parameter has unit, bounds, uncertainty, source; JSON schema, presets and CLI | Passports are flagged synthetic for most vessels |
| Registry | A new vessel file appears in the dashboard with no other change; the photoreactor was added this way | |
| Sorbent bed (CALF-20) | Breakthrough errors -3.3 %, +1.9 %, +9.8 % against published curves (n = 3); isothermal shock time within 3 %; generic reference column within 3 % (arXiv 1907.00195) | 13X is off by -38 %; CO2/H2O competition under-predicted |
| Ampoule, diffusion-limited cases | OpenFOAM and Tier 1 agree within 2 %; 4 coarse cases re-run bit-identically after solver changes | Over-predicts published WO2 + HgX2 rates by 1x to 38x |
| Photoreactor vs actinometry | Predicted/measured actinometer slope 0.879 (tolerance x1.25) and 0.688 (tolerance x1.5), both pass; inputs taken from the paper (Saenz 2024), not fitted; quantum yield from Hatchard & Parker 1956 Table 5 read from the page image | One paper, one lab, two geometries; lamp-to-irradiance not validated |
| Extractor (procedure text to values) | 33 real procedures, 113 gold fields: stand-in precision 0.969, recall 0.832, 0 fabricated values; offline rules backend precision 0.953, recall 0.726, 0 fabricated | Stand-in is a Claude subagent, not a deployed model; rules were tuned on this set |
| Ranking of atomistic calculations | Best of top 3 beats the median random parameter 0.96-1.00 over 50 seeds | Self-consistent (our own model), not experiment-checked |
| Tube Tier 0 regime call | 37/40 = 92.5 % against the CFD label (was 26/40 = 65 %); fitted half-split 97.9 +- 2.6 % | Rule designed after seeing the failure; the CFD label is an agent-chosen convention (63 % wall uptake) |
| Ampoule Tier 0 regime call | 81.7 % (f > 1.1) and 75.0 % (f > 1.2) on 60 cases; held-out half-splits 83.4 +- 2.6 % | A model with no stratification term does about as well |
| Grid convergence | GCI computed with Roache's method; ampoule diffusion 0.0 %, weak 0.5 %, tilted 2.1 % | Strong convection is unsteady (13 %, not meaningful); tube 0.8-13 %; flask 14 % at 400 rpm |
| Flask power number | CFD Np 0.956 (Re 4636) and 0.856 (Re 9271) with GCI bands; Tier 1 gives about 0.51, so CFD/Tier 1 = 1.86 and 1.69 | Two single points, frozen rotor, equal-volume cylinder |
| Excerpt verification | A literature excerpt counts only if it names the parameter and states a value within 2 %: 10 of 48 pass | Edison answers are prose summaries, 0 of 23 pass |
| LLM backends | Generic provider interface (OpenAI-compatible, Anthropic, MLX, offline rules); tested with a local fake server, no key stored; one live connection test through the real API succeeded | Docker image not built (no Docker here) |
| Recorded model runs | Two complete agent runs recorded with claude-sonnet-5-5 through the generic adapter (extract, solve, rank, with a final answer); shown in the dashboard as recorded runs | Two runs only; they replay without any API |
| Dashboard | New Home page (5-step story), Vessel view (schematics, Tier 1 profiles with bands, stored CFD fields, a centrepiece figure), Reasoning trace, Advanced tabs, sidebar LLM settings | Not seen in a real browser by any agent; the user must check |
| Tests | 298 pass, 6 skip (OpenFOAM-dependent), 1 expected failure (13X held-out check) | Many tests check bookkeeping and analytic limits |

## 3. What failed, and why

### 3.1 MoS2 direction-of-change (sensitivity) benchmark

| Table | Model | Blind no-tool agent | Always-increase | Notes |
| --- | --- | --- | --- | --- |
| Original 8 items, as first published | 5/8 | 6/8 | 4/8 | Proxy choices and a clipped range made this look better than it was |
| Original 8, pre-registered rebuild (Track A) | 2/8 | 6/8 | 4/8 | Uncertain counted wrong; confident calls 2/5 |
| Development set, 9 primary items (Track A) | 3/9 | 6/9 | 4/9 | |
| Jian 2019 items j1-j3 | 0/3 | 3/3 | 2/3 | One paper; vapour-pressure law stops at the 1068 K melting point |
| Paper-stated geometry, 9 primary items (Track L) | 1/9 | 6/9 | 4/9 | No item improved |
| Paper-stated geometry, dev + j (n = 12) | 1/12 | 9/12 | 6/12 | |

Causes found, in order of discovery:

1. **Proxies were assumptions** (nucleation density from MoO3 supersaturation, and so on). Replaced by Venables nucleation theory in Track A; the model then abstains when the sign depends on unsourced energies.
2. **Vapour-pressure clamp.** The MoO3 law stopped at 1068 K. A liquid branch was added as an option (Track I). It did not fix the sensitivity, because the clamp was not what blocked the response.
3. **Intended transport physics** (Track K). With the substrate more than about 4 cm from the boat, the wall removes about 98 % of the boat's MoO3 before the substrate (wall-uptake number about 11). The substrate flux equals the furnace and flow state, not the boat. The stored CFD saturates the same way. This is not a bug.
4. **Input gap** (Track L). With each paper's own geometry, tying boat temperature to furnace temperature puts the substrate at the boat's temperature, so the flux is exactly zero. Real substrates are cooler than the source, and no paper states the offset the model needs.
5. **Six of 14 items are not modellable** (layer number, film thickness, lateral substrate position, and similar).

### 3.2 MoS2 shape class

- Accuracy 0.50, equal to the always-triangle baseline, in every configuration tried: synthetic rates, MACE kink energies, DFT Mo edge (Rosen 2018). n = 14 cases, 8 in scope.
- The map is decided by synthetic S-edge and attachment constants. With the DFT Mo edge and the synthetic S edge, the old default map comes back; with the MACE S edge it collapses to all Mo-edge triangles.
- Sourced equilibrium edge model (Track I, Momeni SI equations S14-S17 and Cao et al. 2015, VASP PBE): the registered version scored 0.25; after a disclosed orientation correction it reproduces Cao's printed sequence (hexagon at -0.95 eV, triangle at -0.04 eV) but abstains on the benchmark. The authors' own supersaturation bridge gives always-triangle by construction.
- Neither model family reproduces Momeni's hexagon-to-triangle trend along the substrate, because the shape depends only on S2 pressure and temperature, which barely change over 1 cm.

### 3.3 Verification targets set in the plan

| Target | Tube | Ampoule | Flask |
| --- | --- | --- | --- |
| Mesh change under 2 % | missed (GCI 0.8-13 %, mostly oscillatory) | met at 2 of 4 points | missed (14 % at 400 rpm) |
| Tier 0 regime agreement at least 90 % | met against an agent-chosen label (92.5 %, rule not blind) | missed (81.7 % / 75.0 %) | not tested |
| Surrogate error within 5 % | missed (24-36 % LOO median; two outputs not learnable from 40 cases) | missed (27-31 % LOO median) | not built |

### 3.4 Other failures and abandoned items

- 13X breakthrough is off by -38 % to -39 %. The two heat-transfer fits tried: no solution in range, then a fit that missed its held-out threshold by 0.6 points; neither adopted.
- IAST for CO2/H2O competition was worse than the current model (CO2 about -100 %); not adopted.
- A threshold fallback for shape (Track A step A5) was not run: Wang 2014 is closed access (the PDF has since been supplied but A5 was not re-run).
- Flask closure is not wired into Tier 1; the GCI-widened uncertainty band is not applied; the new surrogate is not shown on the dashboard.
- The stlite (static GitHub Pages) deployment was judged not feasible. Docker and Codespaces files are written but untested.

## 4. Per-vessel scorecard

| Vessel | Tier 1 | Verified against | Status |
| --- | --- | --- | --- |
| MoS2 CVD tube (flagship) | Hertz-Knudsen boats, plug flow, wall and substrate condensation, S speciation, Wulff shape map, MC uncertainty | CFD (substrate pressure, Mo:S), 14 shape cases, 15 sensitivity items | Transport structure is checkable and the CFD saturates the same way; morphology and sensitivity predictions are not validated; Tier 1 plateau 2.5-3x above CFD |
| Sealed ampoule | Diffusion flux, equilibrium, Stefan flow, calibrated convection enhancement | 60-case CFD sweep, published WO2 + HgX2 rates | Diffusion limit within 2 % of CFD; absolute rates off 1x-38x |
| Stirred flask | Power number, mixing time, Villermaux-Dushman | CFD at two Re | Tier 1 power number about half the CFD value; no published stir-bar Np found |
| Sorbent bed | LDF/Langmuir column, competitive isotherms, dispersion, heat | CALF-20 (3 points), 13X (2 flows) | CALF-20 good; 13X too hot |
| Photoreactor | Beer-Lambert, lamp geometry, wall Fresnel and absorption, inner filter | Ferrioxalate actinometry, 2 geometries | Passes pre-registered tolerances; mixing cap and heating are unsourced |

## 5. What the process found (these are real results)

- **A 30-60x constant error** in the MoO3 vapour pressure, caught by a literature check (Edison found Smolik et al.) after an OCR'd source was used. All tube results before Oct 20 were invalid.
- **Stale claims** (5/8, shape 1/8) were still in the dashboard and traces after the benchmark was rebuilt; replaced.
- **A wrong sign hypothesis** for the ampoule was disproved; the real bug (a stratification scale off by the length-to-height ratio) was found and fixed, then reported as not held out.
- **Edge orientation error** in a first sourced edge model, found by reading the DFT paper, disclosed and corrected with both runs reported.
- **A quoted-number error** in a literature answer (Edison's scale numbers were off by about 1000x) caught by recomputing from its own equations.
- **A cache bug** in the sorbent solver that shifts CALF-20 results by up to 2 points; noted, not fixed.
- **A process mistake** (100 MB of pip wheels committed to a track branch) and a blanket `pkill` by an agent; both recorded.

## 6. Literature tools and sources used

- **Edison Scientific Literature agent:** 9 plain Literature jobs, one credit each (MoO3 vapour pressure, sulfur vapour pressure, MoS2 edge energies, stir-bar power number, 329-reaction study, flow rate, substrate position, sulfur supply, liquid MoO3). Gives cited numbers and honest "not found", but some quoted numbers were wrong. Credit use is unconfirmed (the cost field came back empty).
- **Valency:** free semantic search over preprint servers; returns papers, not numbers; corpus lacks most chemistry journals.
- **Sources opened and used for constants:** Smolik et al. 2000 (MoO3 solid pressure), Rau et al. 1973 (sulfur), Rosen et al. 2018 with its SI workbook (DFT Mo-edge S binding), Hatchard & Parker 1956 (ferrioxalate quantum yield), Saenz et al. 2024 (actinometer setup and slopes), Momeni et al. 2018 with SI (closest precedent; edge-energy fits), Cao et al. 2015 (DFT level: VASP, PAW, GGA-PBE, 400 eV cutoff), Samant et al. 1992 (solid MoO3 only), Pimpinelli, Tumbek and Winkler 2014 (nucleation exponents), NASA Glenn tutorial for Roache's GCI.
- **Not opened or unverified:** Fieser 1931 and Blackburn 1954 liquid MoO3 relations (via Edison only); the MoO3 boiling point 1428 K (secondary page quoting CRC, cross-checked with a NIST Antoine fit); Wang 2016 geometry.
- **Foam-Agent 2.0** (Yue et al., arXiv 2509.18178, MIT licence): related work for LLM-driven OpenFOAM; only the abstract, architecture figure and repository layout were read. Targets OpenFOAM Foundation v10, not our ESI v2512; not integrated.

## 7. Repository and process state

- **Branches on origin:** `main` (docs updates only since the first push), `polish` (everything merged, latest `dc94852` at the time of writing), `integration` (tracks A, B, C, E merged), and `track-a`, `track-b`, `track-c`, `track-e`, `track-g`, `track-h`, `track-i`, `track-j`, `track-k`, `track-l`. Merging `polish` into `main` is the user's step.
- **History:** `track-e` carries about 100 MB of pip wheels in its history; the merged branches do not (squash merge). The first commit that pushed a 2 MB compiled OpenFOAM object is still in `main` history.
- **Secrets:** each merge was scanned; no keys in tracked files. The Edison and Anthropic keys were passed inline only and are visible in the session transcript; rotate both.
- **Environment:** the OpenFOAM v2512 volume is mounted for Tier 2; Docker is not installed; no browser rendering was possible for the agents.

## 8. Not verified by anyone yet

- The dashboard in a real browser: Home, Vessel view and Reasoning trace, in light and dark, at 1440 px and 390 px wide (checklists: `docs/screens/CHECKLIST_home.md`, `CHECKLIST_vessel_view.md`, `CHECKLIST.md`).
- The "See the reasoning" button (needs Streamlit 1.66 tab state; `requirements.txt` still says streamlit>=1.40).
- The Dockerfile and the Codespaces config.
- A timed manual run of the demo; the video; the one-page write-up.

## 9. Positioning for the submission

- **Do not claim:** that VesselTwin predicts MoS2 shape or the direction of parameter effects; that reactor-to-atomistic coupling is new (Momeni et al. 2018 did it and validated it on MoS2 islands).
- **Can claim, and show:** procedure text in, a vessel model out, with uncertainty; a ranked list of atomistic calculations; every number labelled as benchmarked, uncertain or hypothesis; a verification harness that finds and reports errors, including its own (the 30-60x constant, the sensitivity benchmark at 1/9 to 3/9 against a blind 6/9); pre-registered benchmarks; a provider-agnostic LLM layer; a visual interface.
- **Concrete explainable finding for the demo:** with the substrate far from the boat, boat temperature does not matter and the furnace ramp and flow do; the stored CFD agrees (Track K).

## 10. Remaining actions

| Action | Owner |
| --- | --- |
| Look at the dashboard in Safari using the checklists; report what looks wrong | User |
| Merge `polish` into `main` | User |
| Run the demo by hand twice with a stopwatch; record the video | User |
| Confirm the submission rules (deadline, video length, write-up length) in the event Slack | User |
| Rotate the Edison and Anthropic keys | User |
| Draft the one-page write-up and the four-minute script | Claude, on request |
| Decide on public hosting (Streamlit Community Cloud) when the repo is made public | User |
| Optional: add a separate substrate-temperature input from papers, wire the flask closure, show the surrogate on the dashboard, raise the Streamlit minimum version | Claude, if time |

## 11. Update (Oct 22, early): Tracks M, N, O

- **Track M** (pre-registered, scored once): a reactive substrate sink (synthetic constants) removes the exact-zero flux for a hot substrate but does not rescue the benchmark (structural ensemble 1/9 strict; blind 6/9). The boat-temperature response at 12 cm returns only with a reflecting wall, so the wall-uptake assumption controls the tube response, and the stored CFD (similar wall law) cannot test it independently. This corrects the earlier statement that the wall takes 98 % of the vapour: it is a model-dependent result.
- **Track N** (pre-registered, scored once, n = 52 stored CFD cases): optional furnace and flow model (editable 1-3 zone or measured profile, quartz radial network, 2D gas energy equation, computed boat and substrate temperatures). Agrees with the stored CFD on the gas side in 45 of 52 cases (legacy 35); did not reproduce the simulated gas peak of Momeni 2018 (+143 K); no measured temperature validates it.
- **Track O:** Furnace and flow dashboard tab on top of Track N.
- **State:** polish holds Tracks A-O; 343 passed, 6 skipped, 1 expected failure.
