# Track C requests (files I do not own)

## To Track E (photoreactor): extras plot schema
The dashboard (app/common.py) draws plots from `result["extras"]` in either of two formats (nothing else needed from Track E):
1. Default declared list: `{"plots": [{"title", "kind"?: "line"|"bar", "x": {"name","unit","values"}, "y": {"name","unit","values"}, "band"?: {"p05": [...], "p95": [...]}}]}`
2. Track E's own `extras["photon_flux_vs_depth"] = {"x","x_label","x_unit","y_label","y_unit","p05","p50","p95"}` (any extras entry with `x` and `p50` lists is drawn as line + p05..p95 band). `extras["notes"]` (list of str) is printed under the plots.
Until Track E's change is merged, the photoreactor shows a bar chart of the existing `extras["sensitivity"][knob]["dln_rate_per_sigma"]`.

## To Track F / merger
- Only after the user merges: `tiers.json` status text from requests-b.md R3 and requests-e.md is Track F's; the dashboard reads it unchanged.
- Dashboard items from requests-b.md R2 (GCI bands) and R5 (surrogate corrections) depend on files that are not on main (`tier2/verification/gci.json`, `surrogate/correction.py`) and on core changes; not applied. If they land on main before 17:00 Oct 21 I will wire them as read-only captions.
