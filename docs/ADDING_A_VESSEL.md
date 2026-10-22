# Adding a vessel

1. Copy `vessels/_template.py` to `vessels/my_vessel.py` (or a package `vessels/my_vessel/__init__.py`).
2. Edit `DEFS` (every dimension and knob as a `ParamDef`: unit, bounds, sigma, source), `tier0`, `solve`, and the `register(Vessel(...))` call.
   Mark anything illustrative `source="synthetic"`.
3. Restart the dashboard (`make dashboard`). The vessel is in the dropdown. No other file changes: `core.registry.load_all()` imports every module in `vessels/` whose name does not start with `_`.
4. Optional: chemistry sets as `presets/<vessel>__<name>.json` with a `_meta` entry (`{"title": ..., "source": ...}`) plus any ParamDef values; add the vessel to `tiers.json` so the badge is honest.
5. Add a test tagged `@pytest.mark.vessel("my_vessel")`; `make test` refreshes the Credibility tab.

Contracts that matter: `solve` returns scalars whose keys are in `units` and includes `T_K`; `tier0` returns `(Regime, margin, numbers)`.

## Quick try in the Studio (no files written)

The Studio page, tab "Add a vessel", clones a template vessel's ParamDefs with your values, runs the template physics for this session only, and labels the result `hypothesis` (borrowed physics, not validated for your geometry). "Download vessel stub" gives a `vessels/<name>.py` whose `tier0`/`solve` delegate to the template; drop it into `vessels/`, restart, then replace the borrowed physics with your own model following the steps above.
