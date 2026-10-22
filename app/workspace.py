"""Workspace page: pick a vessel, set a few key controls, see results recompute live (Tier 1, cached).
Everything else is under 'Advanced parameters'. Offline: Tier 1 models + stored CFD + stored traces. No keys.
Usage: from app.workspace import render; render()"""
import html, json, pathlib, shutil, time
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
FIDELITY = ["Live model", "Stored CFD"]
CFD_VESSELS = ("cvd_tube", "ampoule", "flask")
CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}  # interactive: hover, zoom, pan, download

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


@st.cache_data(show_spinner="Solving (cached afterwards)...", max_entries=48)
def solve_live(vessel, ov_items, extras=False):
    n = K.N_MC.get(vessel, 12)
    t0 = time.perf_counter()
    r = api.solve(vessel, dict(ov_items), n_mc=n, seed=0, extras=extras)
    r = json.loads(json.dumps(r, default=float))
    r["_solve_s"] = time.perf_counter() - t0  # kept in the cache so a cached hit can still report the real solve time
    return r


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


@st.cache_data(show_spinner="Testing each knob (slow vessels take about 20 s, then cached)...", max_entries=24)
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
    p = presets(vessel).get(ss[f"wk_preset:{vessel}"] or "Defaults", {})
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


# ---------------- vessel picker
def _pick(key):
    st.session_state["wk_vessel"] = st.session_state["vt_vessel"] = key


def _picker(vessel):
    with st.container(key="vpick"):
        cols = st.columns(len(VESSELS), gap="small")
        for col, v in zip(cols, VESSELS):
            with col, st.container(key=f"vp_{v}" + ("__sel" if v == vessel else "")):
                st.markdown(KIT.vessel_card(v, K.TITLES[v]), unsafe_allow_html=True)
                st.button(f"Select {K.TITLES[v]}", key=f"wk_pick_{v}", on_click=_pick, args=(v,))


# ---------------- knobs
def _preset_vals(vessel):
    p = presets(vessel).get(st.session_state.get(f"wk_preset:{vessel}") or "Defaults", {})
    d = api.defaults(vessel)
    return {c["name"]: p.get(c["name"], d[c["name"]]) for c in K.KEY_CONTROLS[vessel]}


def _reset(k, v):
    st.session_state[k] = v


def _vtext(d, x):
    return x if isinstance(x, str) else f"{x:g} {d['unit']}".strip()


def _control(vessel, c, d, eff, base):
    ss, k = st.session_state, _ck(vessel, c["name"])
    ss.setdefault(k, d["default"])
    x = ss[k]
    nm = c["name"].replace(".", "_")
    with st.container(key=f"kn_{vessel}_{nm}"):
        hc = st.columns([14, 1], vertical_alignment="center")
        hc[0].markdown(f'<div title="{html.escape(c["help"])}">' + KIT.knob_head(c["label"], d["unit"], c["name"], _vtext(d, x)) + "</div>", unsafe_allow_html=True)
        if x != base:
            with hc[1].container(key=f"rs_{vessel}_{nm}"):
                st.button("↺", key=f"wk_rs:{vessel}:{c['name']}", on_click=_reset, args=(k, base), help="Reset to the preset value")
        if "select" in c:
            v = st.selectbox(c["label"], list(d["choices"]), key=k, label_visibility="collapsed")
        elif c["log"]:
            v = st.select_slider(c["label"], K.options(c, x), key=k, format_func=lambda v: f"{v:g}", label_visibility="collapsed")
        else:
            lo, hi = min(c["lo"], x), max(c["hi"], x)  # a preset value outside the usual range stays reachable
            isint = isinstance(d["default"], int) and not isinstance(d["default"], bool)
            v = st.slider(c["label"], type(x)(lo) if isint else float(lo), type(x)(hi) if isint else float(hi), key=k,
                          step=type(x)(c["step"]) if isint else float(c["step"]), label_visibility="collapsed")
        if eff and c["name"] in eff:
            top = max(abs(e) for e in eff.values()) or 1
            st.markdown(KIT.effect_bar(abs(eff[c["name"]]) / top, eff[c["name"]], SHORT[vessel]), unsafe_allow_html=True)
    return v


def _knob_grid(vessel, sch, eff):
    base = _preset_vals(vessel)
    vals = {}
    for i, c in enumerate(K.KEY_CONTROLS[vessel]):
        if i % 2 == 0:  # one column pair per row, so the stacked mobile order stays row by row
            cols = st.columns(2, gap="medium")
        with cols[i % 2]:
            vals[c["name"]] = _control(vessel, c, sch[c["name"]], eff, base[c["name"]])
    return vals


def _adv_values(vessel):
    """Advanced overrides as of this run: stored dict, overlaid by the advanced widgets that exist (needed because the hero renders before them)."""
    ss, d = st.session_state, api.defaults(vessel)
    adv = _adv(vessel)
    for k in [k for k in ss if isinstance(k, str) and k.startswith(f"wka:{vessel}:")]:
        n = k.split(":", 2)[2]
        if n in d:
            adv.pop(n, None) if ss[k] == d[n] else adv.__setitem__(n, ss[k])
    return adv


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


# ---------------- LLM card
def _reader():
    """(chat or None, badge html). Offline rules reader unless LLM settings are configured."""
    try:
        from app.llm_settings import get_chat, active
        chat = get_chat()
        if chat is not None:
            return chat, f'<span class="wk-badge">LLM: {html.escape(active())}</span>'
    except Exception:  # noqa: BLE001
        pass
    return None, '<span class="wk-badge g">Offline rules reader (no LLM configured)</span>'


def _paste(vessel):
    ss = st.session_state
    with st.container(key="wk_paste"):
        chat, badge = _reader()
        st.markdown('<div style="display:flex;justify-content:space-between;align-items:center;gap:.5rem;flex-wrap:wrap">'
                    f'<span class="wk-h" style="margin:0">Paste a procedure</span>{ss.get(f"wk_used:{vessel}") or badge}</div>', unsafe_allow_html=True)
        txt = st.text_area("Procedure", key=f"wk_text:{vessel}", height=96, label_visibility="collapsed",
                           placeholder="Paste a synthesis procedure. Stated values fill the controls below.")
        b = st.columns([1, 1.25, .6])
        read = b[0].button("Read with LLM", key=f"wk_fill:{vessel}", type="primary", use_container_width=True)
        if b[1].button("Open the agent Studio", key=f"wk_studio:{vessel}", use_container_width=True):
            try:
                from app.theme import go_to
                go_to("Studio", vt_vessel=vessel)
            except Exception:  # noqa: BLE001
                st.caption("Studio page is not available in this build.")
        if read and txt.strip():
            _read_text(vessel, txt, chat)
        chips = ss.get(f"wk_chips:{vessel}")
        if chips:
            st.markdown("".join(chips), unsafe_allow_html=True)
            st.markdown('<span class="wk-chip stated">stated</span><span class="wk-chip default">default</span><span class="wk-chip missing">missing</span>', unsafe_allow_html=True)
            info("stated = found in your text (with the exact words as evidence). default = the model's own value. missing = not found. Stated values were applied to the controls.")


def _read_text(vessel, txt, chat):
    from llm.extract import extract, llm_backend
    ss = st.session_state
    try:
        spec = extract(txt, vessel, (lambda t, v: llm_backend(t, v, chat)) if chat else "rules")
    except Exception as e:  # noqa: BLE001
        return st.error(f"Could not read the text: {e}")
    keys = {c["name"] for c in K.KEY_CONTROLS[vessel]}
    sch = {d["name"]: d for d in api.schema(vessel)}
    chips = []
    for k, f in spec.params.items():
        st_ = f.status.value
        if k not in sch or (k not in keys and st_ != "stated"):
            continue
        if st_ == "stated" and f.value is not None:
            ch = sch[k].get("choices")
            if k in keys and (not ch or f.value in ch):
                ss[_ck(vessel, k)] = f.value
            elif k not in keys:
                _adv(vessel)[k] = f.value
                ss.pop(f"wka:{vessel}:{k}", None)
        val = "" if f.value is None else (f"{f.value:g}" if isinstance(f.value, (int, float)) else str(f.value))
        chips.append(f'<span class="wk-chip {st_}">{html.escape(sch[k]["label"])} <small>{html.escape(val)} {html.escape(sch[k]["unit"] or "")}</small></span>')
    ss[f"wk_chips:{vessel}"] = chips
    ss[f"wk_used:{vessel}"] = '<span class="wk-badge">Read by the LLM</span>' if chat else '<span class="wk-badge g">Read by the offline rules reader</span>'
    st.rerun()


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


def _kpis(vessel, res, base):
    kind = "synthetic" if res["passport"]["synthetic"] else "model"
    items = []
    for label, key, unit, scale in K.TILES[vessel]:
        p = res["passport"]["derived"].get(key, {}).get("p50")
        a = base["passport"]["derived"].get(key, {}).get("p50") if base else None
        dl = None if not a or p is None or abs(p - a) <= 1e-9 * abs(a) else 100 * (p - a) / abs(a)
        items.append((label, _fmt(None if p is None else p * scale), unit, kind, dl))
    st.markdown(KIT.kpis(items), unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:.72rem;color:#6B7A90">{KIT.status_legend()}</div>', unsafe_allow_html=True)


KNOB_INFO = ("Bars: change in the result for one small step of each knob. Whiskers: the same change at the 5th and 95th percentile of the parameter uncertainty. One knob at a time, no interactions.")
CALC_INFO = "Ranked by how much each uncertain input moves the result, per unit of calculation cost. Cost classes: cheap, medium, expensive."


def _knobs(vessel, ov_items):
    st.markdown(f"#### What matters most{_ii(KNOB_INFO)}", unsafe_allow_html=True)
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
    st.markdown(f'<div class="wk-card" style="font-weight:700;color:#0B1F44">Change {html.escape(rows[0]["name"].split(" (")[0])} first.</div>', unsafe_allow_html=True)


def _photo_sens(res):
    ex = res.get("extras") or {}
    sens = ex.get("sensitivity")
    if not sens:
        return st.caption("No sensitivity data for this setup.")
    import plotly.graph_objects as go
    r = sorted(sens.items(), key=lambda kv: abs(kv[1]["dln_rate_per_sigma"]))
    lab = {d["name"]: d["label"] for d in api.schema("photoreactor")}
    fig = go.Figure(go.Bar(y=[lab.get(k, k) for k, _ in r], x=[v["dln_rate_per_sigma"] for _, v in r], orientation="h", marker_color=KIT.BLUE,
                           hovertemplate="%{y}<br>change in ln(rate) per 1 sigma: %{x:.3g}<extra></extra>"))
    fig.update_layout(height=60 + 30 * len(r), margin=dict(l=0, r=10, t=10, b=30), xaxis_title="Change in ln(rate) for a 1-sigma move of the input")
    st.plotly_chart(fig, width="stretch", config=CFG)
    info("Each bar: how much the reaction rate changes when that input moves by one standard deviation of its uncertainty. Elasticity (local power-law exponent) is in the stored extras.")


def _calcs(vessel, ov_items):
    from app import home
    if vessel == "photoreactor":
        st.caption("No atomistic parameter is ranked for the photoreactor yet. Sensitivity by knob instead:")
        try:
            return _photo_sens(solve_live(vessel, ov_items, True))
        except Exception as e:  # noqa: BLE001
            return st.caption(f"Sensitivity unavailable ({e}).")
    st.markdown(f"#### What to calculate next{_ii(CALC_INFO)}", unsafe_allow_html=True)
    with st.spinner("Ranking calculations..."):
        calcs = ranked_calcs(vessel, ov_items)
    if not calcs:
        return st.caption("No atomistic calculation maps to this setup.")
    cols = st.columns(3, gap="medium")
    for col, c in zip(cols, calcs[:3]):
        color, sym = KIT.COST[c["cost"]]
        col.markdown(f'<div class="wk-card wk-rank"><div class="r">{c["rank"]}</div><div><div class="t">{html.escape(home.plain(c["calc"]))}</div>'
                     f'<div class="s">{html.escape(c["label"].split(" (")[0])} moves the {SHORT[vessel]} by {_fmt(c["delta"])} {c["outcome_unit"]}.</div>'
                     f'<span class="wk-badge {"o" if c["cost"] != "cheap" else ""}">{c["cost"]} {sym}</span></div></div>', unsafe_allow_html=True)


def _trust(vessel, res):
    from app.trace_tab import COL, GLYPH
    from app import home
    lab = setup_label(vessel, res)
    n = trust_counts()
    st.markdown("#### How far to trust this" + _ii(f"Across all stored reasoning traces: {n['benchmarked']} benchmarked, {n['uncertain']} uncertain, {n['hypothesis']} hypothesis claims. "
                f"{home.COPY['trust.sentence']} Labels only go down with weaker evidence, never up."), unsafe_allow_html=True)
    order = ("benchmarked", "uncertain", "hypothesis")
    sent = {"hypothesis": "Treat as a hypothesis: inputs are defaults or placeholders, so read trends, not absolute numbers.",
            "uncertain": "Some support exists, but a flag applies; check before relying on it.",
            "benchmarked": "This comparison passed a held-out benchmark."}[lab]
    st.markdown('<div class="wk-card">' + KIT.wk_meter([(l, n[l], {"benchmarked": KIT.WB, "uncertain": "#7FB0F0", "hypothesis": KIT.WO}[l]) for l in order])
                + f'<div style="margin-top:.5rem"><span class="wk-badge {"o" if lab == "hypothesis" else ""}">{lab}</span> {sent}</div></div>', unsafe_allow_html=True)


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


LLM_INFO = ("The language model only reads text and explains results. Every number comes from the physics tools: extracted values must quote your text, "
            "and the explanation may cite tool outputs only. Without an LLM configured, a rule-based reader does the first step and the recorded runs in Studio replay offline.")
TIER1_DEF = "Fast physics model: recomputes as you move a slider, with uncertainty bands."


def _tier1_info(vessel):
    return (f"Solves reduced-order balances for this vessel (closed-form and 1-D transport, kinetics and heat terms), not a 3-D flow field. "
            f"Every update draws {K.N_MC.get(vessel, 12)} Monte Carlo samples of the uncertain inputs, which gives the p05 to p95 bands. "
            f"Typical time: well under a second for most vessels, several seconds for the sorbent bed. "
            f"Not captured: 3-D flow structure, turbulence detail, surface chemistry and anything outside the stated parameter ranges. Use Stored CFD for flow fields.")


def _pick_preset(vessel, ps):
    pk = f"wk_preset:{vessel}"
    st.session_state.setdefault(pk, "Defaults")
    if st.session_state[pk] not in ps:
        st.session_state[pk] = "Defaults"
    st.pills("Starting point", list(ps), key=pk, on_change=_apply_preset, args=(vessel,), label_visibility="collapsed",
             help="Named starting points. They set the controls and any advanced values they carry.")
    if st.session_state[pk] is None:
        st.session_state[pk] = "Defaults"


def _effects(vessel, base_items):
    """knob -> signed effect, measured around the preset (stable while you drag, so cached). Slow vessels only after the opt-in toggle."""
    if vessel in SLOW and not st.session_state.get(f"wk_deep:{vessel}"):
        return {}
    try:
        return {r["knob"]: r["effect"] for r in knob_effects(vessel, base_items)}
    except Exception:  # noqa: BLE001
        return {}


def render():
    ss = st.session_state
    try:
        from app import llm_settings
        llm_settings.render()
    except Exception:  # noqa: BLE001
        pass
    if ss.get("wk_vessel") not in VESSELS:
        ss["wk_vessel"] = ss.get("vt_vessel") if ss.get("vt_vessel") in VESSELS else VESSELS[0]
    vessel = ss["vt_vessel"] = ss["wk_vessel"]
    st.markdown(KIT.WS_CSS, unsafe_allow_html=True)
    _picker(vessel)

    sch = {d["name"]: d for d in api.schema(vessel)}
    # state first: the hero and KPIs render above the knobs, so everything is read from session state (widgets update it before the run)
    pk = f"wk_preset:{vessel}"
    ss.setdefault(pk, "Defaults")
    dflt = api.defaults(vessel)
    for c in K.KEY_CONTROLS[vessel]:
        ss.setdefault(_ck(vessel, c["name"]), dflt[c["name"]])
    vals, adv = current_values(vessel), _adv_values(vessel)
    ov_items = tuple(sorted(overrides(vessel, vals, adv).items()))
    pr = presets(vessel).get(ss[pk] or "Defaults", {})
    base_items = tuple(sorted({k: v for k, v in pr.items() if dflt.get(k) != v}.items()))

    # LLM role + paste card
    left, right = st.columns([3, 2], gap="medium", vertical_alignment="center")
    with left:
        _paste(vessel)
    with right:
        st.markdown(f'<div class="wk-h">How the LLM is used{_ii(LLM_INFO)}</div>' + KIT.llm_strip(), unsafe_allow_html=True)


    # fidelity + tier strip
    t_l, t_r = st.columns([5, 2], gap="medium", vertical_alignment="center")
    with t_r:
        fid = st.segmented_control("Model fidelity", FIDELITY, default=FIDELITY[0], key="wk_fid", label_visibility="collapsed") or FIDELITY[0]
    t0 = time.perf_counter()
    try:
        res = solve_live(vessel, ov_items)
    except Exception as e:
        return st.error(f"These settings could not be solved: {e}")
    wall = time.perf_counter() - t0
    try:
        base = solve_live(vessel, base_items)
    except Exception:  # noqa: BLE001
        base = None
    with t_l:
        st.markdown(KIT.tier_strip(2 if fid == FIDELITY[1] else 1), unsafe_allow_html=True)
    ts = res.get("_solve_s", wall)
    badge = f"solved in {ts:.1f} s" if ts >= .05 else "solved in under 0.05 s" + (" (cached)" if wall < 0.05 else "")
    reg = res["regime"].replace("_", " ")
    st.markdown(f'<div class="wk-def"><b style="color:#1F5FBF">Tier 1</b> {TIER1_DEF} {_ii(_tier1_info(vessel))} '
                f'<span class="wk-badge">{badge}</span> <span class="wk-badge g">Tier 0 regime: {html.escape(reg)}</span></div>', unsafe_allow_html=True)

    # hero band
    hl, hr = st.columns([3, 1.15], gap="large")
    with hl:
        if fid == FIDELITY[1]:
            _cfd(vessel, res)
            st.caption("OpenFOAM is installed: run `tier2/run.sh <case_dir>` for a new CFD result. This page shows the stored one." if openfoam_available()
                       else "OpenFOAM is not available here; showing the stored result.")
        else:
            _hero(vessel, res)
    with hr:
        _kpis(vessel, res, base)

    # knobs
    st.markdown('<div class="wk-h" style="margin-top:.6rem">Set up</div>', unsafe_allow_html=True)
    _pick_preset(vessel, presets(vessel))
    if vessel in SLOW:
        st.toggle("Compute knob effects and the ranking (about 20 s, then cached)", key=f"wk_deep:{vessel}")
    _knob_grid(vessel, sch, _effects(vessel, base_items))
    _advanced(vessel)

    # results
    if vessel in SLOW and not ss.get(f"wk_deep:{vessel}"):
        st.caption("Sensitivity is off for this slow vessel until you switch it on above; the numbers still update live.")
    else:
        _knobs(vessel, ov_items)
        _calcs(vessel, ov_items)
    _trust(vessel, res)
    _extra_plots(vessel, res)
    _furnace(vessel, res)
    with st.expander("Literature: where the parameters come from"):
        from app import literature
        literature.render(vessel, pick=False)


def _ii(text):
    if _theme_info is None:
        return ""
    try:
        from app.theme import info_html
        return info_html(text)
    except Exception:  # noqa: BLE001
        return ""
