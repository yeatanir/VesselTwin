# Home page checklist (Safari)

Run `make dashboard`, open the URL in Safari. The page opens on the Home tab with the sidebar collapsed. Do each pass at **1440 x 900** and at **390 px wide** (Safari: Develop > Enter Responsive Design Mode), in **light** and **dark** (System Settings > Appearance, or Safari Develop > Show Web Inspector > Elements > dark-mode toggle). 4 passes.

For every step the whole step must fit without page scrolling at 1440 x 900 (390 px may scroll). Next and Back must be easy to hit.

1. Header: "VesselTwin", one short pitch line, an orange "Research prototype" badge. Readable in dark mode; the badge text is not clipped.
2. Stepper: five labels, the current one underlined in dark blue, earlier ones light blue.
3. Procedure: three scenario cards (MoS2 CVD tube first, selected). Click each: the card outline turns blue and the text box changes. Press "Read procedure": numbers in the text get blue chips, and orange (default) and pink (missing) chips appear under the legend. Text not highlighted must stay readable.
4. Vessel: the vessel figure (from Track H) with a bright marker, then three big-number tiles, each with a unit and a status dot (blue circle = model, orange diamond = synthetic). Check the dot colours differ by shape too.
5. What matters: one horizontal bar chart (max 5 bars) with grey whiskers, a bold "Change X first." line, a closed Details expander. Check bar colours (blue up, orange-red down) in dark mode and that axis labels are not cut off.
6. What to calculate: up to three ranked cards (number, plain name, one line, cost badge). Details expander is closed.
7. How far to trust: a three-colour meter with counts, three labelled chips (benchmarked, uncertain, hypothesis), "This setup: hypothesis", one sentence mentioning 2/8 vs 6/8, shape class, CFD targets missed. Press "See the reasoning": the Advanced tab opens on Reasoning trace. If it opens on Advanced but another inner tab, say so (browser-side tab state).
8. Advanced tab: all old content is still there (Results, Brief, Reasoning trace, Credibility), with the vessel/chemistry/tier selectors at its top and the sidebar form still working (open the sidebar with the arrow at top left).
9. Switch scenario to Sealed ampoule and Sorbent bed and click through all five steps again. Sorbent can pause a few seconds on the first visit only if you edit the text.
10. Never expected: red error boxes, "Hero figure unavailable", a word "Claude" or "Anthropic" anywhere on Home.

Report anything that fails with: step, width, light/dark.
