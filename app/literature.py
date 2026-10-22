"""Literature section: which parameters have a sourced value, stored literature-agent answers, optional live Edison call (own key).
Offline by default. Keys only in st.session_state; never written anywhere. Usage: from app.literature import render; render(vessel)"""
import json, pathlib, re
import streamlit as st
from core import api

ROOT = pathlib.Path(__file__).resolve().parents[1]
LIT = ROOT / "docs" / "literature"
DOI = re.compile(r"(10\.\d{4,9}/[^\s;,)]+)|(arXiv:\s?\d{4}\.\d{4,5})", re.I)
VALENCY_NOTE = "Valency search runs through its MCP server (used while building this project); the app shows stored results."
VERIFIED = "Quote check (docs/status_oct21.md): 10 of 48 verified; Edison answer sentences 0 of 23. Treat stored answers as leads, not as verified numbers."


def _info(text):
    try:
        from app.theme import info
        info(text)
    except ImportError:
        st.caption(text)


def param_sources(vessel):
    """rows: name, label, unit, value, kind (sourced | synthetic | default), source text, link (DOI/arXiv URL or '')."""
    rows = []
    for d in api.schema(vessel):
        s = d["source"] or "default"
        kind = "synthetic" if s.startswith("synthetic") else "default" if s == "default" else "sourced"
        m = DOI.search(s)
        link = "" if not m else ("https://doi.org/" + m.group(1).rstrip(".") if m.group(1) else "https://arxiv.org/abs/" + re.sub(r"\D*(\d.*)", r"\1", m.group(2)))
        rows.append({"name": d["name"], "label": d["label"], "unit": d["unit"], "value": d["default"], "kind": kind, "source": s, "link": link, "help": d["help"]})
    return rows


def stored_answers():
    """Cached literature-agent answers from docs/literature: question, date, status, answer excerpt."""
    out = []
    for f in sorted(LIT.glob("edison_q*.json")):
        try:
            d = json.loads(f.read_text())
        except ValueError:
            continue
        out.append({"label": f.stem.replace("edison_", ""), "query": d.get("query", ""), "date": str(d.get("created_at", ""))[:10],
                    "status": d.get("status", "?"), "answer": d.get("answer") or ""})
    return out


def edison_available():
    try:
        import edison_client  # noqa: F401
        return True
    except ImportError:
        return False


def ask_edison(question, key):
    """One plain LITERATURE job (never the high variant). Returns the answer text. Raises on any failure; key never in messages."""
    from edison_client import EdisonClient, JobNames
    c = EdisonClient(api_key=key)
    r = c.run_tasks_until_done({"name": JobNames.LITERATURE, "query": question})
    r = r[0] if isinstance(r, (list, tuple)) else r
    return getattr(r, "answer", None) or str(getattr(r, "formatted_answer", "")) or "(no answer returned)"


def _sources(vessel):
    rows = param_sources(vessel)
    n = {k: sum(r["kind"] == k for r in rows) for k in ("sourced", "synthetic", "default")}
    st.caption(f"{n['sourced']} sourced, {n['synthetic']} synthetic placeholder, {n['default']} plain default")
    _info("Sourced = the parameter carries a citation or datasheet in its definition. Synthetic = illustrative placeholder. Default = chosen starting value without a source. A citation text is not a verified quote.")
    sel = st.multiselect("Show", ["sourced", "synthetic", "default"], default=["sourced"], key=f"lit_f:{vessel}")
    txt = st.text_input("Filter by name", key=f"lit_q:{vessel}").lower()
    for r in rows:
        if r["kind"] in sel and txt in (r["name"] + r["label"]).lower():
            c = st.columns([5, 3, 1])
            c[0].markdown(f"**{r['label']}**  \n`{r['name']}` = {r['value']} {r['unit']}")
            c[1].markdown(f"[{r['link']}]({r['link']})" if r["link"] else r["kind"])
            with c[2]:
                _info(f"{r['source']}. {r['help']}")


def _agents(vessel):
    st.markdown("**Literature agents**")
    st.markdown("- **Edison Scientific Literature agent**: cited answers; one credit per question; needs your own key.\n"
                "- **Valency**: semantic paper search; returns papers, not numbers.")
    for a in stored_answers():
        with st.expander(f"{a['label']} ({a['date']}, {a['status']})"):
            st.markdown(f"**Question.** {a['query'][:600]}")
            st.markdown(a["answer"][:1800] + (" ..." if len(a["answer"]) > 1800 else ""))
            st.caption("Stored answer. " + VERIFIED)
    st.caption(VALENCY_NOTE)
    st.markdown("**Live Edison question (optional)**")
    if not edison_available():
        return st.caption("The Edison python client is not installed here (pip install edison-client); live questions are off.")
    key = st.text_input("Your Edison API key", type="password", key="edison_key", help="Session only; not saved or logged.")
    q = st.text_area("Question", key="edison_q", height=80)
    ok = st.checkbox("This spends one credit", key="edison_ok")
    if st.button("Ask (plain Literature job)", disabled=not (key and q.strip() and ok), key="edison_go"):
        with st.spinner("Waiting for the agent..."):
            try:
                st.session_state["edison_ans"] = ask_edison(q.strip(), key)
            except Exception as e:  # noqa: BLE001
                st.error(f"Edison call failed: {type(e).__name__}")
    if st.session_state.get("edison_ans"):
        st.markdown(st.session_state["edison_ans"])
        st.caption("Live answer, unverified. " + VERIFIED)


def render(vessel=None, pick=True):
    st.subheader("Literature")
    vessel = vessel or st.session_state.get("vt_vessel", "cvd_tube")
    vs = ["cvd_tube", "ampoule", "flask", "sorbent", "photoreactor"]
    if pick:
        vessel = st.selectbox("Vessel", vs, index=vs.index(vessel) if vessel in vs else 0, key="lit_vessel")
    a, b = st.tabs(["Parameter sources", "Literature agents"])
    with a:
        _sources(vessel)
    with b:
        _agents(vessel)
