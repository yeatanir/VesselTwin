"""Hosted demo model: capped per session and per process; the key never enters session state."""
import pytest
from streamlit.testing.v1 import AppTest

APP = '''
import streamlit as st
from app import llm_settings as L
import llm.backends as B
_orig = (L._demo_cfg, L.make_chat)
L._demo_cfg = lambda: {"provider": "openai_compatible", "base_url": "http://x/v1", "model": "m", "api_key": "SECRET-KEY-123", "max_calls_per_session": 2, "max_calls_total": 5}
def fake(*a, **k):
    def c(msgs): return "ok"
    c.model, c.backend = "m", "openai_compatible"
    return c
L.make_chat = fake
c = L.get_chat()
out = []
for _ in range(3):
    try: out.append(c([{"role": "user", "content": "hi"}]))
    except B.LLMError as e: out.append("LIMIT")
st.write(" ".join(out)); st.write(c.backend); st.write(L.active()); st.write(str(dict(st.session_state)))
L._demo_cfg, L.make_chat = _orig  # AppTest runs in-process: do not leak the patch into other tests
'''


def test_demo_chat_is_capped_and_keyless_in_session():
    at = AppTest.from_string(APP, default_timeout=60).run()
    assert not at.exception
    txt = " ".join(m.value for m in at.markdown)
    assert "LIMIT" in txt and "hosted demo" in txt
    assert "SECRET-KEY-123" not in txt
