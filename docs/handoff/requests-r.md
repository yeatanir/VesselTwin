# Requests from Track R
1. app/home.py `_step_matters` (Track Q): replace the altair bar chart with `st.plotly_chart(plotly_figs.knob_bars(story["knobs"][:5], unit=SCENARIOS[v]["proxy"][2]), width="stretch")`.
2. app/furnace_view.py (Track O/Q): use `plotly_figs.furnace_figs(prof, v)` -> [(title, fig)] instead of fz.* so the tab gets the blue-white template.
3. Plot config for all st.plotly_chart: `{"displayModeBar": "hover", "scrollZoom": True, "displaylogo": False}` (see app/vessel_view.py CFG).
