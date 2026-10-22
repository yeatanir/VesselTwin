# Requests from Track S
- Track T (app/landing.py or streamlit_app.py): call `app.llm_settings.render()` once on Home so the LLM settings sidebar is there too (it already is on Workspace, Evidence, Advanced). Also the top navigation links were not found in the DOM of the rendered page (headless check); please confirm users can see page links.
