# Deploying VesselTwin

The dashboard needs only `requirements.txt`. It runs fully offline with the `rules` extractor and scripted/recorded agent traces; no API key, no network, no OpenFOAM. A fresh-venv check (Python 3.14, `pip install -r requirements.txt`, Streamlit AppTest loading the dashboard) loaded without exceptions. The Dockerfile, devcontainer, Streamlit Cloud and Hugging Face recipes below were **not run** (Docker is not installed on the authoring machine); they are minimal and standard.

## Local Docker
```
docker build -t vesseltwin .
docker run --rm -p 8501:8501 vesseltwin          # http://localhost:8501
```
The image runs as a non-root user, listens on 0.0.0.0:8501, has usage stats off and a healthcheck on `/_stcore/health`. To use your own LLM, pass settings at run time (never bake keys into the image):
`docker run --rm -p 8501:8501 -e VT_LLM_PROVIDER=openai_compatible -e VT_LLM_BASE_URL=https://host/v1 -e VT_LLM_MODEL=NAME -e VT_LLM_API_KEY vesseltwin`
(`-e VT_LLM_API_KEY` without a value forwards it from your shell.) Or just type them into the sidebar "LLM settings (optional)".

## GitHub Codespaces
`.devcontainer/devcontainer.json` installs `requirements.txt`, starts the app and forwards port 8501. Open the repository on GitHub, Code > Codespaces > Create; the forwarded port opens the dashboard. Keep the port private. Add keys as Codespaces secrets named `VT_LLM_API_KEY` etc., not in files.

## Streamlit Community Cloud
Connect the GitHub repo, main file path `streamlit_app.py` (repo root; it hosts Home, Workspace, Evidence and the old dashboard as Advanced), Python 3.12; dependencies come from `requirements.txt`. API keys, if any, go in the app's Secrets or in the sidebar. Nothing else to configure; the app works without them. The free tier has limited memory: the Monte Carlo runs are small, but the sorbent vessel is the slowest.

## Hugging Face Spaces
Create a Space with the Streamlit SDK (or Docker SDK using this Dockerfile with `app_port: 8501` in the README front matter). Set the app file to `app/dashboard.py`. Keys go in Space secrets (exposed as environment variables `VT_LLM_*`).

## Static GitHub Pages via stlite (Streamlit in WebAssembly)
Verdict: **not feasible as it stands; possible only as a reduced demo after real work. Not built, nothing published.**

Checked against the opened Pyodide package list (pyodide.org/en/stable/usage/packages-in-pyodide.html) and the stlite README:
- Built in to Pyodide: numpy 2.4.6, scipy 1.18.0, pandas 3.0.2, pydantic 2.12.5 (pydantic_core 2.41.5), pyyaml 6.0.3, altair 6.0.0, jsonschema 4.26.0, scikit-learn 1.8.0.
- **pint is not in the list.** It is pure Python, so `micropip` could probably install it from PyPI, but I did not test that.
- Imports in the repo that would be a problem: `sklearn` (surrogate/*; available in Pyodide, but GP fits are slow in single-threaded WASM), optional `openpyxl`, `mace`/`ase`/`e3nn`/`pyiast`/`mlx_lm`/`anthropic` (atomistic and bench paths only, not the dashboard core), `concurrent.futures`, `tempfile`/file writes (`cache/dashboard`, `runs/`) which need the ephemeral in-browser filesystem.
- stlite limits from its README: single-threaded, `time.sleep` is a no-op, ephemeral filesystem, only a limited set of `urllib`/`requests` features (so the LLM backends in `llm/backends.py`, which use `urllib`, would need `pyodide.http.pyfetch`, and browsers would hit CORS limits on most provider APIs), and stlite pins its own Streamlit build, so the Streamlit version used here (>=1.40) may not match.
- Reasons it is not feasible today: the whole `core/`, `vessels/`, `llm/`, `surrogate/`, `presets/`, `schemas/` tree would have to be shipped as files into the Pyodide filesystem; Tier 1 Monte Carlo and the GP surrogates in a single browser thread would be slow; the app was never run under Pyodide, so import failures are unknown. A realistic route is a separate stripped-down page (Tier 0 plus recorded results), which is a different product from this dashboard. Use Codespaces or Streamlit Community Cloud for a link instead.

## Keys and privacy
Keys typed in the sidebar live only in that browser session's Streamlit state; they are not written to disk or to traces (a test checks this). A hosted app means the key passes through the host's server: use a key with a spend limit, or run locally.

## Literature and LLM settings
LLM settings (sidebar expander, `app/llm_settings.render()`) are on Workspace, Evidence and Advanced; values are mirrored into `st.session_state["vt_llm"]` so they survive page changes. The Literature section is offline (stored `docs/literature/*.json`); a live Edison question needs the optional `edison-client` package (not in requirements) and your own key typed into the page. Valency has no documented HTTP API reachable with a key, so nothing live is implemented for it.
