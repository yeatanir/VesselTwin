# Track R progress
Files touched: app/viz/plotly_figs.py (new), app/viz/template.py (new), app/viz/schematics.py, app/viz/profiles.py, app/viz/fields.py, app/viz/furnace.py (template only), app/vessel_view.py (minimal), tests/test_plotly_figs.py, docs/progress/track-r.md
Finding: all app figures were already Plotly (matplotlib only used as colormap/streamline integrator, never shown; no st.pyplot/st.image). Work = template, hover on components, CFD dropdown, sliders, wrappers.
