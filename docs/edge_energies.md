# MoS2 zigzag edge energies and attachment energies from MACE-MP-0

Code: `atomistic/edges.py` (`python -m atomistic.edges refs|run|analyze|finalize`). Data: `atomistic/data/{refs,raw_results,mos2_edges}.json`. Tests: `tests/test_edges.py`.
Status: **machine-learned-potential numbers, not DFT.** No barriers. Nothing here was tuned to any literature value.

## What was computed
- Model: MACE-MP-0 medium (`20231203mace128L1_epoch199`), float64, no D3; MACE-MP-0 small (`20231210mace128L0_energy_epoch249`) for model spread. mace-torch 0.3.15, ASE 3.27. The cached model files do not unpickle with the installed e3nn 0.6 as shipped; `calc()` wraps the e3nn loader at runtime (no site-packages edit).
- Monolayer: a = 3.183 A (medium; 3.179 small), S-Mo plane offset 1.572 A, inside the 3.16-3.19 A reference range. MLIP formation energy MoS2 from bcc Mo + S8: -2.86 eV/f.u. (experiment about -2.4 eV vs rhombic S, so the MLIP over-binds; the Dmu_S window below is MLIP-internal). Mo bcc a = 3.17 A.
- Edges: periodic zigzag ribbons (Mo rows 0..J, one Mo edge and one S edge each, 2H pairing forces this), relaxed BFGS/FIRE to fmax <= 0.02 eV/A (all runs 0.012-0.020). Triangular flakes with three identical edges (n = 4-8 Mo per side, up to ~140 atoms) separate the two edges.
- Edge S coverage = fraction of the two S atoms per outer lattice site present: Mo edge 100/50/0 %, S edge 100/50 % (50 % = alternating top/bottom). S-edge 0 % was not run.
- Reference: Dmu_S = mu_S - E(S8 crown ring)/8 (MLIP; the ring is re-minimised after a rattle because the symmetric crown is a saddle in MACE, 4 meV/atom). Window: -1.43 < Dmu_S < 0 eV (lower bound = MLIP dHf/2, Mo-bulk coexistence).
- gamma per length = [E - N_Mo e(MoS2) - (N_S - 2 N_Mo)(mu_ref + Dmu)] / L (ribbons carry two different edges, so sums gamma_Mo + gamma_S per L; the "/2L" of a symmetric ribbon does not exist for 2H). Separation: S_100 from triangle fits (energy linear in n to < 0.01 eV), all other edges from ribbon differences at J = 8. Per site: gamma_site = gamma x a_site, a_site = 3.183 A (one Mo per a along the edge).

## Results (medium model, eV/A; per site = x 3.183)
Convergence: ribbon sum gamma_Mo0 + gamma_S100 at Dmu = 0 is 1.02979 / 1.02987 / 1.02986 / 1.02984 eV/A for J = 4/6/8/10 (width 11-30 A): converged to 1e-4. Length 2 vs 4 cells: identical (1e-15). Vacuum 6-20 A with a fully periodic box: identical to 1e-15, because the MLIP has a finite 6 A cutoff (this test is therefore weak; it only shows no spurious image coupling). Additivity: gamma_S50 - gamma_S100 = 0.3378, 0.3376, 0.3378 eV/A on three different Mo edges. Ribbon sum vs triangle sum differ by 0.01-0.06 eV/A (we take 0.03 eV/A as separation error).

| edge phase | gamma(Dmu=0) eV/A | slope eV/A/eV | gamma(Dmu=0) eV/site |
|---|---|---|---|
| Mo 100 % S | 0.242 | -0.419 | 0.77 |
| Mo 50 % S | 0.392 | -0.105 | 1.25 |
| Mo 0 % S | 0.866 | +0.209 | 2.76 |
| S 100 % S | 0.164 | -0.209 | 0.52 |
| S 50 % S | 0.500 | +0.105 | 1.59 |

Stable phases: Mo edge 100 % S for Dmu > -0.5 eV, 50 % S below; S edge 100 % S for Dmu > -1.1 eV, 50 % below. Over the whole window gamma_S < gamma_Mo (0.35-0.16 vs 0.54-0.24 eV/A). The 0 % Mo edge is never stable in the window (crossing near -1.5 eV).

Conversion to the vessel: Dmu_S(T,p) = [G_S8(T) - E_el(S8) + DG_rxn(S8 = 4 S2, JANAF via `vessels/cvd_tube/thermo.py`) + 4 kT ln(pS2/1 bar)]/8, with G_S8 from the MLIP harmonic frequencies (rigid rotor, sigma = 8; 7 soft modes dropped). T = 1073 K: pS2 = 50 Pa gives -1.15 eV, 1 Pa -1.33, 1000 Pa -1.01; 973 K/50 Pa -0.97. The vessel's `mu_S_eV` is an offset on ln pS, so mu_S_eV = 0 corresponds to the Dmu of the actual gas; the closure below is evaluated at 1073 K, 50 Pa. Treat this conversion as +-0.3 eV (S8 gas vs solid reference, anharmonic ring modes, MLIP).

## Closures (`atomistic.edges.closures()`)
`gamma_edge_Mo.gamma_eV = 1.63`, `gamma_edge_S.gamma_eV = 1.21` eV/site (stable phases Mo 50 %, S 50 % at the reference condition; 0.51 and 0.38 eV/A), law `const`, method `MACE-MP-0 (medium)...`, `synthetic=False`. sigma = 0.53 eV/site each, in quadrature: separation 0.10, medium-vs-small model spread of the stable-pair ribbon sum 0.49 (0.15 eV/A; the dominant term), assumed MLIP floor 0.15 (an assumption, 0.05 eV/atom x 3 edge atoms, not derived), Dmu +-0.3 eV x slope 0.1. The S8 energy used for the small model was not re-minimised (<= 0.01 eV effect).
The vessel model uses one constant per edge, but gamma depends on Dmu_S by ~0.3-1.3 eV/site per eV; `mos2_edges.json["gamma_vs_Dmu_S"]` has the full table.

## Effect on the shape map (default tube, nothing in wulff.py edited)
`apply_wulff_closures` replaces 0.3/0.3 eV by 1.63/1.21 eV. Default map: triangle_Mo 7, truncated 14, triangle_S 19 of 40 points, boundary at 12.2 cm. With the MLIP values: **all 40 points collapse to "hexagon" at s = 0 and the boundary vanishes (0.5 cm)**, because exp(gamma/kT) at ~970 K is 3e8 (Mo) and 2e6 (S) times P_eq_ref = 1e-5 Pa (a synthetic value), pushing p_eq above the feed (0.1 Pa MoO3, 48 Pa S2) so both edges sit at the 1e-12 um/s floor and r = 1. This is not a physical prediction: it shows that the synthetic P_eq_ref (and the "gamma x a_site in the exponent" construction of the Wulff model) is inconsistent with a real edge energy; P_eq_ref must be re-anchored (e.g. from the gas-phase thermodynamics) before gamma can be used. The only closure-robust output is the difference gamma_Mo - gamma_S = +0.42 +- 0.5 eV/site (Mo edge more expensive at this condition; opposite sign possible within sigma, and sign depends on Dmu).

## Attachment energies (not barriers)
Energies of relaxed end states, 4-cell ribbons, J = 6. S edge, adding Mo rows (MoS2 units): incremental 1st +2.37, 2nd +0.19, 3rd -0.01 (kink site, about 0 as expected for a half-crystal site, a consistency check), 4th (row closed) -2.56 eV; kink formation about 1.3 eV. A lone Mo adatom: bare Mo +4.49, MoS1 +2.75, MoS2 +2.37, MoS3 +0.96 eV (MoS3 value shifts by -Dmu_S, so about 2.1 eV at Dmu = -1.15). Mo edge, adding S to the bare (0 %) edge: -1.0 to -2.6 eV per S vs S8; full row -1.0 eV/S. These mix S binding with edge-phase change on an unstable starting edge; they are not the S-attachment energy at the stable 50-100 % edge. Not computed: NEB barriers, gas-phase MoO3/S2 references, Mo attachment on the Mo edge, any edge diffusion. `k_attach_*` therefore stays synthetic; no Arrhenius closure is emitted.

## Literature comparison
- Levita et al. 2016 (0.77 eV/A zigzag, 0.52 reconstructed; recorded by the earlier tube agent in `edge_data.json`, termination/functional/reference not stated there and not re-read by me): our unreconstructed bare Mo edge 0.87 eV/A and mean of the ribbon (Mo 0 %, S 100 %) pair 0.51 eV/A at Dmu = 0; fully S-covered edges 0.16-0.24. Same order of magnitude, but not a like-for-like comparison (coverage, reference and functional unknown); not used to tune anything.
- Rosen, Notestein, Snurr, J. Phys. Chem. C 122, 15318 (2018), doi:10.1021/acs.jpcc.8b02524 (PBE-D3(BJ), 0-100 % coverage, H2/H2S conditions) is the right target. I could not read it, so no number or ordering is quoted from it; conditions differ anyway (hydrogen chemical potential vs CVD S2 gas). From general knowledge (unverified here), partial-coverage Mo edges and S-covered S edges being the stable sulfided edges is the commonly reported trend, which our ordering resembles.
- Cao et al., J. Phys. Chem. C 119, 4294 (2015), doi:10.1021/jp5097713: numerical tables not retrievable, so no check against its Mo-zz/S-zz energies. Barrier sources (Li et al. doi:10.1021/acsami.9b14577; Govind Rajan et al. doi:10.1021/acsnano.5b07916) not read.

## Limitations
MLIP error is typically 0.05-0.1 eV/atom and larger on undercoordinated edges (here the small/medium models disagree by 0.15 eV/A on the stable pair); only one 50 % S pattern per edge; no reconstructions beyond what BFGS finds from one start; no H, no solvent/substrate; no entropy or finite-T edge contributions; Dmu_S conversion approximate; triangle fits for Mo 100/50 % are noisy (residuals up to 1 eV) so those two edges rely on ribbon differences; vacuum test is weak (finite cutoff).
