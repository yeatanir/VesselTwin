"""Sidebar 'LLM settings (optional)'. Values live only in st.session_state (never disk, never logged). Without settings the dashboard is unchanged:
scripted replay and recorded runs need no API."""
import streamlit as st
from llm.backends import PROVIDERS, make_chat, test_connection, LLMError

_KEYS = ("llm_provider", "llm_base_url", "llm_model", "llm_api_key", "llm_hdr_name", "llm_hdr_value")


def _sync():
    """Streamlit drops a widget's state when its page is not rendered, so mirror the values into one plain dict
    (st.session_state['vt_llm'], session only) and restore them when a page shows the widgets again."""
    ss = st.session_state
    store = ss.setdefault("vt_llm", {})
    for k in _KEYS:
        if k in ss:
            store[k] = ss[k]
        elif k in store:
            ss[k] = store[k]


def active():
    """Short label of what is configured, for captions: 'offline' or 'provider / model'."""
    _sync()
    s = st.session_state
    if s.get("llm_provider", "rules") == "rules" and _demo_cfg():
        return "hosted demo model (limited)"
    return "offline" if s.get("llm_provider", "rules") == "rules" else f"{s['llm_provider']} / {s.get('llm_model') or 'default model'}"


def _demo_cfg():
    """Hosted demo model from Streamlit secrets (section [vt_demo_llm]); None when not configured. The key stays in st.secrets only."""
    try:
        c = st.secrets.get("vt_demo_llm")
        return dict(c) if c and c.get("api_key") else None
    except Exception:  # no secrets file, or running locally
        return None


def demo_status():
    """One line for the UI: is the hosted demo model on, and if not, why (no key values are ever shown)."""
    try:
        sec = st.secrets.get("vt_demo_llm")
    except Exception:  # noqa: BLE001
        sec = None
    if not sec:
        return "Hosted demo model: off (no [vt_demo_llm] secret found)"
    if not sec.get("api_key") or str(sec.get("api_key")).strip() in ("", "YOUR_KEY"):
        return "Hosted demo model: off (api_key not set)"
    return f"Hosted demo model: on ({sec.get('model', 'default model')}, {int(sec.get('max_calls_per_session', 24))} calls per session)"


@st.cache_resource
def _demo_total():
    return {"n": 0}


def demo_chat():
    """Rate-limited chat on the site owner's model, for visitors who bring no key of their own: a per-session and a per-process cap on calls."""
    cfg = _demo_cfg()
    if not cfg:
        return None
    per_session, total = int(cfg.get("max_calls_per_session", 24)), int(cfg.get("max_calls_total", 400))
    hdr = {"anthropic-workspace-id": cfg["workspace_id"]} if cfg.get("workspace_id") else None
    real = make_chat(cfg.get("provider", "anthropic"), cfg.get("base_url") or None, cfg["api_key"], cfg.get("model") or None, hdr)

    def chat(msgs):
        ss, tot = st.session_state, _demo_total()
        if ss.get("vt_demo_calls", 0) >= per_session or tot["n"] >= total:
            raise LLMError("The hosted demo model's limit is reached for this session. Connect your own model under LLM settings, or replay a recorded run.")
        ss["vt_demo_calls"] = ss.get("vt_demo_calls", 0) + 1
        tot["n"] += 1
        return real(msgs)
    chat.model, chat.backend = real.model, f"{real.backend} (hosted demo, limited)"
    return chat


def get_chat():
    """chat callable from the session settings, or None (rules/offline). Raises LLMError on a bad configuration."""
    _sync()
    s = st.session_state
    p = s.get("llm_provider", "rules")
    if p == "rules":
        return demo_chat()  # None unless the site owner configured a hosted demo model
    hdr = {s["llm_hdr_name"].strip(): s.get("llm_hdr_value", "")} if s.get("llm_hdr_name", "").strip() else None
    return make_chat(p, s.get("llm_base_url") or None, s.get("llm_api_key") or None, s.get("llm_model") or None, hdr)


def _models():
    try:
        from llm.agent import recorded_runs
        return sorted({r["model"] for r in recorded_runs()})
    except Exception:
        return []


def render(container=None):
    """Settings expander; sidebar by default so it looks the same on every page. Safe to call from any page."""
    _sync()
    with (container if container is not None else st.sidebar).expander("LLM settings (optional)"):
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
        _sync()
        m = _models()
        st.caption(f"Recorded runs were produced with {', '.join(m) if m else 'a model recorded in each trace'}; replay needs no API.")
