# Checklist: Furnace and flow tab (Safari, 1440 px and 390 px wide)

Run `make dashboard`. Open Advanced, then the "Furnace and flow" tab. Vessel template = the tube (the default). Try Solver tier 0, 1 and 2: the tab looks the same at each.

1. Top picture: the tube drawn along its length, colour = furnace wall temperature (one colourbar, units C), dotted orange box = heated zone, green arrow = gas flow, boats and substrate are small boxes coloured by their computed temperature, yellow star = where growth is computed. The caption says the diameter is exaggerated.
2. Below it, three plots on the same x axis (cm from the tube centre): temperatures (wall, quartz, gas centreline and mean, boat, substrate; shaded band = p05 to p95; dotted vertical lines = boat and substrate), velocity with Reynolds number (orange sliver = entrance region), and two thin strips (buoyancy, Peclet; blue = forced flow, orange = buoyancy or diffusion matters). The tick marks line up between the plots.
3. One line under each plot. The numbers in it change when you change an input (they are computed, not typed).
4. Change a value (for example Zone 1 setpoint, Boat from centre, Carrier flow) and press Update. The figures redraw in about 2 s or less. Nothing changes until you press Update.
5. Heating zones = 2 or 3: the dotted box gets dividers and the wall profile gets steps. Thermal model = legacy: temperatures switch to the legacy model; a yellow note says it ignores zones and pasted profiles.
6. Tick "Compare legacy and furnace": an extra plot overlays the two models, with a one-line difference at the substrate.
7. Open "Paste a measured wall profile". Paste `-20, 25` / `-10, 600` / `0, 750` / `10, 600` / `20, 25` (one per line) and press Update: the wall follows your points. Paste a bad line (for example `banana`, or `0, 9999`): a red message names the line numbers and the profile is ignored; the page keeps working.
8. Badges under the form: model (Tier 1); not validated against measured temperatures; CFD agreement 45 of 52 stored cases (same-physics CFD, not independent); did not reproduce Momeni 2018 simulation (+143 K). The numbers come from bench/track_n/results.json.
9. "Details" (closed): the model's assumptions, the list of synthetic constants, and the constants that have a source.
10. Other vessels: the tab shows one line, "Furnace and flow is only for the tube furnace."
11. Light and dark theme: text and colourbar readable; no white boxes except the small label chips on the boats. 390 px: controls stack, plots fit without sideways scrolling.
Known limits: boat and substrate temperatures rest on synthetic constants and are not validated; the strips use the model's own flags; the x positions of a pasted profile are measured from the tube centre.
