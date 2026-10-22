# Track J requests

1. app/dashboard.py (hook lines, already applied on track-j; merge by hand if another track changed the same lines):
   - `st.set_page_config(..., initial_sidebar_state="collapsed")` so the front door is not the parameter form.
   - outer `st.tabs(["Home", "Advanced"], key="vt_main", on_change="rerun")` created right after set_page_config; `app.home.render()` runs inside Home.
   - the vessel/chemistry/tier selector row and the tier status line now render inside the Advanced tab; the existing inner tabs (Results, Brief, Reasoning trace, Credibility) are created inside Advanced with key `vt_adv` (so Home's "See the reasoning" button can select them).
   - Needs a Streamlit with tab state (`st.tabs(key=, on_change=)`, installed 1.66). Older Streamlit falls back to plain tabs; the button then cannot switch tabs.
2. requirements.txt: `streamlit>=1.40` should become the version that has tab state (1.66 here; plotly is used by Track H's hero and must be in requirements).
3. Track H: Home calls `app.vessel_view.render_vessel_hero(result, vessel, spec, height=300)`; it draws itself. If missing or it raises, Home draws a small schematic placeholder.
4. Track F / tiers.json: none. Home reads label rules from llm.trace only and prints the 2/8 vs 6/8, shape-class, CFD-missed sentence from docs/status_oct21.md.
5. app/home_data/*.json is a committed snapshot of the three demo stories (model outputs). If vessel physics or ranking change, regenerate with `python -m app.home` (a test fails if the demo text changes).
