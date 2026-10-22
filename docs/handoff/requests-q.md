# Requests from Track Q
- streamlit_app.py (Track P): call `app.workspace.render()` and `app.evidence.render()`. Workspace reads `st.session_state['vt_vessel']` (one of cvd_tube, ampoule, flask, sorbent, photoreactor) to preselect the vessel and writes it back.
- Track R: workspace calls PF.vessel_hero(vessel, res, None, height=380), PF.cfd_field(vessel, field, case_name), PF.knob_bars(rows) (rows: dicts knob/name/effect/lo/hi), PF.profiles(vessel, res, spec); all wrapped in try/except with fallbacks.
