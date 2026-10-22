"""VesselTwin demo dashboard. Driven only by core.api (offline, no OpenFOAM). Run: make dashboard"""
import hashlib, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import altair as alt, pandas as pd, streamlit as st
from core import api
from app.common import show_df, status_badge, render_extras, clean

try:
    from llm.extract import extract_and_solve
except Exception:  # extractor not installed -> disabled state, manual form still works
    extract_and_solve = None
try:
    from vessels.cvd_tube.wulff import shape_map, knob_sensitivity
except Exception:
    shape_map = knob_sensitivity = None

try:
    from app.brief_tab import render as render_brief  # written by the brief agent; tab hidden until it exists
except Exception:
    render_brief = None
try:
    from app.trace_tab import render as render_trace
except Exception:
    render_trace = None
from core import params as _params
from core.registry import load_all

TIERS = json.loads((ROOT / "tiers.json").read_text()) if (ROOT / "tiers.json").exists() else {}
TIER_OPTS = {0: "Tier 0: regime only (instant)", 1: "Tier 1: reduced model + Monte Carlo", 2: "Tier 2: CFD (cached)"}
CACHE = ROOT / "cache" / "dashboard"
N_MC = {"sorbent": 12}  # slow vessel -> few MC samples
AMBER, BLUE = "#b7791f", "#2a6fb0"
SYN = ":orange[synthetic]"

try:  # as a page of streamlit_app.py the config is already set
    st.set_page_config(page_title="VesselTwin", layout="wide", initial_sidebar_state="collapsed")
except Exception:
    pass
# Home is the front door; the form lives in Advanced
try:  # Track J: Home (visual story) first and default; every existing tab sits under Advanced. Tab keys let Home's button jump to the trace.
    if st.session_state.get("vt_embedded"):  # streamlit_app.py has its own landing page
        raise ImportError
    from app import home as _home
    try:
        _tab_home, _tab_adv = st.tabs(["Home", "Advanced"], key="vt_main", on_change="rerun")
    except TypeError:  # older streamlit: no tab state, so the trace button cannot switch tabs
        _tab_home, _tab_adv = st.tabs(["Home", "Advanced"])
except Exception:
    _home = None
    _tab_adv = st.container()
if _home is not None:
    with _tab_home:
        _home.render()


def _key(*a):
    return hashlib.sha256(json.dumps(a, sort_keys=True, default=str).encode()).hexdigest()[:20]


@st.cache_data(show_spinner="solving...")
def solve(vessel, values, n_mc, seed=0):
    """api.solve keyed by hash(vessel, values, n_mc, seed); JSON on disk so repeat demos need no recompute."""
    f = CACHE / f"{_key(vessel, values, n_mc, seed)}.json"
    try:
        return json.loads(f.read_text())
    except Exception:
        pass
    d = api.defaults(vessel)
    r = api.solve(vessel, {k: x for k, x in values.items() if d.get(k) != x}, n_mc=n_mc, seed=seed)
    r = json.loads(json.dumps(r, default=float))
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(r))
    except OSError:
        pass
    return r


@st.cache_data(show_spinner="shape map...")
def cached_map(values, n_mc):
    return shape_map(dict(values), 40, n_mc)


@st.cache_data
def sweep(vessel, values, name, xs, out):
    """Re-solve over one parameter (small n_mc) and read one passport 'derived' median."""
    ys = [solve(vessel, {**dict(values), name: x}, 5)["passport"]["derived"][out]["p50"] for x in xs]
    return pd.DataFrame({name: xs, out: ys}).set_index(name)


def tag_synth(r):
    return SYN if r["passport"]["synthetic"] else ""


# ---------------- sidebar: vessel, procedure, parameters
vessels = {v["name"]: v for v in api.list_vessels()}
with _tab_adv:
    top = st.columns(3)
vessel = top[0].selectbox("Vessel template", list(vessels), key="vessel", format_func=lambda n: vessels[n]["title"])
sets = {"custom": {"title": "custom (defaults)", "params": {}, "source": ""}} | {p["name"]: p for p in api.preset_info(vessel)}


def _load_set():  # ponytail: on_change callback so widget keys are set before the form is built
    pr = st.session_state[f"chem:{vessel}"]
    for d in api.schema(vessel):
        st.session_state[f"{vessel}:{d['name']}"] = sets[pr]["params"].get(d["name"], d["default"])


cs = top[1].selectbox("Chemistry set", list(sets), key=f"chem:{vessel}", on_change=_load_set, format_func=lambda n: sets[n]["title"])
if sets[cs]["source"]:
    top[1].caption(f"source: {sets[cs]['source']}" + (" :orange[synthetic]" if sets[cs]["source"] == "synthetic" else ""))
tier = top[2].selectbox("Solver tier", list(TIER_OPTS), index=1, key="tier", format_func=TIER_OPTS.get)
ti = TIERS.get(vessel)
if ti:
    _tab_adv.markdown(f":orange[Highest tier available: {ti['tier']}] {ti['status']}")
with st.sidebar:
    __import__("app.llm_settings", fromlist=["render"]).render()  # Track G: optional LLM settings expander
    sch = api.schema(vessel)
    dflt = api.defaults(vessel)
    sk = lambda n: f"{vessel}:{n}"
    st.text_area("Procedure text", key="proc", height=100, disabled=extract_and_solve is None,
                 placeholder="extractor not installed" if extract_and_solve is None else "paste a procedure")
    if extract_and_solve is None:
        st.caption("Extractor not installed: manual form below.")
    elif st.button("Extract"):
        try:
            ex = extract_and_solve(st.session_state.proc)
            st.session_state.prov = ex.get("provenance", {})
            if ex.get("vessel") in vessels:
                st.warning(f"Extracted for {ex['vessel']}; select it to see values.")
            for n, x in ex.get("values", {}).items():
                st.session_state[f"{ex.get('vessel', vessel)}:{n}"] = x
        except Exception as e:
            st.error(f"extract failed: {e}")
    prov = dict(st.session_state.get("prov", {}))
    if cs != "custom":  # values coming from a chemistry set carry that set's provenance
        _src = sets[cs]["source"].lower()
        prov |= {k: ("synthetic" if ("synthetic" in _src or "illustrative" in _src or not _src) else "sourced") for k in sets[cs]["params"]}
    values = {}
    for g in dict.fromkeys(d["group"] for d in sch):
        with st.expander(g, expanded=g in ("operation",)):
            for d in [d for d in sch if d["group"] == g]:
                n, k = d["name"], sk(d["name"])
                syn = (d["source"] == "synthetic") and prov.get(n) not in ("sourced", "stated")
                state = prov.get(n) or ("edited" if st.session_state.get(k, d["default"]) != d["default"] else "default")
                lab = f"{d['label']} [{d['unit']}]" if d["unit"] else d["label"]
                badge = (":orange[synthetic] " if syn else "") + (":green[stated]" if state == "stated" else ":green[sourced]" if state == "sourced" else ":orange[default]" if state == "default" else ":blue[edited]")
                hlp = f"bounds {d['lo']}..{d['hi']}, sigma {d['sigma']}{' (rel)' if d.get('sigma_rel') else ''}; source: {d['source']}. {d['help']}"
                if d["choices"]:
                    values[n] = st.selectbox(lab, d["choices"], index=list(d["choices"]).index(d["default"]), key=k, help=hlp)
                else:
                    step = abs(d["default"]) * 0.05 or 0.01
                    values[n] = st.number_input(lab, float(d["lo"]), float(d["hi"]), float(d["default"]), float(step), format="%.4g", key=k, help=hlp)
                st.caption(badge)

names = ["Results"] + (["Brief"] if render_brief else []) + (["Reasoning trace"] if render_trace else []) + ["Vessel view", "Furnace and flow", "Credibility"]
with _tab_adv:
    try:
        tabs = dict(zip(names, st.tabs(names, key="vt_adv", on_change="rerun")))
    except TypeError:  # older streamlit: no tab state
        tabs = dict(zip(names, st.tabs(names)))
tab_res, tab_cred = tabs["Results"], tabs["Credibility"]
r = solve(vessel, values, 2 if tier == 0 else N_MC.get(vessel, 60))  # ponytail: tier 0 reuses the cached solve, only shows tier0 output

# ---------------- results
with tab_res:
    st.title(vessels[vessel]["title"])
    if tag_synth(r):
        st.markdown(f"{SYN} illustrative placeholders in play (tier 1 stubs/constants), not validated predictions.")
    c = st.columns([2, 3])
    c[0].metric("Regime", r["regime"].replace("_", " "), f"margin {r['margin']:.3g}", delta_color="off")
    c[0].caption(status_badge(r["passport"]["synthetic"], "computed, tier 0"))
    with c[1]:
        show_df(st, pd.DataFrame({"tier0 number": {k: float(x) for k, x in r["numbers"].items()}}))
        st.caption(status_badge(r["passport"]["synthetic"], "computed, tier 0"))

    if tier == 0:
        st.caption('Tier 0: regime and dimensionless numbers only. Switch tier for the passport and plots.')
    if tier == 2:
        f2 = ROOT / "cache" / "tier2" / f"{vessel}.json"
        if f2.exists():
            st.subheader("Tier 2 (CFD) passport, cached")
            st.json(json.loads(f2.read_text()))
        else:
            st.info(f"No cached Tier 2 result for {vessel}. Tier 2 needs the OpenFOAM v2512 volume (launch /Applications/OpenFOAM-v2512.app), "
                    "then run `tier2/run.sh <case_dir>` and save the passport to cache/tier2/%s.json. The dashboard never runs OpenFOAM. Tier 1 shown below." % vessel)
    if tier != 0:
        st.subheader("Conditions passport (p05 / p50 / p95)")
        ps = r["passport"]
        rows = [("T", ps["T_K"])] + [(f"{s} {q}", dd) for s, qs in ps["species"].items() for q, dd in qs.items()] + list(ps["derived"].items())
        df = pd.DataFrame([{"quantity": n, "unit": x["unit"], "p05": x["p05"], "p50": x["p50"], "p95": x["p95"],
                            "status": "synthetic inputs" if ps["synthetic"] else "sourced inputs"} for n, x in rows if x["p05"] is not None])
        st.caption(status_badge(ps["synthetic"], "computed, tier %s" % ps["tier"]))
        base = alt.Chart(df).encode(y=alt.Y("quantity:N", sort=None, title=None))
        st.altair_chart((base.mark_rule(color=BLUE, strokeWidth=3).encode(x=alt.X("p05:Q", scale=alt.Scale(type="symlog"), title="value (symlog)"), x2="p95:Q") +
                         base.mark_point(color=BLUE, filled=True, size=60).encode(x="p50:Q", tooltip=["quantity", "unit", "p05", "p50", "p95"])).properties(height=24 * len(df) + 40),
                        width="stretch")
        show_df(st, df, hide_index=True)

        pf = r["profile"]
        if vessel == "cvd_tube" and pf:
            st.subheader("Tube profile")
            x = pf["x_cm"]
            for key, title in [("T_C", "Temperature [C]"), ("ratio_Mo_S", "Mo:S ratio"), ("supersaturation_MoO3", "MoO3 supersaturation")]:
                d = pd.DataFrame({"x_cm": x, "y": pf[key]})
                ch = alt.Chart(d).mark_line(color=BLUE, strokeWidth=2).encode(x="x_cm:Q", y=alt.Y("y:Q", title=title))
                sub = alt.Chart(pd.DataFrame({"x": [pf["x_substrate_cm"]]})).mark_rule(color=AMBER, strokeDash=[4, 3]).encode(x="x:Q")
                st.altair_chart((ch + sub).properties(height=140), width="stretch")
            st.caption("Dashed amber line = substrate position.")
            if shape_map:
                st.subheader("Triangle to hexagon shape vs position " + SYN)
                vals = dict(r["values"])
                T = st.slider("Sulfur boat temperature [C]", 100.0, 300.0, float(vals["T_boat_S_C"]), 5.0)
                vals["T_boat_S_C"] = T
                m = cached_map(tuple(sorted(vals.items())), 30)
                d = pd.DataFrame({"x_cm": m["x_cm"], "s": m["shape_index"], "p05": m["p05"], "p95": m["p95"]})
                band = alt.Chart(d).mark_area(opacity=0.25, color=BLUE).encode(x="x_cm:Q", y=alt.Y("p05:Q", title="shape index"), y2="p95:Q")
                line = alt.Chart(d).mark_line(color=BLUE, strokeWidth=2).encode(x="x_cm:Q", y="s:Q")
                st.altair_chart((band + line).properties(height=180), width="stretch")
                st.caption(f"Boundary {m['boundary_cm_from_boat']:.1f} cm from the MoO3 boat; band = p05..p95 over parameter sigma. Kinetic rates are synthetic and were tuned so the default spans all shape classes: trend direction only, not a prediction. The band spans nearly the full shape range because the placeholder uncertainties are large.")
                if knob_sensitivity:
                    ks = pd.DataFrame(knob_sensitivity(vals))
                    ks["boundary moves (cm per step)"] = ks["shift_cm"].where(ks["valid"], float("nan")) if "valid" in ks else ks["shift_cm"]
                    show_df(st, ks[["knob", "step", "boundary moves (cm per step)"]], hide_index=True)
        elif vessel == "flask":
            st.subheader("Villermaux-Dushman Xs vs stir rate " + SYN)
            v0 = r["values"]["stir_rpm"]
            xs = tuple(round(v0 * f, 1) for f in (0.25, 0.4, 0.6, 0.8, 1, 1.25, 1.6, 2, 3))
            xs = tuple(x for x in xs if x >= next(d["lo"] for d in sch if d["name"] == "stir_rpm"))
            st.line_chart(sweep(vessel, tuple(sorted(r["values"].items())), "stir_rpm", xs, "Xs_villermaux_dushman"), color=BLUE)
        elif vessel == "ampoule":
            st.subheader("Transport rate vs tilt " + SYN)
            xs = (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0)
            st.line_chart(sweep(vessel, tuple(sorted(r["values"].items())), "tilt_deg", xs, "transport_rate_mmol_h"), color=BLUE)
        elif vessel == "sorbent" and pf:
            st.subheader("Breakthrough curve")
            st.line_chart(pd.DataFrame({"t_min": pf["t_min"], "c/c0": pf["c_out_over_c0"]}).set_index("t_min"), color=BLUE)
        if vessel not in ("cvd_tube",):  # generic: any plots a vessel declares in extras (photoreactor sensitivity, Track E plots)
            if r.get("extras"):
                st.subheader("Model-declared plots")
            render_extras(st, r)

if render_brief:
    with tabs["Brief"]:
        render_brief(st, vessel, r["values"])

if render_trace:
    with tabs["Reasoning trace"]:
        render_trace(st)

with tabs["Vessel view"]: __import__("app.vessel_view", fromlist=["render"]).render(st, vessel, r, tier)  # Track H hook
with tabs["Furnace and flow"]: __import__("app.furnace_view", fromlist=["render"]).render(st, vessel, r, tier)  # Track O hook

# ---------------- credibility
with tab_cred:
    f = ROOT / "cache" / "harness.json"
    if not f.exists():  # fresh clone: fall back to the committed snapshot
        f = ROOT / "docs" / "harness_snapshot.json"
        if f.exists():
            st.caption("Showing committed snapshot docs/harness_snapshot.json; `make test` writes a fresh cache/harness.json.")
    if not f.exists():
        st.warning("No cache/harness.json: run `make test`. Nothing is shown as passing without a test.")
    else:
        h = pd.DataFrame(json.loads(f.read_text()))
        h["check"] = h.get("check", pd.Series(dtype=str)).fillna("-")
        npass = int((h.outcome == "passed").sum())
        st.metric("Last `make test`", f"{npass} / {len(h)} passed", "all green" if npass == len(h) else f"{len(h) - npass} not passing", delta_color="off")
        st.caption("Read from cache/harness.json (written by pytest). Re-run `make test` to refresh.")
        h["ok"] = h.outcome.map(lambda o: "PASS" if o == "passed" else "FAIL")
        piv = h.pivot_table(index="vessel", columns="check", values="ok", aggfunc=lambda s: "FAIL" if "FAIL" in set(s) else f"PASS x{len(s)}", fill_value="")
        show_df(st, piv)
        show_df(st, h[["vessel", "check", "test", "ok", "duration"]].sort_values(["ok", "vessel"], ascending=[False, True]), hide_index=True)
