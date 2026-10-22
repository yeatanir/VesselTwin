# VesselTwin implementation plan

Source: `../VesselTwin — OSI Hackathon plan.pdf`. Submission Oct 22, 2026. Owners: **A** CVD tube + ampoule OpenFOAM, integration lead · **B** OpenFOAM flask, Tier 0–1 engine · **C** LLM, benchmark, surrogates, sorbent · **D** atomistic, brief, Wulff/phase field, dashboard.

## Rules
1. Vertical slice first: MoS2 end to end. Other vessels are Tier 0–1 until Gate 3.
2. Contracts in `schemas/` are frozen after Oct 11. Change them only with everyone's agreement.
3. Nothing in the demo without a passing test (`make test`, results in `cache/harness.json`).
4. Anything illustrative carries `synthetic=True` and a visible tag. Stubs are synthetic.
5. The LLM never produces a physical number. Values come from the text (span-checked), `llm/defaults.yaml`, a property DB, or a solver.
6. Demo runs offline from `cache/`, keyed by spec hash.

## Setup
- Run: `make test`, `make demo`. Python: conda env `research` (pydantic, pint, pytest, scipy, sklearn, fastapi, ase present).
- Missing, install when needed: `streamlit CoolProp thermo cantera mlx-lm` (see `environment.yml`).
- OpenFOAM: openfoam.com **v2512** via `/Applications/OpenFOAM-v2512.app`. It is not on PATH; the app mounts a case-sensitive volume, so launch the app first and run solvers from its shell. Check that the PG solver builds against v2512.
- Tier 2 is OpenFOAM-only (COMSOL dropped).

## Status of scaffold (done Oct 10)
- [x] `schemas/` SetupSpec (stated/default/missing invariants), Passport, Closure
- [x] `core/dimensionless.py` Tier 0 numbers + regime classifier; `core/registry.py` vessel template; `core/pipeline.py`
- [x] `llm/span_check.py` (fabricated-value metric), `llm/units.py` (pint)
- [x] Four vessel stubs (tier0/tier1 placeholders, tagged synthetic)
- [x] Test harness (pytest marks `vessel` / `check` → `cache/harness.json`), `make demo` passes the empty case
- [ ] CI on a remote (no remote yet; `make test` is the gate meanwhile)

## Status of Tier 1 solvers (done Oct 10, all four vessels)
Prior art searched first: no released CVD-tube, Schafer-flux or Villermaux-Dushman code found; laminarSMOKE (flames) and RUPTURA (C++ breakthrough, MIT) noted as cross-checks. All four are fresh Python (numpy/scipy), 4 ms to 0.3 s per solve.
- [x] `vessels/cvd_tube`: Hertz-Knudsen boats + laminar plug flow + wall/substrate condensation -> Mo:S ratio, supersaturation, flux at substrate
- [x] `vessels/ampoule`: Schafer diffusion flux from equilibrium p(T), Rayleigh number and convection enhancement
- [x] `vessels/flask`: Np(Re), Grenville theta95, engulfment micromixing time, Villermaux-Dushman incorporation model
- [x] `vessels/sorbent` (rebuilt Oct 18, see "Sorbent status" below): was LDF-Langmuir column, optional energy balance, Ergun dP, isotherm closures in
- [x] Editable params: `core/params.py` ParamDef (unit, bounds, sigma, group, source) -> `core/api.py` `schema/defaults/presets/solve`, CLI `python -m core.solve`
- [x] `vessels/cvd_tube/wulff.py` kinetic Wulff + shape_map + knob_sensitivity (all rates synthetic; Wang trend direction only, Gate 2 NOT claimed); tests/test_wulff.py
- [ ] Known limits: Tier 1 convection enhancement, flask power number, flask laminar blend and all thermo constants are synthetic placeholders; anchor them in Gate 1.
- [x] Tier 2 case writer+parser `tier2/openfoam.py` (buoyantFoam + passive scalars, tube wedge / ampoule 2D slab); parser tested on a FAKE fixture, **solver run untested** (OpenFOAM volume not mounted; `tier2/run.sh`)
- [x] LLM extractor v0 (Oct 18): `llm/extract.py` rules (offline default) + anthropic + mlx (mlx UNTESTED); `bench/score.py`; 12 synthetic procedures in `bench/procedures/`; real 100 annotated procedures still a human task.
- [x] Ampoule Tier 2 RUNS on v2512 (custom tier2/foam/ampouleBoussinesqFoam = Boussinesq + composition buoyancy; wedge at |tilt|=90 else equal-area half-duct; HK end-face BCs). Diffusion-limited cases match Tier 1 within ~5%; Tier 1 convection enhancement is far too high at large Ra (scan: docs/ampoule_convection_scan.json).
- [x] Ampoule physics upgrade (Oct 18, `vessels/ampoule`, `tests/test_ampoule_physics.py`): multi-species speciation (carrier, co-product, 2nd carrier, I2<->2I from NIST-JANAF 1000 K), Stefan film flux with inert-Ar backfill, convection `conv_model=calibrated` (default): saturating Taylor-dispersion horizontal term (362880 derived) + capped Globe-Dropkin vertical term, 3 params fitted ONLY on the OpenFOAM tilt-0 D 10-60 mm scan (train err <=3%; 5 pts/3 params). CFD-calibrated, laminar, L=15 cm, A=0.067-0.4, Ra_s<=1.64e6; `convection_in_range` = inside that scan. Held-out vs CFD (fine mesh): tilt 30 -11%, 60 -41% (unsteady), 90 +46% (unsteady, mesh 16%), -60 -18%, presets -13/+21/-5% (CFD mesh 4-16%). Uncalibrated `buoyancy` (overshoots 20-4000x) and `placeholder` remain selectable, two-zone wall profile, growth mm/day. Old model reachable with `dissociation=off, stefan=dilute, conv_model=placeholder` (tested equal to 1e-9).
  - SOURCED: WO2 + HgX2 (X=Br,I,Cl) dH/dS at 1000 K and experimental rates (graph-read, +-10%) from Schmidt, Binnewies, Glaum, Schmidt, InTech 2013, DOI 10.5772/55547 (eqs 33-35, Fig. 13); presets `ampoule__WO2_*`. I2 dissociation: NIST-JANAF.
  - ANCHOR ERROR (not tuned; ampoule size/loading of those runs unpublished, chapter-typical 15 cm x 15 mm, 1 bar agent assumed): model/published = 7.4, 9.6, 18.8, 2.1, 38.9 for five T-pairs (over-prediction, T-dependence too weak; unchanged by calibrated convection, f<=1.65 for these presets). Cause is not convection: D0=0.1 cm2/s Schafer convention too large for heavy halides (0.6e-4 prefactor, D0~0.025: 2.4-12x; binary Fuller: 1.9-10x), unknown loading (x0.1 changes ratios 0.1-96x), and a T-dependence the equilibrium+diffusion model lacks (HgI2 840>760 still 10-12x; candidate: side equilibria/kinetics, not tested). Gate 1 for the ampoule is NOT met quantitatively; only direction/ordering is.
  - NOT FOUND: GeSe/GeI4 Ge-I gas thermochemistry (paywalled), so Skylab fluxes (Wiedemeier et al., NASA NTRS 19740021782) are unused; only the qualitative tilt trend is tested. Everything marked `synthetic` in ParamDefs (default dH/dS, Fuller volumes of C/E, crystal density) is still illustrative.
- [x] Flask physics pass (Oct 18, `vessels/flask/{__init__,vd,solvents}.py`, `tests/test_flask_physics.py`): Villermaux-Dushman rate law, k2(I) two-branch (Guichardon 2000 as quoted by jchpe.ut.ac.ir/article_89303), K(T) (Palmer 1984), Y_ST/Xs checked against PMC9866573 and arXiv:1909.11868 SI; Xs -> 1 as t_m -> inf (slow, so 0.7 at finite t_m is chemistry, not a bug); presets `flask__vd_*`. rho/mu/cp(T) from refitted published tables (ThermoML, CRC, CHERIC), CoolProp not needed. Added: micro/meso/macro time scales and critical addition rate, Bourne consecutive/parallel selectivity (incorporation model), wall-cooling and plume hotspot flag, vortex/torque/bar-fit flags, volume scaling (`scale_up`), `mixing_sensitive` verdict + knob code. Anchor: model Xs 0.31-0.37 vs ~0.26-0.34 read off Yang 2012 figure axes (low confidence, buffer set unknown), not tuned. Still synthetic: stir-bar Np(Re), Grenville constant (baffled tanks), feed-point eps ratio, slip/torque, U films, thresholds. No published stir-bar power number found. The 329-reaction study (Synlett 2024, doi 10.1055/a-2384-7220) SI could not be opened (publisher blocks bots): per-reaction data unverified, reanalyses by third parties suggest paired yields are published but scale/stir rate per reaction unknown.
- [x] Ampoule CFD verification (Oct 20, `docs/ampoule_cfd_verification.json`, `surrogate/ampoule.py`): 60-case OpenFOAM sweep; Tier 0 vs CFD regime agreement 72% (f_CFD>1.2) / 65% (>1.1), target 90% NOT met (all misses are tilt-sign/narrow-tube cases); mesh convergence INCOMPLETE (fine level unfinished; tilted 4.51->4.10 coarse->medium); GP surrogate held-out mean error 56% on f vs 5% target NOT met.
- [x] Tube Tier 2 credibility (Oct 20, Smolik MoO3 basis; `docs/tube_cfd_verification.json`, `scripts/tube_cfd_verification.py`): mesh M2->M3 changes 1-8 % (target 2 %: MISSED, boat release +2-5 %/level); CFD/Tier 1 median p(MoO3) 0.92 (0.01-3.2), p(S2) 6.5x, supply 2.9x (ring vs disk boat); Tier 0 vs CFD regime 65 % of 40 (target 90 %: MISSED); GP surrogate held-out mean error >> 5 % (MISSED).
- [ ] Not built: Tier 2 (OpenFOAM tube/ampoule/flask case writer), kinetic Wulff / shape map, extractor, surrogates, dashboard.
- [x] `app/dashboard.py` (Streamlit, `make dashboard`): core.api only, disk cache `cache/dashboard/`, Credibility tab from harness.json; `tests/test_dashboard.py` (AppTest). Extractor hook guarded (disabled until `llm/extract.py` exists).
- [x] `atomistic/brief.py` + `ranking.py` + `app/brief_tab.py` (Oct 18): passport -> brief (p05/p50/p95 + re-solved 95% tails) and finite-difference ranking of atomistic calcs through `core.api.solve`; `tests/test_ranking.py` (check `ranking_benefit`, 50 draws/vessel), `tests/test_brief_tab.py`. Inherits Tier 1 placeholders (synthetic); dashboard hook not yet wired.

## Sorbent status (Oct 18)
- Sourced, not illustrative: 13X (Zeochem Z10-02ND premium and Z10-02 standard) CO2, N2, H2O dual-site Langmuir, Wilkins MSc thesis 2017 Tab 4.1; CALF-20 CO2 DSL, N2 equal-energy-site, H2O cubic-Langmuir and CO2 water factors, Nguyen PhD thesis 2021 Tab 2.1/2.3/3.1/4.3. Every number and its table is in `vessels/sorbent/sorbent_data.json`; presets are generated from it (`python -m vessels.sorbent.build_presets`). Papers behind the theses (Wilkins & Rajendran 2019, Nguyen 2024) were paywalled and not cross-read.
- Still `synthetic`: h_wall, h_in (column specific), micropore D_c/r_c^2 and macropore radius (off), regeneration operating values, 13X particle size (not published). No sourced CO2/H2O competition at flue-gas CO2 fractions exists (data are ~1 bar CO2): runs with RH>0 set `outside_fit_range`.
- Physics added (all ParamDef-switchable): EDSL competition CO2/N2/H2O + CALF-20 'modified' water scheme, total molar balance with compressible flow, Ergun feedback (cell pressure as a state), axial dispersion (Ruthven) + TVD, LDF from film + macropore (+ micropore) resistances (k_ldf overrides), energy balance with per-component isosteric heat, adsorbed-phase and wall heat capacity, optional purge/regeneration stage with cycle capacity. Not done: pressure-swing blowdown transient, axial wall conduction, radial gradients, real-adsorbed-solution theory for CO2/H2O, temperature-dependent gas properties.
- Credibility (tests/test_sorbent_physics.py, results in cache/sorbent_benchmark.json): isotherm fits reproduce the tabulated measured loadings within 1-8 %; CALF-20 CO2/He breakthrough t_bar(50 %) within -3/+2/+10 %, bed temperature peak +7..9 K high; 13X CO2/He breakthrough -38/-39 % early and +27..33 K too hot (source h_in = 4 W/m2/K and heat capacities are ambiguous in the thesis; isothermal bound is +17 %). Not tuned. 13X CO2/H2O extended DSL vs measured CO2 loading -17 / -41 %.
- Speed: nominal solve ~0.25 s (30 cells); thermal peak converges only at >= 100 cells (~1 s). Humid CALF-20 ~1-5 s.

## Schedule
| Dates | Owner | Deliverable | Done when |
|---|---|---|---|
| Oct 10–11 | All | Contracts, harness, **resolve blockers (below)**, send emails early | empty case runs (done) |
| Oct 10–12 | C | LLM extractor v0 (MLX, constrained JSON on `Vessel.params`), `defaults.yaml`, first 40 procedures in `bench/procedures/` | field P/R logged |
| Oct 10–12 | A | Run existing PG solver unchanged on a hard-coded tube case, then parameterize from SetupSpec (`vessels/cvd_tube/openfoam/`) | mass balance < 0.5% |
| Oct 10–12 | B | Real Tier 0–1 for all four vessels; OpenFOAM flask frozen rotor | regime calls on test specs |
| Oct 10–12 | D | Edge-energy table, kinetic Wulff (`vessels/cvd_tube/wulff.py`), MLIP/ReaxFF setup | Wulff shape moves with μ_S as published |
| Oct 12 | A | Email van Duin, Chen/Momeni, 2DCC | sent |
| **Oct 13** | All | **Gate 1**: Tier 1 known-answer per vessel | failing vessel is cut |
| Oct 13–14 | A | Ampoule buoyant template | matches Schäfer limit with convection off |
| Oct 13–15 | B | Villermaux–Dushman in OpenFOAM; 329-reaction regime check if data exists | trend matches literature |
| Oct 13–15 | C | Sorbent bed (forward only); 100 procedures; benchmark final; surrogate pipeline | numbers final |
| Oct 13–15 | D | Passport→brief; decision ranking; MLIP edge recomputes; cached ReaxFF sulfidation | brief for a real MoS2 spec |
| **Oct 15** | A+D | **Gate 2**: shape vs position reproduces Wang trend | else MoS2 ships at Tier 1 |
| Oct 16 | A+D | MoS2 shape benchmark, 10–20 papers vs majority baseline (hand-label first) | scored |
| Oct 16 | C | Surrogates for every Tier 2 case | within 5% held out |
| **Oct 17** | All | **Gate 3 + feature freeze**: record tier per vessel in `tiers.json` | recorded |
| Oct 18 | D | Stretch: phase field. Hard stop end of day | runs or dropped |
| Oct 18–19 | C+D | Dashboard (Streamlit): procedure → spec (amber defaults) → regime → shape map slider → brief | works offline |
| Oct 19 | All | 90 s demo dry run ×2 | < 90 s, no failures |
| Oct 20 | All | README, `make demo` on a fresh clone < 10 min, slides, video draft | verified |
| Oct 21–22 | All | Record, fix only demo-breakers, submit | submitted |

## Credibility tests (harness)
Mass/energy balance < 0.5% · mesh convergence < 2% · analytic limit per template · known-answer per vessel · MoS2 shape benchmark vs majority baseline · extraction P/R with **zero fabricated values** · Tier 0 agrees with Tier 2 on ≥ 90% of sweep · surrogate within 5% · top-ranked calc beats random.

## Blockers to resolve Oct 10–11
- [ ] PG solver on v2512 vs openfoam.org build?
- [ ] Does the 329-reaction study supplement list per-reaction conditions?
- [ ] OSI submission requirements (repo, video, write-up, licence)
- [ ] Talk to van Duin: authorship, thesis link
- [ ] Final name

## Cuts (restore only if ahead)
Sorbent reverse loop · photo/micrograph input · neural-operator surrogate (start GP / gradient boosting) · MOCVD.

## Risks
CFD fails to converge → ship Tier 0–1 and say so · shape trend fails → kinetic Wulff vs published edge energies, report the gap · phase field slips (likely) → stretch only · judges see "LLM sets up CFD" → lead with outcome link and known-answer checks · figures → classify for scoring only, never redistribute.

## cvd_tube physics + sourced constants (Oct 18, `vessels/cvd_tube/`, tests in `tests/test_tube_physics.py`)
**Sourced** (see `thermo.py`, `edge_data.json`): MoO3 total vapour pressure Simnad & Spilners, Trans. AIME 1956 (~1.2 Pa at 1000 K, 30x below the old placeholder; read from an OCR'd page, origin unverified, so level kept as `MoO3.P_ref_Pa`, sigma 50%); (MoO3)3 dominant vapour species, Berkowitz/Inghram/Chupka JCP 26, 842 (1957) (abstract level); S8 = 4 S2 equilibrium from NIST-JANAF Shomate fits (Chase 1998 via WebBook) with dfH(S8,g) = 100.416 kJ/mol (Jackson, Tiana, Walsh, Chem. Sci. 7, 1082 (2016)); Fuller diffusivities; Sh/Nu 3.66 (Incropera). Sulfur total vapour pressure is an Antoine fit from a forum page (reproduces the normal boiling point, NOT traced to a primary source). Edge energy: one number only (zigzag 0.77 eV/A, Levita et al., Carbon 107, 878 (2016)), not split by edge or mu_S, not used in the rates.
**Still synthetic**: all k_attach/gamma_edge/P_eq_ref (Wulff rates, retuned only so the default spans all shapes after the MoO3 pressure dropped), alpha_MoO3 (no published value found), nucleation density, buoyancy exponent, P_scale/D_scale uncertainty widths. No Mo-zz vs S-zz edge energy vs mu_S number and no attachment barrier could be retrieved (Cao 2015, Govind Rajan 2016, Momeni 2018 full texts/SI unreachable).
**Physics added (each a ParamDef switch)**: gas-temperature lag (Graetz, Nu), Stefan flow at boats/walls, boat as finite disk (4D/pi a), Gr/Re^2 + Ra buoyancy criterion (+ optional Sherwood enhancement, synthetic exponent), S speciation, MoO3 oligomer transport, substrate length/offset/centre reporting, H2 carrier, growth size = integral of edge velocity over `duration_min`. Mo3O9 + S2 -> MoOxSy intermediates (Lei, Xie, Yakobson ACS Nano 15, 10525 (2021)) is a flagged simplification (instantaneous). Grid is now 2nd order (cell-midpoint wall T, boat on a node): MoO3 p changes <1% 400->1600 cells. Solve ~2 ms.
**Closure vs OpenFOAM v2512 default case** (same constants as the CFD run, `thermo_basis=legacy_synthetic`, n_oligomer=1; CFD at the substrate centre x=0.625 m: axis 2.7 Pa / bulk 1.7 Pa, probe 3.5 Pa, S2 73 Pa, Mo:S 0.048, ss 1.00 vs gas T): Tier 1 before (leading edge of a fixed 3 cm strip, gas at wall T) 4.4 Pa, 103 Pa, 0.043, ss 1.54. After: 3.6 Pa, 113 Pa, 0.032, ss(gas T) 1.35, ss(wall T) 2.2. Causes found: (1) the old number was read at the strip's leading edge, not the substrate; (2) supersaturation was against wall T while the CFD uses the (hotter, 20 K lag) gas T; (3) the CFD boat supplies 14 Pa vs Tier 1 6.7 Pa because its mixed BC uses half-cell distance D/dn (mesh dependent) on a full wall ring, so the CFD source is not mesh-converged; (4) the CFD substrate is a perfect sink and radial profile gives axis > bulk, which a 1D bulk model cannot show. Not tuned. With the literature constants: p_MoO3 0.06 Pa, S2 49 Pa, Mo:S 1.2e-3, ss 8 (wall) / 3.4 (gas): MoO3 supply is ~50x lower than the placeholder implied.

**Atomistic edges (Oct 19-20, `atomistic/edges.py`, `docs/edge_energies.md`):** MACE-MP-0 (medium) MoS2 zigzag edge energies vs Dmu_S (S8 ref) and MoS2-unit attachment energies on the S edge, done; closures gamma_edge_Mo/S = 1.63/1.21 +-0.53 eV/site at 1073 K, 50 Pa S2; applying them collapses the default shape map to hexagons (synthetic P_eq_ref inconsistent, needs re-anchoring); no barriers, no DFT.

**Wulff re-anchoring (Oct 20, `docs/wulff_reanchor.md`):** equilibrium term now from kink energies (S2/S8-ref for Mo edge, MLIP E_kink_Mo 0.52, E_kink_S 0.01 eV; Mo-vapour reference still synthetic); hexagon collapse gone but MLIP map is all triangle_Mo; shape benchmark unchanged at majority baseline (0.50); `eq_model="legacy_gamma"` keeps the old term.
