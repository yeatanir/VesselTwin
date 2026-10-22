# Re-anchoring the Wulff equilibrium term on kink energies

Code: `vessels/cvd_tube/wulff.py` (`p_eq`, `eq_model`), `atomistic/edges.py` (`mo_kink`, `closures_kink`), tests `tests/test_wulff_anchor.py`, evaluation `docs/wulff_reanchor_eval.py` (+ `.json`). MLIP = MACE-MP-0 medium, not DFT.

## Why
The old term p_eq = P_eq_ref exp(gamma_edge a_site/kT) used an edge excess energy per site. With MLIP gamma (1.63 / 1.21 eV/site) p_eq exceeds the feed, both edges sit at the rate floor and the map collapses to hexagons (`eq_model="legacy_gamma"` still reproduces this; regression test). Equilibrium between crystal and vapour is set at a half-crystal (kink) site, so the right input is the energy to remove one growth unit from a kink.

## Derivation
E_kink,e = energy to take one unit from a kink of edge e to its gas reference (eV, positive = bound). Crystal unit chemical potential at the kink = E_ref - E_kink; gas = E_ref + g0(T) + n kT ln(p/p0). Setting them equal gives p_eq; the forward rate is k(p - p_eq), the reverse k p_eq, so detailed balance (net rate 0 at p = p_eq) is exact.
- **Mo-zz edge, S feed.** Unit = one S atom from 1/2 S2 (Tier 1 species). E_ref = E_MACE(S8 ring)/8, the same reference as `gamma_edge`. Gas mu_S = E_ref + Dmu_S(T,p), Dmu_S = Dmu_std(T) + 1/2 kT ln(pS2/1 bar), where Dmu_std(1073 K) = -1.148 - 1/2 kT ln(50/1e5) = -0.796 eV (from `edge_energies.md`: MLIP S8 free energy + JANAF S8 = 4 S2) and the T dependence is the JANAF S2 Gibbs energy. Hence p_eq,Mo = 1 bar exp(-2 (E_kink_Mo + Dmu_std(T))/kT). The factor 2 is S2 -> 2 S. The standard-state conversion is the 1 bar choice in Dmu_std; `mu_S_eV` still offsets ln pS in the feed.
- **S-zz edge, Mo feed.** Unit = MoS2, Mo-bearing vapour in MoO3-unit equivalents (Tier 1). E_kink_S is measured relative to the bulk MoS2 formula unit (ideal half-crystal site = 0). The pressure of Mo vapour in equilibrium with bulk MoS2 (MoO3 + S2 -> MoS2 + SO2 thermodynamics) is not in the repo: `P_std_Mo_Pa` stays **synthetic** (1e-5 Pa, the old scale). p_eq,S = P_std_Mo_Pa exp(-E_kink_S/kT).

New ParamDefs: `E_kink_Mo.E_eV`, `E_kink_S.E_eV` (synthetic defaults 1.7 / -0.3 eV chosen so the default map is unchanged: S edge identical to the old p_eq, Mo edge within ~2x near 1070 K, 50x lower at 1000 K, default map identical), `P_std_Mo_Pa`, `Dmu_S_std_eV` (MLIP+JANAF, sigma 0.3 eV), switch `eq_model` (`kink` default, `legacy_gamma`). `gamma_edge_*` closures are still accepted and only act with `legacy_gamma`.

## What was computed (MLIP)
- `E_kink_S = +0.008 eV` vs bulk MoS2 (3rd MoS2-unit increment on the S edge, earlier agent), sigma 0.18.
- `E_kink_Mo = 0.52 eV` (`atomistic.edges.mo_kink`, `atomistic/data/mo_kink.json`): S added one site at a time to the stable 50 %-S Mo edge (J=6, 4-cell periodic row, medium model); increments vs S8: -0.45, -0.67, -0.38, -0.40 eV; kink value = mean of the two middle ones, spread 0.29, sigma 0.21 with the assumed 0.15 eV MLIP floor (assumption, as in `closures()`). This is the S-coverage kink (50 % -> 100 %), the only S-attachment step with a defined growth-unit meaning I could compute; it is not Mo-row growth on the Mo edge (no Mo-row attachment on the Mo edge was computed).

## Effect (new Smolik MoO3 basis, default tube; `docs/wulff_reanchor_eval.json`)
| map | classes (40 pts) | boundary | mean band p95-p05 |
|---|---|---|---|
| default (synthetic) | 29 triangle_Mo, 11 triangle_S | 18.2 cm | 2.0 |
| kink MLIP closures | 40 triangle_Mo | none | 1.05 |
| legacy gamma + MLIP gamma | 40 hexagon | 0.5 cm (collapse) | 0 |
The hexagon collapse is gone, but the map still collapses, now to triangle_Mo: p_eq,Mo = 5e6 Pa at 1000 K. At the CVD sulfur chemical potential (-1.15 eV) the MLIP binds an extra S at the Mo-edge coverage kink by only 0.5 eV, not the ~1.15 eV needed, so the Mo edge never advances. This is consistent with the edge phase result (the 50 % edge is the stable one), and says that "S filling" is not the Mo-edge growth step; the physical Mo-edge growth unit (Mo plus S, with an Mo source) was not computed. MLIP over-binds MoS2 by ~0.4 eV/f.u. vs experiment, which would also shift the S reference; it cannot rescue 6 eV worth of exponent (2 x 0.6 / kT ~ 13 e-folds).

## Benchmark (bench.shape_score functions, closures merged per case; bench/* untouched; "before" = new Smolik default)
| | in-scope acc | all acc | majority baseline | abstain-if-band acc (all) |
|---|---|---|---|---|
| before (default constants) | 0.50 | 0.50 | 0.50 (triangle) | 0.43 |
| after (kink closures) | 0.50 | 0.50 | 0.50 | 0.00 |
| before, simnad_ocr basis | 0.12 | 0.21 | 0.50 | 0.14 |
| after, simnad_ocr basis | 0.50 | 0.50 | 0.50 | 0.07 |
Both runs are at the majority baseline: the model predicts "triangle" for every case (S06 hexagon and S04 truncated missed). No improvement; the "after" equals always-triangle because the whole map is triangle_Mo. Nothing was tuned to the score.

## Limits
Single MLIP model and one pattern per kink; MACE error and MLIP floor assumed, not derived; kink energies are end-state energies (no barriers, no NEB, no entropy of kink formation, no vibrational free energy in the crystal term); the Mo-vapour reference (P_std_Mo_Pa) is synthetic; Dmu_std conversion +-0.3 eV = +-6.5 e-folds in p_eq,Mo; kink-site equilibrium is edge-independent in thermodynamics (E_kink,e should equal the bulk chemical potential up to MLIP error), so edge selectivity must come from k_attach (still synthetic).
