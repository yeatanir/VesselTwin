"""Sidebar 'LLM settings (optional)'. Values live only in st.session_state (never disk, never logged). Without settings the dashboard is unchanged:
scripted replay and recorded runs need no API."""
import streamlit as st
from llm.backends import PROVIDERS, make_chat, test_connection, LLMError

_KEYS = ("llm_provider", "llm_base_url", "llm_model", "llm_api_key", "llm_hdr_name", "llm_hdr_value")


def get_chat():
    """chat callable from the session settings, or None (rules/offline). Raises LLMError on a bad configuration."""
    s = st.session_state
    p = s.get("llm_provider", "rules")
    if p == "rules":
        return None
    hdr = {s["llm_hdr_name"].strip(): s.get("llm_hdr_value", "")} if s.get("llm_hdr_name", "").strip() else None
    return make_chat(p, s.get("llm_base_url") or None, s.get("llm_api_key") or None, s.get("llm_model") or None, hdr)


def _models():
    try:
        from llm.agent import recorded_runs
        return sorted({r["model"] for r in recorded_runs()})
    except Exception:
        return []


def render():
    with st.expander("LLM settings (optional)"):
        st.selectbox("Provider", PROVIDERS, index=PROVIDERS.index("rules"), key="llm_provider",
                     help="rules = fully offline, no API. openai_compatible = any server with an OpenAI-style /v1 endpoint.")
        st.text_input("Base URL", key="llm_base_url", placeholder="https://host/v1", help="Ends in /v1 or is the full /chat/completions URL.")
        st.text_input("Model", key="llm_model")
        st.text_input("API key", key="llm_api_key", type="password", help="Kept in this browser session only; not saved or logged.")
        c = st.columns(2)
        c[0].text_input("Extra header name", key="llm_hdr_name", placeholder="OpenAI-Organization")
        c[1].text_input("Extra header value", key="llm_hdr_value", help="e.g. organisation, workspace or project ID.")
        if st.button("Test connection"):
            try:
                chat = get_chat()
                ok, msg = (False, "provider is 'rules': nothing to test (offline mode)") if chat is None else test_connection(chat)
            except LLMError as e:
                ok, msg = False, str(e)
            (st.success if ok else st.error)(msg)
        m = _models()
        st.caption(f"Recorded runs were produced with {', '.join(m) if m else 'a model recorded in each trace'}; replay needs no API.")
