"""Workspace page: pick a vessel, set a few key controls, see results recompute live (Tier 1, cached).
Everything else is under 'Advanced parameters'. Offline: Tier 1 models + stored CFD + stored traces. No keys.
Usage: from app.workspace import render; render()"""
import html, json, pathlib, shutil
import numpy as np
import streamlit as st
from core import api
from app import controls as K
from app import ui_kit as KIT

ROOT = pathlib.Path(__file__).resolve().parents[1]
VESSELS = list(K.KEY_CONTROLS)
SHORT = {"cvd_tube": "shape boundary", "ampoule": "transport rate", "flask": "mixing-vs-reaction ratio", "sorbent": "breakthrough time",
         "photoreactor": "mixing-vs-light ratio"}
SLOW = ("sorbent",)  # vessels where knob effects + ranking take > 10 s
FIDELITY = ["Tier 1 (live)", "Stored CFD"]
CFD_VESSELS = ("cvd_tube", "ampoule", "flask")
CFG = {"displayModeBar": False}

try:  # Track R figures (agreed signatures); fall back to the existing helpers
    from app.viz import plotly_figs as PF
except ImportError:
    PF = None
try:  # Track P theme helper
    from app.theme import info as _theme_info
except ImportError:
    _theme_info = None


def info(text):
    """Details behind an info icon."""
    if _theme_info is not None:
        return _theme_info(text)
    with st.expander("ⓘ info"):
        st.caption(text)


# ---------------- pure layer (testable without a page)
def presets(vessel):
    """label -> param dict. 'Defaults' first, then preset files, then the built-in tube starting points."""
    out = {"Defaults": {}}
    for p in api.preset_info(vessel):
        out[p["title"]] = p["params"]
    for k, v in K.EXTRA_PRESETS.get(vessel, {}).items():
        out.setdefault(k, v)
    return out


def overrides(vessel, ctl_values, adv):
    """Values that differ from ParamDef defaults (what core.api.solve takes)."""
    d = api.defaults(vessel)
    return {k: v for k, v in (ctl_values | adv).items() if v is not None and d.get(k) != v}


@st.cache_data(show_spinner=False, max_entries=48)
def solve_live(vessel, ov_items, extras=False):
    n = K.N_MC.get(vessel, 12)
    r = api.solve(vessel, dict(ov_items), n_mc=n, seed=0, extras=extras)
    return json.loads(json.dumps(r, default=float))


def _outcome_get(vessel, ov, n_mc):
    """(p05, p50, p95) of the headline output. Tube: shape boundary read off the shape-map band (hypothesis-level model)."""
    from atomistic import ranking as R
    key = R.OUTCOMES[vessel][0]
    if key == "boundary_cm":
        from vessels.cvd_tube.wulff import boundary_cm
        r = api.solve(vessel, ov, n_mc=n_mc, seed=0)
        sm = r["extras"]["shape_map"]
        return tuple(boundary_cm(np.array(sm["x_from_boat_cm"]), np.array(sm[c]), r["values"]["s_boundary"]) for c in ("p05", "shape_index", "p95"))
    d = api.solve(vessel, ov, n_mc=n_mc, seed=0, extras=False)["passport"]["derived"][key]
    return d["p05"], d["p50"], d["p95"]


@st.cache_data(show_spinner=False, max_entries=24)
def knob_effects(vessel, ov_items):
    """Each numeric key control moved down/up by one small step (+-10 %, or +-25 for temperatures), clipped to its range, re-solved.
    effect = change of the headline output; whiskers = same change from p05 / p95. ponytail: one at a time, no interactions."""
    ov, n_mc = dict(ov_items), max(3, K.N_MC.get(vessel, 12) // 3)
    base = _outcome_get(vessel, ov, n_mc)
    if not np.isfinite(base[1]):
        return []
    sch = {d["name"]: d for d in api.schema(vessel)}
    rows = []
    for c in K.KEY_CONTROLS[vessel]:
        d = sch[c["name"]]
        x0 = ov.get(c["name"], d["default"])
        if "select" in c or not isinstance(x0, (int, float)):
            continue
        h = 25.0 if d["unit"] in ("C", "K") else abs(x0) * 0.1
        lo, hi = max(x0 - h, d["lo"]), min(x0 + h, d["hi"])
        if hi <= lo:
            continue
        try:
            a, b = _outcome_get(vessel, ov | {c["name"]: lo}, n_mc), _outcome_get(vessel, ov | {c["name"]: hi}, n_mc)
        except Exception:
            continue
        e = [b[i] - a[i] for i in range(3)]
        if not np.isfinite(e[1]):
            continue
        e = [x if np.isfinite(x) else e[1] for x in e]
        step = "±25 " + d["unit"] if d["unit"] in ("C", "K") else "±10%"
        rows.append({"knob": c["name"], "name": f"{c['label']} ({step})", "effect": e[1], "lo": min(e[0], e[2]), "hi": max(e[0], e[2])})
    return sorted(rows, key=lambda r: -abs(r["effect"]))


@st.cache_data(show_spinner=False, max_entries=24)
def ranked_calcs(vessel, ov_items):
    from atomistic import ranking as R
    seen, out = set(), []
    for c in R.rank_calculations(vessel, dict(ov_items), None, 1, 0):
        if c["calc"] not in seen:
            seen.add(c["calc"])
            out.append({k: c[k] for k in ("rank", "calc", "cost", "param", "label", "sigma", "unit", "delta", "outcome_unit")})
    return out


@st.cache_data(show_spinner=False)
def trust_counts():
    from app import home
    return home.trust_counts()


def setup_label(vessel, res):
    """Weakest evidence wins (llm.trace.cap_of); never upgraded."""
    from llm import trace as T
    ev = [{"kind": "tier_status"}] if vessel == "cvd_tube" else []
    if res["passport"]["synthetic"]:
        ev.append({"kind": "synthetic_model"})
    if any(p in ("default", "synthetic") for p in res["provenance"].values()):
        ev.append({"kind": "paramdef_default"})
    return T.cap_of(ev)


def openfoam_available():
    return shutil.which("blockMesh") is not None or pathlib.Path("/Applications/OpenFOAM-v2512.app").exists()


def _fmt(x):
    return "n/a" if x is None or not np.isfinite(x) else (f"{x:.0f}" if abs(x) >= 100 else f"{x:.2g}" if abs(x) < 0.1 else f"{x:.3g}")


# ---------------- state
def _ck(vessel, name):
    return f"wk:{vessel}:{name}"


def _adv(vessel):
    return st.session_state.setdefault(f"wk_adv:{vessel}", {})


def _apply_preset(vessel):
    ss = st.session_state
    p = presets(vessel).get(ss[f"wk_preset:{vessel}"], {})
    d = api.defaults(vessel)
    keys = {c["name"] for c in K.KEY_CONTROLS[vessel]}
    for n in keys:
        ss[_ck(vessel, n)] = p.get(n, d[n])
    ss[f"wk_adv:{vessel}"] = {k: v for k, v in p.items() if k not in keys}
    for k in [k for k in ss if k.startswith(f"wka:{vessel}:")]:
        del ss[k]


def current_values(vessel):
    ss, d = st.session_state, api.defaults(vessel)
    return {c["name"]: ss.get(_ck(vessel, c["name"]), d[c["name"]]) for c in K.KEY_CONTROLS[vessel]}


# ---------------- controls column
def _control(vessel, c, d):
    ss, k = st.session_state, _ck(vessel, c["name"])
    ss.setdefault(k, d["default"])
    lab = f"{c['label']} ({d['unit']})" if d["unit"] else c["label"]
    if "select" in c:
        ch = list(d["choices"])
        return st.selectbox(lab, ch, key=k, help=c["help"])
    x = ss[k]
    if c["log"]:
        return st.select_slider(lab, K.options(c, x), key=k, help=c["help"], format_func=lambda v: f"{v:g}")
    lo, hi = min(c["lo"], x), max(c["hi"], x)  # a preset value outside the usual range stays reachable
    isint = isinstance(d["default"], int) and not isinstance(d["default"], bool)
    return st.slider(lab, type(x)(lo) if isint else float(lo), type(x)(hi) if isint else float(hi), key=k, step=type(x)(c["step"]) if isint else float(c["step"]), help=c["help"])


def _advanced(vessel):
    sch = [d for d in api.schema(vessel) if d["name"] not in {c["name"] for c in K.KEY_CONTROLS[vessel]}]
    groups = list(dict.fromkeys(d["group"] for d in sch))
    adv = _adv(vessel)
    with st.expander("Advanced parameters"):
        st.caption(f"{len(adv)} changed. Sorted by group; changes recompute the results.")
        g = st.radio("Group", groups, horizontal=True, key=f"wk_grp:{vessel}", label_visibility="collapsed")
        for d in [d for d in sch if d["group"] == g]:
            n, cur = d["name"], adv.get(d["name"], d["default"])
            lab = f"{d['label']} ({d['unit']})" if d["unit"] else d["label"]
            hlp = f"{d['help']} Range {d['lo']} to {d['hi']}. Source: {d['source']}."
            k = f"wka:{vessel}:{n}"
            if d["choices"]:
                v = st.selectbox(lab, list(d["choices"]), index=list(d["choices"]).index(cur), key=k, help=hlp)
            elif isinstance(d["default"], int) and not isinstance(d["default"], bool):
                v = st.number_input(lab, int(d["lo"]), int(d["hi"]), int(cur), key=k, help=hlp)
            else:
                v = st.number_input(lab, float(d["lo"]), float(d["hi"]), float(cur), format="%.4g", key=k, help=hlp)
            if v != cur:
                adv[n] = v
            if adv.get(n) == d["default"]:
                adv.pop(n, None)
    return adv


def _paste(vessel):
    with st.expander("Paste a procedure (optional)"):
        txt = st.text_area("Procedure", key=f"wk_text:{vessel}", height=110, label_visibility="collapsed",
                           placeholder="Paste a synthesis procedure; stated values fill the controls.")
        if st.button("Fill controls from text", key=f"wk_fill:{vessel}") and txt.strip():
            from llm.extract import extract, llm_backend
            chat = None
            try:
                from app.llm_settings import get_chat
                chat = get_chat()
            except Exception as e:
                st.warning(f"LLM settings not usable ({e}); using the offline reader.")
            try:
                spec = extract(txt, vessel, (lambda t, v: llm_backend(t, v, chat)) if chat else "rules")
            except Exception as e:
                return st.error(f"Could not read the text: {e}")
            keys = {c["name"] for c in K.KEY_CONTROLS[vessel]}
            sch = {d["name"]: d for d in api.schema(vessel)}
            n = 0
            for k, f in spec.params.items():
                if f.status.value == "stated" and k in sch and f.value is not None:
                    if k in keys:
                        st.session_state[_ck(vessel, k)] = f.value
                    else:
                        _adv(vessel)[k] = f.value
                        st.session_state.pop(f"wka:{vessel}:{k}", None)
                    n += 1
            st.session_state[f"wk_filled:{vessel}"] = n
            st.rerun()
        if (n := st.session_state.get(f"wk_filled:{vessel}")) is not None:
            st.caption(f"{n} stated value(s) filled in. Everything else keeps its default.")


# ---------------- results column
def _hero(vessel, res):
    try:
        if PF is not None:
            st.plotly_chart(PF.vessel_hero(vessel, res, None, height=380), width="stretch", config=CFG)
        else:
            from app.vessel_view import render_vessel_hero
            render_vessel_hero(res, vessel, None, height=380)
    except Exception as e:
        st.caption(f"Vessel figure unavailable ({e}). Numbers below are unchanged.")


def _cfd(vessel, res):
    if vessel not in CFD_VESSELS:
        st.info("No stored CFD for this vessel. Showing the Tier 1 model.")
        return _hero(vessel, res)
    from app.viz import fields
    metas = fields.available(vessel)
    if not metas:
        st.info("No stored CFD result found. Showing the Tier 1 model.")
        return _hero(vessel, res)
    i = fields.nearest(metas, res["values"], vessel)
    m = metas[i]
    names = list(m["fields"])
    fld = st.radio("Field", names, horizontal=True, key=f"wk_field:{vessel}", format_func=lambda f: m["fields"][f]["label"]) if len(names) > 1 else names[0]
    fig = None
    try:
        if PF is not None:
            fig = PF.cfd_field(vessel, fld, m["name"])
        if fig is None:
            from app.vessel_view import UNITS, _field
            xu, yu, xs, ys = UNITS.get(vessel, ("mm", "mm", 1000.0, 1000.0))
            fig = _field(m["name"], fld, fld in ("speed", "T"), xs, ys, xu, yu, 380, vessel != "cvd_tube")
        st.plotly_chart(fig, width="stretch", config=CFG)
    except Exception as e:
        st.caption(f"Field could not be drawn ({e}).")
    st.markdown(f"**Stored CFD result, not re-run.** Case: `{m['case']}`")
    diff = fields.differences(m, res["values"], vessel)
    if diff:
        st.warning("The stored case used different inputs than your controls: " + "; ".join(diff[:4]))


def _tiles(vessel, res):
    kind = "synthetic" if res["passport"]["synthetic"] else "model"
    items = []
    for label, key, unit, scale in K.TILES[vessel]:
        p = res["passport"]["derived"].get(key, {}).get("p50")
        items.append((label, _fmt(None if p is None else p * scale), unit, kind))
    st.markdown(KIT.tiles(items), unsafe_allow_html=True)
    st.caption(f"Regime: {res['regime'].replace('_', ' ')}  |  {KIT.status_legend()}", unsafe_allow_html=True)


def _knobs(vessel, ov_items):
    st.markdown("#### What matters most")
    with st.spinner("Testing each knob..."):
        rows = knob_effects(vessel, ov_items)
    if not rows:
        return st.caption("No knob moves the headline result here.")
    from atomistic import ranking as R
    unit = R.OUTCOMES[vessel][2]
    fig = None
    try:
        if PF is not None:
            fig = PF.knob_bars(rows)
    except Exception:
        fig = None
    if fig is None:
        import plotly.graph_objects as go
        r = rows[:6][::-1]
        fig = go.Figure(go.Bar(y=[x["name"] for x in r], x=[x["effect"] for x in r], orientation="h", marker_color=[KIT.BLUE if x["effect"] >= 0 else KIT.VERM for x in r],
                               error_x=dict(type="data", symmetric=False, array=[x["hi"] - x["effect"] for x in r], arrayminus=[x["effect"] - x["lo"] for x in r]),
                               hovertemplate="%{y}<br>change %{x:.3g}<extra></extra>"))
        fig.update_layout(height=60 + 42 * len(r), margin=dict(l=0, r=10, t=10, b=30), xaxis_title=f"Change in {SHORT[vessel]}" + (f" ({unit})" if unit else ""))
    st.plotly_chart(fig, width="stretch", config=CFG)
    st.markdown(f'<div class="vt-take">Change {html.escape(rows[0]["name"].split(" (")[0].lower())} first.</div>', unsafe_allow_html=True)
    info("Bars: change in the result for one small step of each knob. Whiskers: the same change at the 5th and 95th percentile of the parameter uncertainty. One knob at a time, no interactions.")


def _calcs(vessel, ov_items):
    from app import home
    st.markdown("#### What to calculate next")
    with st.spinner("Ranking calculations..."):
        calcs = ranked_calcs(vessel, ov_items)
    if not calcs:
        return st.caption("No atomistic calculation maps to this setup.")
    for c in calcs[:3]:
        col = st.columns([1, 6, 3])
        col[0].markdown(KIT.rank_dot(c["rank"]), unsafe_allow_html=True)
        col[1].markdown(f"**{html.escape(home.plain(c['calc']))}**  \n{html.escape(c['label'].split(' (')[0])} moves the {SHORT[vessel]} by {_fmt(c['delta'])} {c['outcome_unit']}.")
        color, sym = KIT.COST[c["cost"]]
        col[2].markdown(KIT.badge(f"{c['cost']} {sym}", color), unsafe_allow_html=True)
    info("Ranked by how much each uncertain input moves the result, per unit of calculation cost. Cost classes: cheap, medium, expensive.")


def _trust(vessel, res):
    from app.trace_tab import COL, GLYPH
    st.markdown("#### How far to trust this")
    lab = setup_label(vessel, res)
    n = trust_counts()
    order = ("benchmarked", "uncertain", "hypothesis")
    st.markdown(KIT.meter([(l, n[l], COL[l]) for l in order]), unsafe_allow_html=True)
    sent = {"hypothesis": "Treat as a hypothesis: inputs are defaults or placeholders, so read trends, not absolute numbers.",
            "uncertain": "Some support exists, but a flag applies; check before relying on it.",
            "benchmarked": "This comparison passed a held-out benchmark."}[lab]
    st.markdown(f'This setup: {KIT.badge(lab, COL[lab], GLYPH[lab])} {sent}', unsafe_allow_html=True)
    from app import home
    info(f"Across all stored reasoning traces: {n['benchmarked']} benchmarked, {n['uncertain']} uncertain, {n['hypothesis']} hypothesis claims. "
         f"{home.COPY['trust.sentence']} Labels only go down with weaker evidence, never up.")


def _extra_plots(vessel, res, spec=None):
    if PF is None:
        return
    try:
        figs = PF.profiles(vessel, res, spec)
    except Exception:
        figs = []
    if figs:
        with st.expander("More plots"):
            for title, f in figs:
                st.markdown(f"**{title}**")
                st.plotly_chart(f, width="stretch", config=CFG)


def _furnace(vessel, res):
    if vessel != "cvd_tube":
        return
    st.divider()
    st.markdown("#### Furnace and flow")
    if st.toggle("Show furnace and flow (about 1 s)", key="wk_furnace"):
        try:
            from app.furnace_view import render as furnace_render
            furnace_render(st, vessel, res, 1)
        except Exception as e:
            st.error(f"Furnace view failed: {e}")


# ---------------- page
def render():
    ss = st.session_state
    if "wk_vessel" not in ss:
        ss["wk_vessel"] = ss.get("vt_vessel") if ss.get("vt_vessel") in VESSELS else VESSELS[0]
    st.markdown(KIT.CSS, unsafe_allow_html=True)
    vessel = st.radio("Vessel", VESSELS, horizontal=True, key="wk_vessel", format_func=K.TITLES.get)
    ss["vt_vessel"] = vessel
    left, right = st.columns([2, 3], gap="large")
    sch = {d["name"]: d for d in api.schema(vessel)}
    with left:
        st.markdown("#### Set up")
        pk = f"wk_preset:{vessel}"
        ps = presets(vessel)
        st.selectbox("Starting point", list(ps), key=pk, on_change=_apply_preset, args=(vessel,), help="Named presets; they set the controls and any advanced values they carry.")
        vals = {c["name"]: _control(vessel, c, sch[c["name"]]) for c in K.KEY_CONTROLS[vessel]}
        adv = _advanced(vessel)
        _paste(vessel)
    ov = overrides(vessel, vals, adv)
    ov_items = tuple(sorted(ov.items()))
    with right:
        fid = st.radio("Model fidelity", FIDELITY, horizontal=True, key="wk_fid",
                       help="Tier 1: reduced-order model, recomputed live. Stored CFD: a saved OpenFOAM result, never re-run here.")
        try:
            res = solve_live(vessel, ov_items)
        except Exception as e:
            return st.error(f"These settings could not be solved: {e}")
        if fid == FIDELITY[1]:
            _cfd(vessel, res)
            if openfoam_available():
                st.caption("OpenFOAM is installed on this machine: run `tier2/run.sh <case_dir>` to make a new CFD result. This page shows the stored one.")
            else:
                st.caption("OpenFOAM is not available here; showing the stored result.")
        else:
            _hero(vessel, res)
        _tiles(vessel, res)
        if vessel in SLOW and not st.toggle("Show what matters and what to calculate (slow, about 20 s)", key=f"wk_deep:{vessel}"):
            st.caption("Sensitivity and calculation ranking are off for this slow vessel; the numbers above still update live.")
        else:
            _knobs(vessel, ov_items)
            _calcs(vessel, ov_items)
        _trust(vessel, res)
        _extra_plots(vessel, res)
    _furnace(vessel, res)
