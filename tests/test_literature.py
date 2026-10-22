import sys, types, pathlib
from streamlit.testing.v1 import AppTest
from app import literature as L

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_param_sources_classified():
    rows = L.param_sources("cvd_tube")
    assert {r["kind"] for r in rows} >= {"sourced", "synthetic"}
    assert all(r["kind"] != "sourced" or r["source"] not in ("default", "synthetic") for r in rows)


def test_stored_answers_have_question_and_date():
    a = L.stored_answers()
    assert a and all(x["query"] and x["date"] and x["status"] for x in a)


def test_ask_edison_uses_literature_job_only(monkeypatch):
    seen = {}

    class JobNames:
        LITERATURE = "job-literature"
        LITERATURE_HIGH = "high"

    class EdisonClient:
        def __init__(self, api_key):
            seen["key"] = api_key

        def run_tasks_until_done(self, req):
            seen["req"] = req
            return [types.SimpleNamespace(answer="fake answer")]
    m = types.ModuleType("edison_client")
    m.EdisonClient, m.JobNames = EdisonClient, JobNames
    monkeypatch.setitem(sys.modules, "edison_client", m)
    assert L.edison_available()
    assert L.ask_edison("q?", "K") == "fake answer"
    assert seen["req"]["name"] == "job-literature"


def test_evidence_page_has_literature_and_llm_settings():
    at = AppTest.from_file(str(ROOT / "tests" / "ev_app.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    assert "Literature" in [t.label for t in at.tabs]
    assert at.sidebar.text_input(key="llm_api_key").proto.type == 1


def test_llm_settings_survive_page_without_widgets():
    def app():
        import streamlit as st
        from app import llm_settings as S
        if st.session_state.get("show"):
            S.render()
        st.write(S.active())
    at = AppTest.from_function(app, default_timeout=60)
    at.session_state["show"] = True
    at.run()
    at.sidebar.selectbox(key="llm_provider").set_value("openai_compatible").run()
    at.session_state["show"] = False
    at.run()  # page without the widgets: values must come from the store
    assert "openai_compatible" in at.markdown[0].value
