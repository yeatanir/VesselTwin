"""Reasoning trace tab: one benchmark question as a replayable agent timeline. Reads traces/sens_<id>.json (written by
`python -m llm.trace`; generated on first use if missing). Labels come only from llm.trace (LABEL_RULES, EVIDENCE_CAP).
Usage: from app.trace_tab import render; render(st)"""
import html, json
import altair as alt
import pandas as pd
from llm import trace as T
from llm import agent as AG
from app.common import show_df

# Okabe-Ito (colour-blind safe); mid-tone so it reads on light and dark; each label also has its own glyph
COL = {"benchmarked": "#0072B2", "uncertain": "#E69F00", "hypothesis": "#CC79A7"}
GLYPH = {"benchmarked": "●", "uncertain": "▲", "hypothesis": "◆"}
BLUE, ORANGE, VERM = "#0072B2", "#E69F00", "#D55E00"
CSS = """<style>
.vt-pill{display:inline-block;border:1.5px solid var(--c);color:var(--c);border-radius:999px;padding:0 .6em;font-size:.78em;font-weight:600;margin-right:.4em;white-space:nowrap}
.vt-head{display:flex;align-items:center;gap:.7rem;margin:0 0 .3rem 0}
.vt-dot{width:2.1rem;height:2.1rem;border-radius:50%;border:2px solid #56B4E9;color:#56B4E9;display:flex;align-items:center;justify-content:center;font-weight:700;flex:none}
.vt-title{font-size:1.25rem;font-weight:700}
.vt-link{height:1.1rem;margin-left:1.05rem;border-left:2px dashed #56B4E9;opacity:.6}
.vt-claim{margin:.15rem 0}
.vt-quote{border-left:3px solid #56B4E9;padding:.1rem .8rem;margin:.4rem 0;opacity:.95}
.vt-flag{border:2px solid var(--c);border-radius:8px;padding:.6rem .9rem;margin:.4rem 0;font-weight:600}
</style>"""


def label(tr):
    """Honest provenance label, derived from the trace itself. A replay is never presented as live."""
    p = tr["policy"]
    if p["kind"] == "llm":
        return f"Recorded run · {p['llm']} · {p.get('date', 'date unknown')}"
    return "Scripted replay (not model-driven)"


def pill(label):
    return f'<span class="vt-pill" style="--c:{COL[label]}">{GLYPH[label]} {label}</span>'


def claims_html(claims):
    out = []
    for c in claims:
        ev = ", ".join(f"{e['kind']}" + (f" [{e['ref']}]" if e.get("ref") else "") for e in c["evidence"]) or "none"
        out.append(f'<div class="vt-claim">{pill(c["label"])}{html.escape(c["text"])}'
                   f'<br><small style="opacity:.7">evidence: {html.escape(ev)}; cap = weakest evidence</small></div>')
    return "".join(out)


def _tool_calls(st, step):
    with st.expander(f"Tool calls ({len(step['tool_calls'])}) - recorded by the policy"):
        show_df(st, pd.DataFrame([{"tool": c["name"], "args": json.dumps(c["args"], default=str), "result": c["result_summary"]} for c in step["tool_calls"]]), hide_index=True)


def _step_extract(st, s):
    f = s["data"]["fields"]
    n = {k: sum(v["status"] == k for v in f.values()) for k in ("stated", "default", "missing")}
    c = st.columns(3)
    c[0].metric("stated (span-checked)", n["stated"])
    c[1].metric("default (not a fact)", n["default"])
    c[2].metric("missing", n["missing"])
    rows = [(k, v) for k, v in f.items() if v["status"] == "stated"]
    if rows:
        t = "".join(f"<tr><td><code>{k}</code></td><td>{v['value']} {v['unit'] or ''}</td><td><em>\"{html.escape(str(v['span']))}\"</em></td></tr>" for k, v in rows)
        st.markdown(f"<table><tr><th>parameter</th><th>value</th><th>verbatim span</th></tr>{t}</table>", unsafe_allow_html=True)
    else:
        st.warning("Nothing numeric was stated in the question. The model will run entirely on defaults.")
    with st.expander("All parameters with status badges"):
        sym = {"stated": "● stated", "default": "▲ default", "missing": "○ missing"}
        show_df(st, pd.DataFrame([{"parameter": k, "status": sym[v["status"]], "value": "" if v["value"] is None else str(v["value"]), "unit": v["unit"], "note": v["note"]} for k, v in f.items()]), hide_index=True)


def _step_lit(st, s):
    d = s["data"]
    if not d["found"]:
        st.error("No evidence found in the stored literature (papers.json, docs/literature/*.json). Nothing is inferred from this.")
        return
    n_ok = sum(bool(e.get("support", {}).get("verified")) for e in d["excerpts"])
    st.caption(f"{n_ok} of {len(d['excerpts'])} excerpts verified: an excerpt supports the parameter only if it names it and states a value within 2% of the question's (docs/prereg/track-c.md).")
    st.caption("Verbatim excerpts only (40 words or fewer). The question's own paper is the held-out reference used in step 4; the model never saw it.")
    for e in sorted(d["excerpts"], key=lambda e: not e["is_question_paper"]):
        link = f"[doi:{e['doi']}](https://doi.org/{e['doi']})" if e["doi"] and e["doi"][0] == "1" else (f"[{e['doi']}](https://arxiv.org/abs/{e['doi'].split(':')[-1]})" if e["doi"] else "no DOI (agent answer sentence, not the paper's words)")
        tag = "this question's paper" if e["is_question_paper"] else ("literature-agent answer" if not e["doi"] else f"related benchmark paper {e['id']}")
        st.markdown(f'<div class="vt-quote">"{html.escape(e["quote"])}"</div>', unsafe_allow_html=True)
        sup = e.get("support")
        badge = (f'<span class="vt-pill" style="--c:{BLUE}">✔ verified excerpt (name + value within 2%)</span>' if sup and sup["verified"]
                 else f'<span class="vt-pill" style="--c:{ORANGE}">▲ unverified excerpt</span>' + (f' <small>({sup["why"]})</small>' if sup else ""))
        st.markdown(f"{badge} {tag} - {e['citation']} - {link}", unsafe_allow_html=True)
    if d["paper_notes"]:
        st.caption("Benchmark notes on the paper: " + d["paper_notes"])


def _step_model(st, s):
    d = s["data"]
    c = st.columns(3)
    c[0].metric("Regime", d["regime"].replace("_", " "))
    c[1].metric("Tier", d["tier"])
    c[2].metric("Synthetic flag", "yes" if d["synthetic"] else "no")
    df = pd.DataFrame(d["passport"])
    base = alt.Chart(df).encode(y=alt.Y("quantity:N", sort=None, title=None))
    st.markdown("**Passport (p05 / p50 / p95)**")
    st.altair_chart((base.mark_rule(color=BLUE, strokeWidth=3).encode(x=alt.X("p05:Q", scale=alt.Scale(type="symlog"), title="value (symlog)"), x2="p95:Q") +
                     base.mark_point(color=BLUE, filled=True, size=70, shape="diamond").encode(x="p50:Q", tooltip=["quantity", "unit", "p05", "p50", "p95"])
                     ).properties(height=22 * len(df) + 40), width="stretch")
    kb = d["knob_bars"]
    kd = pd.DataFrame(kb["rows"])
    kd["knob_step"] = kd["knob"] + " (" + kd["step"] + ")"
    st.markdown(f"**Which knob moves `{kb['proxy']}`** (change in p50, % of base; whiskers = same change at p05 and p95)")
    b = alt.Chart(kd).encode(y=alt.Y("knob_step:N", sort=alt.EncodingSortField("effect_p50_pct", order="descending"), title=None))
    st.altair_chart((b.mark_bar(color=BLUE, opacity=0.8).encode(x=alt.X("effect_p50_pct:Q", title="% change in p50 across the step"),
                                                                 tooltip=["knob", "step", "low", "high", "effect_p05_pct", "effect_p50_pct", "effect_p95_pct"]) +
                     b.mark_rule(color=ORANGE, strokeWidth=3).encode(x="effect_p05_pct:Q", x2="effect_p95_pct:Q")).properties(height=190), width="stretch")
    st.markdown(f"Predicted flake shape at the substrate: **{d['shape_here']}** " + pill("hypothesis") +
                " (shape benchmark accuracy 0.50, equal to the always-triangle baseline)", unsafe_allow_html=True)
    with st.expander("tiers.json status for this vessel"):
        st.write(d["tier_status"])


def _step_compare(st, s):
    d = s["data"]
    v = d["verdict"]
    if v == "not_modellable":
        st.info(f"Not modellable: {d['reason']}. No model claim is made for this question; the paper's '{d['observed']}' stands alone.")
        return
    flag = []
    if v == "disagree":
        flag.append((VERM, f"MODEL DISAGREES WITH THE PAPER: model '{d['model_direction']}', paper '{d['observed']}'"))
    if d["flip"]:
        flag.append((VERM, "SIGN FLIP: the p05 and p95 trends point in opposite directions"))
    if v == "agree_fragile":
        flag.append((ORANGE, "Direction matches, but the match is fragile (" + ", ".join(x for x, on in (("band-uncertain", d["uncertain"]), ("p05-p95 band endpoints overlap", d["band_overlap_endpoints"])) if on) + ")"))
    if v == "agree":
        flag.append((BLUE, f"Model and paper agree on '{d['observed']}' for this item"))
    for c, t in flag:
        st.markdown(f'<div class="vt-flag" style="--c:{c}">{html.escape(t)}</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    cols[0].metric("Paper (observed)", d["observed"])
    cols[1].metric("Model (p50 trend)", d["model_direction"])
    cols[2].metric("Knob sweep", f"{d['parameter']}: {d['sweep'][0]} to {d['sweep'][1]}")
    if d["series"]:
        a = pd.DataFrame(d["series"], columns=["p05", "p50", "p95"])
        a["x"] = d["values"]
        band = alt.Chart(a).mark_area(opacity=0.25, color=BLUE).encode(x=alt.X("x:Q", title=d["parameter"]), y=alt.Y("p05:Q", title=d["proxy"]), y2="p95:Q")
        line = alt.Chart(a).mark_line(color=BLUE, strokeWidth=3, point=alt.OverlayMarkDef(shape="diamond", size=80, filled=True)).encode(x="x:Q", y="p50:Q", tooltip=["x", "p05", "p50", "p95"])
        st.altair_chart((band + line).properties(height=220), width="stretch")
        st.caption(f"Proxy `{d['proxy']}` (an assumed stand-in for the observed quantity, not the quantity itself). Line = p50, band = p05..p95 from parameter uncertainty.")
    elif d["labels"]:
        show_df(st, pd.DataFrame({d["parameter"]: d["values"], "shape class": d["labels"]}), hide_index=True)
    sm = d["summary"]
    st.caption(f"Benchmark context: model {sm['correct']}/{sm['n_modellable']} direction accuracy, majority baseline {sm['majority_baseline_correct']}/{sm['n_modellable']}, "
               f"blind no-tool baseline {sm['blind_correct_on_modellable8']}/{sm['n_modellable']}. A single match is not evidence of skill.")


def _step_briefs(st, s):
    d = s["data"]
    L = {c["id"]: c["label"] for c in s["claims"]}
    a, b = st.columns(2)
    with a:
        st.markdown("**Experimentalist: what to change and measure**")
        st.markdown(pill(L["c5.1"]), unsafe_allow_html=True)
        for x in d["experimentalist"]:
            st.markdown(f"- {x}")
    with b:
        st.markdown("**Simulation person: atomistic brief**")
        st.markdown(pill(L["c5.2"]), unsafe_allow_html=True)
        for x in d["simulation"]:
            st.markdown(f"- {x}")
        with st.expander("Full atomistic brief (markdown)"):
            st.markdown(d["simulation_markdown"])
    st.caption("Both briefs rest on the vessel model's sensitivities, which carry the tier and synthetic limits from step 3, so they cannot be labelled above those.")


RENDER = {"extract_setup": _step_extract, "literature": _step_lit, "vessel_model": _step_model, "compare": _step_compare, "briefs": _step_briefs}


def does_not_show(st, tr):
    with st.container(border=True):
        st.markdown("### What this does not show")
        lim = tr["limits"]
        st.markdown(f"- **Sensitivity benchmark:** {lim['sensitivity']} The model does not beat a no-tool baseline; n = 8 cannot validate it.\n"
                    f"- **Shape class:** {lim['shape']}\n"
                    "- **Proxies are assumptions** (nucleation density ~ supersaturation, coverage ~ MoO3 flux); a wrong proxy gives a wrong sign that says nothing about the physics.\n"
                    "- **Boat and substrate positions** are always defaults here; the model is 1-D and steady-state, with no source depletion or layer number.\n"
                    + ("- **This trace is a recorded model run**; the model chose the tool order, but the tools and numbers behind them are the same synthetic-limited models.\n"
                       if tr["policy"]["kind"] == "llm" else "- **Scripted replay (not model-driven):** the policy calls tools in a fixed order; it reasons about nothing.\n"))
        st.markdown("**Verification misses recorded in tiers.json**")
        for k in ("cvd_tube", "ampoule"):
            st.markdown(f"*{k}*")
            st.markdown("> " + lim["tiers"][k])


def render_recorded(st, run):
    """A model-driven run exactly as logged in runs/traces/<ts>.jsonl. Never live: the label says Recorded."""
    st.markdown(f"**Recorded run · {run['model']} · {run['date']}**")
    st.caption(f"Replay of {run['file']}; the model chose each tool, nothing is re-run. Question: {run['question']}")
    for s in run["steps"]:
        with st.container(border=True):
            st.markdown(f"**Step {s['step']}: `{s['tool']}`** ({s['seconds']} s)")
            st.code(json.dumps(s["args"], indent=1, default=str)[:1500], language="json")
            st.code(str(s["output"])[:1500], language="json")
    f = run["final"]
    lab = AG.final_label(run)
    st.markdown(f"{pill(lab)} **Final answer**", unsafe_allow_html=True)
    for k in ("answer", "change_first", "atomistic_priority", "caveats"):
        st.markdown(f"- **{k.replace('_', ' ')}:** {f[k]}")
    st.caption("The label is set by code from the tools used (vessel tier and synthetic limits), not by the model.")


def render(st, qid=None):
    st.markdown(CSS, unsafe_allow_html=True)
    runs = AG.recorded_runs()
    if runs:
        i = st.selectbox("Recorded model runs", range(len(runs)), key="trace_run", format_func=lambda i: f"{runs[i]['model']} · {runs[i]['date']} · {runs[i]['question'][:60]}")
        render_recorded(st, runs[i])
        st.divider()
    papers = {p["id"]: p for p in json.loads((T.ROOT / "bench/sensitivity/papers.json").read_text())}
    qid = qid or st.selectbox("Question (held-out sensitivity benchmark)", list(papers), key="trace_q",
                              format_func=lambda i: f"{i}: {papers[i]['outcome_quantity']} vs {papers[i]['parameter']}", index=2)
    tr = T.load(qid)
    st.markdown("### Reasoning trace")
    st.info(tr["question"]["text"])
    with st.expander("Label rules (the only place labels are defined: llm/trace.py)"):
        for k in reversed(T.LABELS):
            st.markdown(f"{pill(k)} {T.LABEL_RULES[k]}", unsafe_allow_html=True)
        st.caption("A claim's label is capped by its weakest evidence, and the app never upgrades it.")
    n = len(tr["steps"])
    k = st.select_slider("Replay: show steps up to", options=list(range(1, n + 1)), value=n, key=f"trace_k_{qid}")
    st.markdown(f"**{label(tr)}**")
    st.caption(f"Policy: {tr['policy']['name']} ({tr['policy']['kind']}), seed {tr['seed']}, trace {tr['trace_id']}.json")
    for s in tr["steps"][:k]:
        st.markdown(f'<div class="vt-head"><div class="vt-dot">{s["idx"]}</div><div class="vt-title">{html.escape(s["title"])}</div></div>', unsafe_allow_html=True)
        with st.container(border=True):
            if s["claims"]:
                st.markdown(claims_html(s["claims"]), unsafe_allow_html=True)
            RENDER[s["name"]](st, s)
            _tool_calls(st, s)
        st.markdown('<div class="vt-link"></div>', unsafe_allow_html=True)
    does_not_show(st, tr)
