# Checklist: Vessel view tab (look at it in Safari, 1440 px and 390 px wide)

Run `make dashboard`, open the "Vessel view" tab. Do each vessel at Solver tier 0, 1 and 2.

1. Your vessel (all tiers): the picture redraws when you edit a sidebar parameter (tube: furnace T, boat positions; ampoule: tilt, D, T source/sink; flask: rpm, bar; sorbent: bed length; photoreactor: distance).
   - Tube: temperature colours the tube, green arrows = gas flow, yellow star = substrate (growth).
   - Ampoule: rotates with tilt, arrows hot to cold, star at sink.
   - Sorbent: colour = CO2 level, star = front. Photoreactor: colour fades with depth.
2. What the model predicts (tier 1+): solid = model output, shaded = p05 to p95, dashed = your input. Badges read "Model (Tier 1)" and "Synthetic inputs" where inputs are synthetic. Sorbent slider moves the front; nothing autoplays.
3. Flow and temperature inside (tier 2, tube / ampoule / flask only): each panel has one colorbar with units, orange streamlines, and the line "case - cells - made date - stored CFD result, not re-run". Sorbent and photoreactor say no stored result.
   - Change ampoule tilt or D: a warning appears when the stored case used other inputs ("not recomputed").
4. Text: only a title and one short line per panel; "Details" expanders are closed and hold tables, tiers.json status, sources.
5. Light and dark theme (Settings menu): all text and colourbars readable; no figure has a white box in dark mode.
6. 390 px wide: columns stack, no sideways scrolling, figures not clipped.
7. Speed: switching vessel or tier renders in about 3 s (first time per parameter set may be slower).
Known limits: ampoule/tube/flask CFD cases are specific stored runs (see Details); flask CFD uses an equal-volume cylinder.
