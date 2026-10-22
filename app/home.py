"""Home: a 60-90 s guided story (Procedure, Vessel, What matters, What to calculate, How far to trust).
Offline: rules extractor + Tier 1 models + stored traces. No LLM, no network. Every label comes from llm.trace; nothing is upgraded.
Usage: from app.home import render; render()"""
import html, json, pathlib, re
import numpy as np
from core import api
from llm import trace as T
from atomistic import ranking as R
from app import ui_kit as K

ROOT = pathlib.Path(__file__).resolve().parents[1]
STEPS = ["Procedure", "Vessel", "What matters", "What to calculate", "How far to trust"]

# all fixed on-screen words live here so tests can check the length limits (titles <= 6 words, captions <= 14, paragraphs <= 30)
COPY = {
    "title.name": "VesselTwin",
    "cap.pitch": "From lab procedure to the one experiment and calculation that matter.",
    "badge.honesty": "Research prototype: numbers are model estimates",
    "title.1": "Pick your procedure",
    "title.2": "Your vessel, in numbers",
    "title.3": "What matters most",
    "title.4": "What to calculate next",
    "title.5": "How far to trust this",
    "cap.chips": "Blue: in your text. Orange: default. Pink: missing.",
    "cap.chips2": "Defaults and missing values are placeholders, not facts.",
    "cap.tiles": "Blue dot: model estimate. Orange: synthetic inputs. Green: CFD.",
    "cap.knobs": "Bars: change in the result for one small step of each knob.",
    "cap.whisk": "Whiskers: the same change at the 5th and 95th percentile.",
    "cap.calcs": "Ranked by how much each uncertainty moves the result.",
    "cap.trust": "Labels only go down with weaker evidence, never up.",
    "trust.sentence": "Sensitivity direction: model 2/8, blind guess 6/8. Shape class: no better than baseline. CFD verification targets: missed.",
    "cap.nocalc": "No atomistic calculation maps to this setup.",
    "btn.read": "Read procedure", "btn.next": "Next", "btn.back": "Back", "btn.reason": "See the reasoning",
    "cap.reason": "Opens the Advanced tab; pick Reasoning trace.",
}
SCENARIOS = {
    "cvd_tube": dict(title="MoS2 CVD tube", cap="Flagship: grow a monolayer in a furnace", file="real_01_cvd_tube", proxy=("boundary_cm", "shape boundary position", "cm"),
                     short="shape boundary"),
    "ampoule": dict(title="Sealed ampoule", cap="Crystal growth by vapour transport", file="real_14_ampoule", proxy=("transport_rate_mmol_h", "transport rate", "mmol/h"),
                    short="transport rate"),
    "sorbent": dict(title="Sorbent bed", cap="CO2 capture in a packed column", file="real_29_sorbent", proxy=("t_break5_min", "breakthrough time", "min"),
                    short="breakthrough time"),
}
# knobs an experimentalist can actually turn (the tube list extends llm.trace.KNOBS)
KNOBS = {"cvd_tube": ["flow_sccm", "T_boat_Mo_C", "T_boat_S_C", "T_furnace_C", "boat_area_MoO3_cm2", "x_substrate_cm", "pressure_Pa"],
         "ampoule": ["T_source_C", "T_sink_C", "D_mm", "L_cm", "agent_mg_per_cm3", "tilt_deg"],
         "sorbent": ["T_K", "flow_sccm", "y_feed", "bed_length_cm", "bed_id_cm", "particle_dp_mm", "P_kPa"]}
SNAP = ROOT / "app" / "home_data"  # committed snapshot of the three demo stories (model outputs, regenerate: python -m app.home)
# tiles per vessel: (label, source, key, unit). source: derived (passport p50) | value (input) | regime
TILES = {
    "cvd_tube": [("Gas temperature", "derived", "T_gas_K", "K"), ("Carrier flow", "value", "flow_sccm", "sccm"), ("Flow regime", "regime", "", "")],
    "ampoule": [("Transport rate", "derived", "transport_rate_mmol_h", "mmol/h"), ("Source temperature", "value", "T_source_C", "C"), ("Flow regime", "regime", "", "")],
    "sorbent": [("Breakthrough time", "derived", "t_break5_min", "min"), ("Peak heating", "derived", "dT_peak_K", "K"), ("Flow regime", "regime", "", "")],
}
PLAIN = [("DFT edge energy", "Crystal edge energy"), ("ReaxFF/MLIP attachment barrier", "Atom attachment barrier"), ("MLIP-MD / TST", "Attachment speed"),
         ("MLIP-MD evaporation", "Evaporation and sticking"), ("DFT/JANAF", "Gas thermodynamics"), ("ab initio collision", "Gas diffusion"),
         ("xTB/DFT competing", "Side-reaction barrier"), ("GCMC isotherm", "Adsorption capacity"), ("DFT binding", "Binding strength"),
         ("MLIP-MD pore", "Pore diffusion")]


def words(s):
    return len(re.findall(r"\S+", s))


def plain(calc):
    return next((p for k, p in PLAIN if calc.startswith(k)), calc)


def procedure(vessel):
    return json.loads((ROOT / "bench" / "procedures" / f"{SCENARIOS[vessel]['file']}.json").read_text())["text"]


# ---------------- pure data layer (no streamlit)
NAMES = {"y_feed": "Feed concentration", "T_K": "Bed temperature", "tilt_deg": "Ampoule tilt", "x_substrate_cm": "Substrate position"}


def _short(label, name=None):
    if name in NAMES:
        return NAMES[name]
    s = label.split(" (")[0]
    return s if len(s) <= 30 else s[:29] + "…"


def knob_effects(vessel, values, n_mc=12, seed=0):
    """Each operation/geometry knob moved up and down by one small step (+-10 %, or +-25 for temperatures), clipped to bounds, re-solved.
    Effect = change of the headline output (its own unit); whiskers = same change from p05 / p95. ponytail: one-at-a-time, no interactions."""
    key = SCENARIOS[vessel]["proxy"][0]

    def get(v):  # (p05, p50, p95) of the headline output
        if key == "boundary_cm":  # tube: triangle/hexagon boundary read off the shape-map band (hypothesis-level model)
            from vessels.cvd_tube.wulff import boundary_cm
            r = api.solve(vessel, v, n_mc=n_mc, seed=seed)
            sm, rv = r["extras"]["shape_map"], r["values"]
            return tuple(boundary_cm(np.array(sm["x_from_boat_cm"]), np.array(sm[c]), rv["s_boundary"]) for c in ("p05", "shape_index", "p95"))
        d = api.solve(vessel, v, n_mc=n_mc, seed=seed, extras=False)["passport"]["derived"][key]
        return d["p05"], d["p50"], d["p95"]
    base, rows = get(values), []
    if not np.isfinite(base[1]):
        return rows
    for d in api.schema(vessel):
        x0 = values.get(d["name"], d["default"])
        if d["name"] not in KNOBS[vessel] or d["choices"] or not isinstance(x0, (int, float)) or d["hi"] is None or d["lo"] is None:
            continue
        temp = d["unit"] in ("C", "K")
        h = 25.0 if temp else abs(x0) * 0.1
        lo, hi = max(x0 - h, d["lo"]), min(x0 + h, d["hi"])
        if hi <= lo:
            continue
        a, b = get(values | {d["name"]: lo}), get(values | {d["name"]: hi})
        e = [b[i] - a[i] for i in range(3)]
        if not np.isfinite(e[1]):
            continue
        e = [x if np.isfinite(x) else e[1] for x in e]  # boundary missing on a band edge: whisker collapses to the effect
        step = "±25 " + d["unit"] if temp else "±10%"
        rows.append({"knob": d["name"], "name": f"{_short(d['label'], d['name'])} ({step})", "effect": e[1], "lo": min(e[0], e[2]), "hi": max(e[0], e[2])})
    return sorted(rows, key=lambda r: -abs(r["effect"]))


def _skey(vessel, text):
    import hashlib
    return hashlib.sha1(f"{vessel}|{text}".encode()).hexdigest()[:16]


def build_story(vessel, text, n_mc=12, chat=None):
    """text -> everything the five steps show. The three demo procedures load from the committed snapshot (instant, identical numbers)."""
    f = SNAP / f"{vessel}.json"
    if f.exists() and n_mc == 12 and chat is None:
        d = json.loads(f.read_text())
        if d.get("key") == _skey(vessel, text):
            return d
    return _build(vessel, text, n_mc, chat)


def _build(vessel, text, n_mc, chat=None):
    from llm.extract import extract, llm_backend
    spec = extract(text, vessel, (lambda t, v: llm_backend(t, v, chat)) if chat else "rules")  # chat: the user's own provider from the sidebar; spans are still checked
    res = api.solve(vessel, spec=spec, n_mc=n_mc, extras=False)
    knobs = knob_effects(vessel, res["values"], n_mc=max(4, n_mc // 3))
    seen, calcs = set(), []
    for c in R.rank_calculations(vessel, res["values"], None, 1, 0):  # one card per distinct calculation
        if c["calc"] not in seen:
            seen.add(c["calc"])
            calcs.append(c)
    return {"key": _skey(vessel, text), "vessel": vessel, "spec": spec.model_dump(mode="json"), "res": json.loads(json.dumps(res, default=float)),
            "knobs": knobs, "calcs": [{k: c[k] for k in ("rank", "calc", "cost", "param", "label", "sigma", "unit", "delta", "outcome_unit", "rationale")} for c in calcs]}


def _fmt(x):
    return "n/a" if x is None or not np.isfinite(x) else (f"{x:.0f}" if abs(x) >= 100 else f"{x:.2g}" if abs(x) < 0.1 else f"{x:.3g}")


def tile_items(story):
    res, v = story["res"], story["vessel"]
    kind = "synthetic" if res["passport"]["synthetic"] else "model"
    out = []
    for label, src, key, unit in TILES[v]:
        unit = {"C": "°C"}.get(unit, unit)
        if src == "regime":
            out.append((label, res["regime"].replace("_", " "), "", kind))
        elif src == "derived":
            out.append((label, _fmt(res["passport"]["derived"][key]["p50"]), unit, kind))
        else:
            out.append((label, _fmt(res["values"][key]), unit, kind))
    return out


def highlight(text, spec):
    """Original text with each stated span wrapped in a blue chip; defaults and placeholders listed after as chips. Returns (html, n_stated)."""
    spans = sorted(((text.find(f["span"]), f) for f in spec["params"].values() if f["status"] == "stated" and f["span"] and text.find(f["span"]) >= 0),
                   key=lambda x: x[0])
    names = {d["name"]: d for d in api.schema(spec["vessel"])}
    out, pos = [], 0
    for i, f in spans:
        if i < pos:
            continue
        k = next(k for k, g in spec["params"].items() if g is f)
        out += [html.escape(text[pos:i]), K.chip(f["span"], "stated", names[k]["label"].split(" (")[0])]
        pos = i + len(f["span"])
    out.append(html.escape(text[pos:]))
    return "".join(out), len(spans)


def placeholder_chips(story):
    """Operating knobs the text did not state: vetted default (orange) or synthetic placeholder (pink, 'missing')."""
    prov, vals = story["res"]["provenance"], story["res"]["values"]
    out = []
    for d in api.schema(story["vessel"]):
        if d["group"] == "operation" and not d["choices"] and prov.get(d["name"]) in ("default", "synthetic"):
            out.append(K.chip(f"{_fmt(vals[d['name']])} {d['unit']}", "default" if prov[d["name"]] == "default" else "missing", _short(d["label"])))
    return "".join(out[:6])


def trust_counts():
    """Claim labels over all stored traces, via llm.trace (labels untouched)."""
    n = {l: 0 for l in T.LABELS}
    for q in T.question_ids():
        for s in T.load(q)["steps"]:
            for c in s["claims"]:
                n[c["label"]] += 1
    return n


def setup_label(story):
    """This setup's label: weakest evidence wins (llm.trace.cap_of). Synthetic inputs, defaults and the tier status each cap at hypothesis."""
    ev = [{"kind": "tier_status"}] if story["vessel"] == "cvd_tube" else []
    if story["res"]["passport"]["synthetic"]:
        ev.append({"kind": "synthetic_model"})
    if any(p in ("default", "synthetic") for p in story["res"]["provenance"].values()):
        ev.append({"kind": "paramdef_default"})
    ev += [{"kind": "span_check"}] * any(f["status"] == "stated" for f in story["spec"]["params"].values())
    return T.cap_of(ev)


# ---------------- UI
def _hero_fallback(st, story):
    res = story["res"]
    st.markdown(f'<div class="vt-card" style="text-align:center">{K.icon(story["vessel"])}<div class="vt-cap">Schematic unavailable; numbers below are unchanged. '
                f'Regime: {html.escape(res["regime"].replace("_", " "))}</div></div>', unsafe_allow_html=True)


def _hero(st, story, height=300):
    try:
        from app.vessel_view import render_vessel_hero  # Track H
    except Exception:
        return _hero_fallback(st, story)
    try:
        render_vessel_hero(story["res"], story["vessel"], story["spec"], height=height)
    except Exception:
        _hero_fallback(st, story)


def _step_procedure(st, S):
    cols = st.columns(3)
    for c, (v, sc) in zip(cols, SCENARIOS.items()):
        with c:
            st.markdown(K.card(sc["title"], sc["cap"], S["scn"] == v, K.icon(v)), unsafe_allow_html=True)
            st.button("Choose" if S["scn"] != v else "Chosen", key=f"home_pick_{v}", width="stretch", type="primary" if S["scn"] == v else "secondary",
                      on_click=lambda v=v: S.update(scn=v, read=False))
    left, right = st.columns(2)
    with left:
        text = st.text_area("Procedure text", procedure(S["scn"]), height=170, key=f"home_text_{S['scn']}", label_visibility="collapsed")
        if st.button(COPY["btn.read"], key="home_read_btn", width="stretch", type="primary"):
            S["read"] = True
    S["text"] = text
    with right:
        if S["read"]:
            story = story_for(S)
            h, n = highlight(text, story["spec"])
            st.markdown(f'<div class="vt-text">{h}</div>', unsafe_allow_html=True)
            st.markdown(K.chip_legend() + " " + placeholder_chips(story), unsafe_allow_html=True)
            st.caption(COPY["cap.chips2"])


def _step_vessel(st, S):
    story = story_for(S)
    _hero(st, story)
    st.markdown(K.tiles(tile_items(story)), unsafe_allow_html=True)
    st.caption(COPY["cap.tiles"])


def _step_matters(st, S):
    import altair as alt, pandas as pd
    story = story_for(S)
    rows = story["knobs"][:5]
    if not rows:
        return st.caption("No knob moves the result.")
    df = pd.DataFrame(rows)
    df["dir"] = np.where(df["effect"] >= 0, "raises result", "lowers result")
    base = alt.Chart(df).encode(y=alt.Y("name:N", sort=None, title=None, axis=alt.Axis(labelLimit=260, labelFontSize=13)))
    bar = base.mark_bar(size=24).encode(x=alt.X("effect:Q", title=f"Change in {SCENARIOS[story['vessel']]['proxy'][1]} ({SCENARIOS[story['vessel']]['proxy'][2]})"), tooltip=["name", "effect"],
                                       color=alt.Color("dir:N", scale=alt.Scale(domain=["raises result", "lowers result"], range=[K.BLUE, K.VERM]), legend=alt.Legend(orient="bottom", title=None)))
    whisk = base.mark_rule(color=K.GREY, strokeWidth=2).encode(x="lo:Q", x2="hi:Q")
    st.altair_chart((bar + whisk).properties(height=230), width="stretch")
    top = rows[0]
    st.markdown(f'<div class="vt-take">Change {html.escape(top["name"].split(" (")[0].lower())} first.</div>', unsafe_allow_html=True)
    st.caption(COPY["cap.knobs"] + " " + COPY["cap.whisk"])
    with st.expander("Details"):
        st.dataframe(pd.DataFrame(story["knobs"]).rename(columns={"effect": "effect", "lo": "low whisker", "hi": "high whisker"}), hide_index=True, width="stretch")


def _step_calcs(st, S):
    import pandas as pd
    story = story_for(S)
    calcs, short = story["calcs"], SCENARIOS[story["vessel"]]["short"]
    if not calcs:
        return st.caption(COPY["cap.nocalc"])
    for c in calcs[:3]:
        col = st.columns([1, 6, 3])
        col[0].markdown(K.rank_dot(c["rank"]), unsafe_allow_html=True)
        col[1].markdown(f'**{html.escape(plain(c["calc"]))}**  \n{html.escape(c["label"].split(" (")[0])} moves the {short} by {_fmt(c["delta"])} {c["outcome_unit"]}.')
        color, sym = K.COST[c["cost"]]
        col[2].markdown(K.badge(f"{c['cost']} {sym}", color), unsafe_allow_html=True)
    st.caption(COPY["cap.calcs"])
    with st.expander("Details"):
        st.dataframe(pd.DataFrame(calcs)[["rank", "calc", "param", "cost", "sigma", "unit", "delta", "rationale"]], hide_index=True, width="stretch")


def _go_reasoning():
    import streamlit as st
    st.session_state["vt_main"], st.session_state["vt_adv"] = "Advanced", "Reasoning trace"  # tab keys set in app/dashboard.py


def _step_trust(st, S):
    story = story_for(S)
    from app.trace_tab import COL, GLYPH
    n = trust_counts()
    order = ("benchmarked", "uncertain", "hypothesis")
    st.markdown(K.meter([(l, n[l], COL[l]) for l in order]), unsafe_allow_html=True)
    st.markdown(" ".join(K.badge(f"{l} {n[l]}", COL[l], GLYPH[l]) for l in order), unsafe_allow_html=True)
    lab = setup_label(story)
    st.markdown(f'<div class="vt-take">This setup: {K.badge(lab, COL[lab], GLYPH[lab])}</div>', unsafe_allow_html=True)
    st.markdown(COPY["trust.sentence"])
    st.caption(COPY["cap.trust"])
    st.button(COPY["btn.reason"], key="home_reason", type="primary", width="stretch", on_click=_go_reasoning)
    st.caption(COPY["cap.reason"])


BODY = [_step_procedure, _step_vessel, _step_matters, _step_calcs, _step_trust]


def story_for(S):
    import streamlit as st
    chat = None
    try:
        from app.llm_settings import get_chat
        chat = get_chat()
    except Exception as e:  # bad sidebar settings: say so, fall back to the offline rules reader
        st.warning(f"LLM settings not usable ({e}); using the offline reader.")
    key = (S["scn"], S["text"], getattr(chat, "backend", None), getattr(chat, "model", None))
    cache = st.session_state.setdefault("home_stories", {})
    if key not in cache:
        with st.spinner("Reading and solving..."):
            try:
                cache[key] = build_story(S["scn"], S["text"], chat=chat)
            except Exception as e:  # never break the page
                st.error(f"Could not solve this procedure: {e}")
                st.stop()
    return cache[key]


def render():
    import streamlit as st
    st.markdown(K.CSS, unsafe_allow_html=True)
    ss = st.session_state
    if "home" not in ss:
        ss["home"] = {"step": 0, "scn": "cvd_tube", "text": procedure("cvd_tube"), "read": False}
    S = ss["home"]
    h = st.columns([5, 3])
    h[0].markdown(f'<div class="vt-name">{COPY["title.name"]}</div><div class="vt-pitch">{COPY["cap.pitch"]}</div>', unsafe_allow_html=True)
    h[1].markdown(f'<div style="text-align:right">{K.badge(COPY["badge.honesty"], K.ORANGE, "◆")}</div>', unsafe_allow_html=True)
    st.markdown(K.stepper(STEPS, S["step"]), unsafe_allow_html=True)
    st.subheader(COPY[f"title.{S['step'] + 1}"])
    BODY[S["step"]](st, S)
    b = st.columns(2)
    b[0].button(COPY["btn.back"], key="home_back", width="stretch", disabled=S["step"] == 0, on_click=lambda: S.update(step=S["step"] - 1))
    b[1].button(COPY["btn.next"], key="home_next", width="stretch", type="primary", disabled=S["step"] == len(STEPS) - 1,
                on_click=lambda: S.update(step=S["step"] + 1))


if __name__ == "__main__":  # regenerate the committed snapshots
    SNAP.mkdir(exist_ok=True)
    for v in SCENARIOS:
        (SNAP / f"{v}.json").write_text(json.dumps(_build(v, procedure(v), 12), indent=1, default=float))
        print("wrote", v)
