# Requests from Track H
1. tiers.json: none required. The Vessel view shows each vessel's existing `status` text under Details.
2. Home page: call `app.vessel_view.render_vessel_hero(result, vessel, spec, height=360)`; `spec` may be None.
3. Optional (dashboard owner): the one dashboard hook is `names = [... "Vessel view", "Credibility"]` plus one `with tabs["Vessel view"]:` line before the credibility section.
4. Stored cases live in a session scratchpad; `scripts/export_fields.py --root <dir>` regenerates data/viz_cache/*.npz. If those case dirs are lost the committed caches are the only copy.
