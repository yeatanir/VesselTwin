"""Studio page: (1) Ask the agent, the visible LLM role (live tool loop or recorded replay); (2) Add a vessel, a pseudo-but-honest wizard.
Entry point: render(). Provider settings are shared with every page through app.llm_settings (session only, key never shown)."""
import glob, html, json, pathlib, tempfile, threading, time
import streamlit as st
from app import custom_vessel as cv, llm_settings, theme
from llm import agent as A

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXAMPLES = [("CVD tube", "real_01_cvd_tube"), ("Ampoule", "real_14_ampoule"), ("Sorbent bed", "real_29_sorbent")]
GLYPH = {"extract_setup": "≡", "solve": "∑", "rank_calculations": "⇅", "lookup_parameter": "⌕"}
WHAT = {"extract_setup": "Read the procedure", "solve": "Run the vessel model", "rank_calculations": "Rank atomistic calculations", "lookup_parameter": "Look up literature"}
STEP_DELAY = 0.7  # seconds between replayed cards
SUFFIX = "\nWhich variable should the experimentalist change first, and which atomistic calculation matters most?"
CSS = """<style>
@keyframes vs-in{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.vs-tl{border-left:3px solid #BCD3F2;margin-left:1rem;padding-left:1.2rem;position:relative;animation:vs-in .5s ease both}
.vs-tl:before{content:"";position:absolute;left:-9px;top:1.1rem;width:15px;height:15px;border-radius:50%;background:#1F5FBF;border:3px solid #fff;box-shadow:0 0 0 2px #BCD3F2}
.vs-step{background:#fff;border:1px solid #D6E3F5;border-radius:16px;padding:.8rem 1rem;box-shadow:0 2px 10px rgba(11,31,68,.06)}
.vs-step .h{display:flex;align-items:center;gap:.6rem;color:#0B1F44;font-weight:700}
.vs-g{display:inline-flex;width:2rem;height:2rem;border-radius:10px;background:#EEF4FC;color:#1F5FBF;align-items:center;justify-content:center;font-size:1.2rem}
.vs-s{margin-left:auto;color:#6B7A90;font-weight:500;font-size:.85rem}
.vs-a{font:.78rem/1.3 ui-monospace,Menlo,monospace;color:#6B7A90;margin:.35rem 0;word-break:break-all}
.vs-o{color:#0B1F44}
.vs-final{background:linear-gradient(135deg,#fff,#EEF4FC);border:1.5px solid #1F5FBF;border-radius:20px;padding:1.2rem 1.4rem;box-shadow:0 10px 30px rgba(31,95,191,.15);animation:vs-in .5s ease both}
.vs-final h4{margin:.8rem 0 .1rem;color:#1F5FBF;font-size:.8rem;text-transform:uppercase;letter-spacing:.06em}
.vs-final p{margin:0;color:#0B1F44}
.vs-banner{background:#FFF3E5;border:1px solid #F6D3A8;border-radius:16px;padding:.8rem 1.1rem;color:#7a4300;font-weight:600}
.vs-live{background:#EEF4FC;border:1px solid #BCD3F2;border-radius:16px;padding:.8rem 1.1rem;color:#0B1F44;font-weight:600}
.vs-kpi{display:flex;gap:.8rem;flex-wrap:wrap}.vs-kpi>div{flex:1 1 9rem;background:#fff;border:1px solid #D6E3F5;border-radius:16px;padding:.8rem 1rem;box-shadow:0 2px 10px rgba(11,31,68,.06)}
.vs-kpi .l{color:#6B7A90;font-size:.85rem}.vs-kpi .n{font-size:1.8rem;font-weight:800;color:#0B1F44;line-height:1.15}.vs-kpi .u{color:#6B7A90;font-size:.9rem;margin-left:.3rem}
.vs-hyp{display:inline-block;border-radius:999px;padding:.15rem .8rem;font-weight:700;font-size:.85rem;background:#FFF3E5;color:#B35F00;border:1px solid #F6D3A8}
@media (prefers-reduced-motion:reduce){.vs-tl,.vs-final{animation:none}}
</style>"""


def _e(x):
    return html.escape(str(x))


def _short(o, n=150):
    s = json.dumps(o, default=str) if not isinstance(o, str) else o
    return s if len(s) <= n else s[:n] + "…"


def summarize(tool, out):
    """One line describing a tool output."""
    if isinstance(out, str):  # llm.agent logs small outputs as a JSON string
        try:
            out = json.loads(out)
        except ValueError:
            return _short(out, 110)
    if not isinstance(out, dict):
        return "no output"
    if "sha256" in out:
        return f"large output ({out.get('bytes', '?')} bytes)"
    if "error" in out:
        return "error: " + _short(out["error"], 110)
    if tool == "extract_setup":
        return f"{out.get('vessel')}: {len(out.get('stated', {}))} stated, {out.get('n_not_stated', '?')} not stated"
    if tool == "solve":
        return f"regime {str(out.get('regime', '?')).replace('_', ' ')}, {len(out.get('derived_p50', {}))} outputs"
    if tool == "rank_calculations":
        r = out.get("ranking") or [{}]
        return f"top: {r[0].get('calc', '?')} ({r[0].get('param', '?')})"
    if tool == "lookup_parameter":
        return f"{out.get('found', 0)} cached excerpt(s)"
    return _short(out, 110)


def step_html(s):
    sec = f"{s['seconds']:.2f} s" if isinstance(s.get("seconds"), (int, float)) else "…"
    out = summarize(s["tool"], s["output"]) if s.get("output") is not None else "running…"
    return (f'<div class="vs-tl"><div class="vs-step"><div class="h"><span class="vs-g">{GLYPH.get(s["tool"], "·")}</span>'
            f'<span>{_e(s["tool"])} <span style="font-weight:400;color:#6B7A90">· {_e(WHAT.get(s["tool"], ""))}</span></span><span class="vs-s">{sec}</span></div>'
            f'<div class="vs-a">{_e(_short(s["args"]))}</div><div class="vs-o">{_e(out)}</div></div></div>')


def final_html(run):
    f = run["final"]
    parts = "".join(f"<h4>{t}</h4><p>{_e(f.get(k, ''))}</p>" for t, k in
                    (("Answer", "answer"), ("Change first", "change_first"), ("Atomistic priority", "atomistic_priority"), ("Caveats", "caveats")))
    lab = A.final_label(run)
    return (f'<div class="vs-final"><span class="vs-hyp">{_e(lab)}</span> {theme.info_html("The model never picks its own trust label: any run that solved a vessel is a hypothesis (tier-1 model, synthetic inputs).")}'
            f'{parts}</div>')


def draw(run, box, animate=False):
    """Render a run's timeline and final card into `box`; with animate, one card at a time."""
    for s in run["steps"]:
        with box:
            st.html(step_html(s))
        if animate:
            time.sleep(STEP_DELAY)
    with box:
        if run.get("final"):
            st.html(final_html(run))
        else:
            st.warning("The model stopped without a final answer.")


def _events(path):
    out = []
    try:
        for l in pathlib.Path(path).read_text().splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def run_live(chat, question, box):
    """Run the agent in a thread and draw a card as each tool output lands. Returns a run dict or raises."""
    tmp, res = tempfile.mkdtemp(prefix="vt_agent_"), {}

    def work():
        try:
            res["final"], res["path"] = A.run_agent(question, chat, tmp, A.MAX_STEPS)
        except Exception as ex:  # surfaced to the user below; backends never put the key in a message
            res["err"] = ex
    t = threading.Thread(target=work, daemon=True)
    t.start()
    shown = 0
    while True:
        alive = t.is_alive()
        ev = [e for f in sorted(glob.glob(tmp + "/*.jsonl")) for e in _events(f)]
        outs = [e for e in ev if e["kind"] == "tool_output"]
        calls = {e["step"]: e for e in ev if e["kind"] == "tool_call"}
        for o in outs[shown:]:
            c = calls[o["step"]]
            with box:
                st.html(step_html({"tool": o["name"], "args": c["args"], "output": o["output"], "seconds": o.get("seconds")}))
        shown = len(outs)
        if not alive:
            break
        time.sleep(0.3)
    if "err" in res:
        raise res["err"]
    run = A.load_run(res["path"])
    with box:
        if run["final"]:
            st.html(final_html(run))
        else:
            st.warning("The model stopped without a final answer within 8 steps.")
    return run


def _recorded(text):
    rr = A.recorded_runs()
    if not rr:
        return None
    key = text.strip()[:80]
    m = next((r for r in rr if key and key in r["question"]), None)
    return m or rr[0], m is not None


def _example(stem):
    st.session_state["studio_q"] = json.loads((ROOT / "bench/procedures" / f"{stem}.json").read_text())["text"]


def tab_agent():
    ss = st.session_state
    ss.setdefault("studio_q", "")
    try:
        chat = llm_settings.get_chat()
        cerr = None
    except Exception as ex:
        chat, cerr = None, str(ex)
    c = st.columns([3, 1])
    c[0].markdown("#### Paste a procedure, or ask a question " + theme.info_html("The agent picks one tool per turn: read the procedure, run the model, rank atomistic calculations, look up cached literature. Max 8 steps. Every number comes from a tool."), unsafe_allow_html=True)
    c[1].html(f'<span class="vs-hyp" style="background:#EEF4FC;color:#1F5FBF;border-color:#BCD3F2">{_e(chat.model) if chat else "no model connected"}</span>')
    st.text_area("Procedure or question", key="studio_q", height=150, label_visibility="collapsed",
                 placeholder="Paste a synthesis procedure here, or try an example below.")
    cols = st.columns(len(EXAMPLES) + 1)
    for col, (lab, stem) in zip(cols, EXAMPLES):
        col.button(lab, key=f"studio_ex_{stem}", on_click=_example, args=(stem,), use_container_width=True)
    go = cols[-1].button("Run agent", key="studio_run", type="primary", use_container_width=True)
    if cerr:
        st.error(cerr)
    box = st.container()
    if go:
        text = ss.studio_q.strip()
        if not text:
            st.info("Pick an example or paste a procedure first.")
        elif chat:
            with box:
                st.html('<div class="vs-live">Live run · ' + _e(chat.model) + "</div>")
            try:
                ss["studio_last"] = run_live(chat, "Here is a synthesis procedure:\n" + text + SUFFIX, box)
            except Exception as ex:
                ss.pop("studio_last", None)
                with box:
                    st.error(f"Live run failed: {type(ex).__name__}: {ex}")
        else:
            run, hit = _recorded(text) if A.recorded_runs() else (None, False)
            if run is None:
                st.error("No recorded run found in runs/traces.")
            else:
                with box:
                    st.html('<div class="vs-banner">No model connected: replaying a recorded run. Connect a model above to run live.</div>')
                    st.caption(f"Recorded run · {run['model']} · {run['date']}" + ("" if hit else " · closest recording, not your exact text"))
                draw(run, box, animate=True)
                ss["studio_last"] = {**run, "_banner": True}
    elif ss.get("studio_last"):
        r = ss["studio_last"]
        with box:
            if r.get("_banner"):
                st.html('<div class="vs-banner">No model connected: replaying a recorded run.</div>')
                st.caption(f"Recorded run · {r['model']} · {r['date']}")
        draw(r, box)


# ---- Add a vessel ----
PREF = {"ampoule": ("transport_rate_mmol_h", "growth_rate_mm_day"), "photo": ("conversion_t_irr", "fraction_absorbed")}


def kpis(r, template):
    keys = [k for k in PREF.get(template, ()) if k in r["derived"]]
    keys += [k for k in r["derived"] if k not in keys and k != "T_K" and not k.startswith("species.") and "err" not in k]
    items = [("Regime", r["regime"].replace("_", " "), "")] + [(k.replace("_", " "), f"{r['derived'][k]:.3g}", r["units"].get(k, "")) for k in keys[:2]]
    return '<div class="vs-kpi">' + "".join(f'<div><div class="l">{_e(l)}</div><div><span class="n">{_e(v)}</span><span class="u">{_e(u)}</span></div></div>' for l, v, u in items) + "</div>"


def generic_fig(e):
    import plotly.graph_objects as go
    f = go.Figure(go.Scatter(x=[0, 10, 10, 0, 0], y=[0, 0, 4, 4, 0], mode="lines", fill="toself", fillcolor="rgba(31,95,191,.10)", line=dict(color="#0B1F44", width=3)))
    f.add_annotation(x=5, y=2, text=e["name"], showarrow=False, font=dict(size=18, color="#0B1F44"))
    f.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), xaxis=dict(visible=False), yaxis=dict(visible=False, scaleanchor="x"), plot_bgcolor="#fff", showlegend=False)
    return f


def figure(e, r):
    try:
        import plotly.graph_objects as go
        from app import vessel_view as vv
        from app.viz.template import apply_template
        return apply_template(go.Figure(vv._schematic(e["base"], vv._key(r["values"]))).update_layout(height=320))  # schematic from the cloned values, never a stored CFD case
    except Exception:
        return generic_fig(e)


def tab_vessel():
    ss = st.session_state
    ss.setdefault("studio_tpl", None)
    step = 0 if not ss.studio_tpl else 1 if "studio_entry" not in ss else 2
    st.html('<div style="display:flex;gap:.5rem;margin:.2rem 0 .6rem">' + "".join(
        f'<span class="vs-hyp" style="{"" if i == step else "opacity:.45;"}background:{"#1F5FBF" if i == step else "#EEF4FC"};color:{"#fff" if i == step else "#1F5FBF"};border-color:#BCD3F2">{i + 1}  {n}</span>'
        for i, n in enumerate(("Pick a template", "Describe it", "Create and run"))) + "</div>")
    st.markdown("#### Which physics is closest? " + theme.info_html("A custom vessel borrows the physics of a validated template. Nothing is written to the repository; download the stub to add it for real."), unsafe_allow_html=True)
    cols = st.columns(len(cv.TEMPLATES))
    from app import landing
    for col, (k, (vn, title, line, _)) in zip(cols, cv.TEMPLATES.items()):
        with col.container(key=f"vcard_{k}"):
            try:
                landing.H(f'<div style="max-width:140px">{landing.icon(vn)}</div>')
            except Exception:
                pass
            st.markdown(f"**{title}**")
            st.caption(line)
            if st.button("Selected" if ss.studio_tpl == k else "Choose", key=f"studio_pick_{k}", use_container_width=True):
                ss.studio_tpl = k
                ss.pop("studio_entry", None)
                st.rerun()
    if ss.studio_tpl:
        k = ss.studio_tpl
        st.html(f"<style>.st-key-vcard_{k}{{border-color:#1F5FBF!important;background:#EEF4FC!important}}</style>")
        st.markdown("#### Describe it")
        name = st.text_input("Vessel name", value="My " + cv.TEMPLATES[k][1].lower(), key=f"studio_name_{k}")
        vals, fc = {}, st.columns(2)
        for i, d in enumerate(cv.fields(k)):
            with fc[i % 2]:
                vals[d.name] = st.number_input(f"{d.label} [{d.unit}]" if d.unit else d.label, min_value=float(d.lo), max_value=float(d.hi),
                                               value=float(d.default), key=f"studio_f_{k}_{d.name}", format="%g")
        notes = st.text_area("Notes (free text)", key=f"studio_notes_{k}", height=80, placeholder="What is different about your vessel?")
        if st.button("Create and run", key="studio_create", type="primary"):
            e = cv.make(k, name, vals, notes)
            cv.save(ss, e)
            ss.studio_entry = e["id"]
            ss.pop("studio_draft", None)
            st.rerun()
    if ss.get("studio_entry"):
        e = ss.vt_custom_vessels[ss.studio_entry]
        with st.spinner("Running the template physics"):
            r = cv.run(e)
        st.markdown(f"#### {_e(e['name'])}")
        st.plotly_chart(figure(e, r), width="stretch")
        st.html(kpis(r, e["template"]))
        st.html(f'<span class="vs-hyp">{r["label"]}</span> &nbsp; <span style="color:#6B7A90">{_e(r["note"])}</span>')
        st.download_button("Download vessel stub", cv.stub(e), file_name=f"{e['id']}.py", mime="text/x-python", key="studio_stub")
        st.caption("Drop the file into vessels/ and restart; see docs/ADDING_A_VESSEL.md.")
        try:
            chat = llm_settings.get_chat()
        except Exception:
            chat = None
        if chat and st.button("Ask the LLM to draft the physics notes", key="studio_draft_btn"):
            msg = [{"role": "user", "content": f"Draft short physics notes (key dimensionless groups, likely limiting regime, what a template '{e['base']}' model gets wrong) for a custom vessel. Name: {e['name']}. Values: {e['edited']}. Notes: {e['notes']}"}]
            try:
                ss.studio_draft = chat(msg)
            except Exception as ex:
                st.error(f"{type(ex).__name__}: {ex}")
        if ss.get("studio_draft") and chat:
            st.html('<div class="vs-banner">LLM draft, not run, not validated</div>')
            st.write(ss.studio_draft)


def render():
    st.html(CSS)
    theme.inject_css()
    st.title("Studio")
    st.caption("Ask the agent, or add your own vessel.")
    llm_settings.render(st.container())
    t1, t2 = st.tabs(["Ask the agent", "Add a vessel"])
    with t1:
        tab_agent()
    with t2:
        tab_vessel()
