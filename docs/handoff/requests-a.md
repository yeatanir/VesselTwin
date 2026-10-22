# Requests from Track A (for Track C dashboard captions, Track F integration / tiers.json)

## Dashboard captions (Track C), text to paste
**Shape map caption:** "Hypothesis, not a prediction. The edge rates are synthetic. Replacing the MACE sulfur-binding numbers with dispersion-corrected DFT (Rosen et al. 2018) on the Mo edge does not make the map better: it still calls triangle everywhere (shape accuracy 0.50 = always-triangle baseline, n = 14; n = 8 in scope). With the DFT Mo edge and the synthetic S edge the map looks as before because the synthetic S-edge and attachment constants set it."

**Sensitivity benchmark caption:** "Direction of the effect of one knob on nucleation density, domain size, coverage or layer number, from mean-field nucleation theory (N ~ F^(i/(i+2))). Development set (items already seen), n = 9 scored: model 3/9 correct (6 confident calls, 3 correct; 3 abstentions), blind no-tool baseline 6/9, always-increase 4/9. Original 8 items: model 2/8 (5 confident, 2 correct), blind 6/8, always-increase 4/8; the previous model scored 5/8. Held-out (3 items from one paper, Jian 2019): model 0/3 (called no change because the vapour-pressure law stops at the melting point), blind 3/3. Too few to support any claim. Lead with the abstentions and the labelled assumptions, not with accuracy."

## tiers.json status text (Track F applies)
cvd_tube: "Tier 1. Shape map: hypothesis (synthetic edge rates; DFT Mo-edge S binding added as an option, map still not predictive). Sensitivity direction: development-set accuracy below a blind no-tool baseline; handles added for MoO3/S inventory and source-substrate gap; held-out n = 3, no claim."

## Code requests (files I do not own)
- `atomistic/edges.py`/`docs/edge_energies.md` (owner unclear): none needed; the DFT data live in `vessels/cvd_tube/rosen_sbinding.py` and `rosen_mo_edge.json`.
- `docs/harness_snapshot.json`: regenerate before the final commit (Track F) because tests were added.
- Dashboard (`app/dashboard.py`, Track C): the new ParamDefs `m_MoO3_mg`, `m_S_mg`, `gap_mm`, `dE_Mo_dft_eV`, and `eq_model="dft_rosen"` appear automatically in the editable parameter list; `m_*_mg` defaults are 1e6 (= unlimited), so the UI may want to hide them or show "unlimited".
- Missing science (nobody owns): a sourced liquid-MoO3 vapour-pressure branch above 1068 K (Smolik et al. is solid only) would let the model respond to a 1073-1123 K boat; Wang et al. 2014 (Chem. Mater. 26, 6371) is closed access and needs a library copy for the A5 threshold.
