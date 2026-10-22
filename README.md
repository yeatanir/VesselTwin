# VesselTwin

> **Provenance.** Development began on Oct 18, 2026 in a private repository (archived as `VesselTwin-dev-history`); the OSI Hackathon period began Oct 21, 2026. This repository is a clean snapshot of the final code, with history starting on the day it was created.

A procedure goes in, a vessel digital twin comes out: the text becomes a checked setup spec, the flow regime is called instantly (Tier 0), a reduced model with Monte Carlo gives a conditions passport (Tier 1), and cached CFD backs it up (Tier 2).
The LLM never produces a physical number: values come from the text (span-checked), defaults, a property DB, or a solver.
Generality lives in three contracts (SetupSpec, Passport, Closure); the dashboard only shows it off.

## Architecture

```
procedure text --llm/extract (rules | any LLM provider)--> SetupSpec (stated / default / missing, span-checked)
                                                        |
             presets/<vessel>__<set>.json  --->  core.api.solve  <--- Closure (atomistic -> vessel params)
                                                        |
        vessels/*.py  (auto-discovered)   tier0: regime + margin  ->  tier1: reduced model + Monte Carlo
                                                        |                         |
                                                    Passport  <--  tier2/ (OpenFOAM v2512, cached in cache/tier2/)
                                                        |
                                   app/dashboard.py: Results | Brief | Credibility
```

## Quickstart

```
conda activate research            # or: python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
make test                          # also writes cache/harness.json
make demo                          # default case through every stage, all vessels
make dashboard                     # Streamlit, offline
```
`make test PY=python` uses the active interpreter (the Makefile default is the author's conda env).

## Vessels and contracts

| Vessel | Tier available | Notes |
|---|---|---|
| cvd_tube | 1 | MoS2 CVD tube, Wulff shape vs position |
| ampoule | 2 | sealed-ampoule transport, OpenFOAM v2512 case |
| flask | 1 | stirred flask, Villermaux-Dushman |
| sorbent | 1 | adsorption column, isotherm closures |

A vessel is one file in `vessels/`: a `ParamDef` list (unit, bounds, sigma, source), `tier0`, `solve`, `register(...)`. `schemas/` holds the frozen contracts: SetupSpec (input), Passport (output), Closure (atomistic to vessel).

## Honesty

Sourced versus illustrative is tracked per parameter: `source="synthetic"` marks a placeholder and shows an amber "synthetic" badge in the UI; any passport that depends on one is flagged `synthetic=True`.
`tiers.json` records the highest tier per vessel and an honest status line (shown as a badge). The Credibility tab lists every test from the last `make test` (`cache/harness.json`, with the committed `docs/harness_snapshot.json` as fallback on a fresh clone). Nothing is shown as passing without a test.
Known limits: Tier 1 convection enhancement is not confirmed by Tier 2; kinetic Wulff rates are synthetic (trend direction only); the real 100-procedure benchmark is a human task.

## Add a vessel

Drop a file into `vessels/` (start from `vessels/_template.py`); it appears in the dashboard with no other edit. Chemistry sets are `presets/<vessel>__<name>.json` with an optional `_meta` entry (`title`, `source`). See `docs/ADDING_A_VESSEL.md`.

## Tier 2 (CFD)

OpenFOAM openfoam.com v2512 is not on PATH. Launch `/Applications/OpenFOAM-v2512.app` (it mounts a case-sensitive volume), write a case with `tier2.openfoam.write_case`, then `tier2/run.sh <case_dir>`. Save the resulting passport JSON to `cache/tier2/<vessel>.json`; the dashboard shows it under "Tier 2" and never runs OpenFOAM itself.

## Run offline, or with your own LLM

Everything runs offline with the default `rules` extractor, scripted agent replay and recorded traces: no key, no network (`make dashboard`, or `pip install -r requirements.txt && streamlit run app/dashboard.py`).

To use a live model, choose any provider and supply your own key. Either fill in the sidebar expander "LLM settings (optional)" (key kept in the browser session only, "Test connection" button) or set environment variables:

```
export VT_LLM_PROVIDER=openai_compatible          # openai_compatible | anthropic | mlx | rules
export VT_LLM_BASE_URL=https://your-host/v1       # or the full .../chat/completions URL
export VT_LLM_MODEL=your-model-name
export VT_LLM_API_KEY=...                         # never commit or log this
export VT_LLM_EXTRA_HEADERS='{"OpenAI-Organization": "org-..."}'   # optional: organisation / workspace / project ID
python -m llm.agent --provider openai_compatible --base-url https://your-host/v1 --model your-model-name
```

In code, `extract(text, vessel, backend="llm")` uses the same variables. `anthropic` (Messages API; optional workspace header) is one optional provider among these; `mlx` is a local model (untested here). The model only proposes; value, span and bounds checks are the same for every backend, and keys never appear in recorded traces.

## Docker and Codespaces

`docker build -t vesseltwin . && docker run --rm -p 8501:8501 vesseltwin`, or open the repo in GitHub Codespaces (`.devcontainer/` forwards port 8501). The Docker files have not been built on the authoring machine. See `docs/deploy.md` (also Streamlit Community Cloud, Hugging Face Spaces, and why a static stlite build is not feasible today).

## Layout

`core/` registry, api, params, uq, dimensionless, pipeline · `vessels/` one file or package each · `presets/` chemistry sets · `schemas/` contracts · `llm/` extractor, span check, units · `tier2/` OpenFOAM case writer and parser · `atomistic/` closures · `bench/` procedures and scoring · `app/` dashboard · `tests/` harness · `tiers.json` · `docs/`.

## Licence

TBD (placeholder; choose an OSI-approved licence before Oct 22).

## 90-second demo

1. (0-15 s) Paste a MoS2 procedure; Extract. Stated values green, defaults amber.
2. (15-35 s) Tier 0 shows the regime instantly; switch to Tier 1: conditions passport, amber synthetic badges.
3. (35-55 s) Shape-vs-position slider: move the sulfur boat temperature, the triangle/hexagon boundary moves (about 0.8 cm per 10 C near the default, with the default constants; hotter than ~190 C the whole substrate is S-rich and the boundary leaves the map). Say on screen that the shape rates are synthetic and were tuned: this shows the workflow and the direction, not a prediction.
4. (55-70 s) Brief tab: ranked decisions from the passport.
5. (70-80 s) Drop a new file into `vessels/` and refresh: the vessel is in the dropdown. Tier 2 shows the cached CFD or the run command.
6. (80-90 s) Credibility tab: the tests behind every claim.
