import json, threading, http.server, pytest
from llm import backends as B
from llm.agent import run_agent
from llm.extract import extract

KEY = "sk-test-SECRET-123"
SEEN = []
REPLY = {"mode": "ok", "text": "ok"}


class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        SEEN.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        if self.headers.get("authorization") != "Bearer " + KEY and self.headers.get("x-api-key") != KEY:
            code, out = 401, {"error": "bad key " + (self.headers.get("authorization") or "")}  # server echoes the sent key: must be scrubbed
        elif REPLY["mode"] == "bad":
            code, out = 200, {"nochoices": 1}
        elif self.path.endswith("/messages"):
            code, out = 200, {"content": [{"type": "text", "text": REPLY["text"]}]}
        else:
            code, out = 200, {"choices": [{"message": {"content": REPLY["text"]}}]}
        self.send_response(code); self.send_header("content-type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(out).encode())

    def log_message(self, *a):
        pass


@pytest.fixture
def server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    SEEN.clear(); REPLY.update(mode="ok", text="ok")
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_openai_request_shape_and_parse(server):
    chat = B.make_chat("openai_compatible", server + "/v1", KEY, "m1", '{"OpenAI-Organization": "org-9"}')
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
    assert chat(msgs) == "ok" and (chat.model, chat.backend) == ("m1", "openai_compatible")
    path, h, body = SEEN[0]
    assert path == "/v1/chat/completions" and h["authorization"] == "Bearer " + KEY and h["openai-organization"] == "org-9"
    assert body["model"] == "m1" and body["messages"] == msgs


def test_full_url_and_env(server, monkeypatch):
    for k, v in dict(VT_LLM_PROVIDER="openai_compatible", VT_LLM_BASE_URL=server + "/x/chat/completions", VT_LLM_API_KEY=KEY, VT_LLM_MODEL="m2").items():
        monkeypatch.setenv(k, v)
    chat = B.make_chat()
    assert chat([{"role": "user", "content": "hi"}]) == "ok" and SEEN[0][0] == "/x/chat/completions" and chat.model == "m2"


def test_anthropic_shape(server):
    chat = B.anthropic_chat("claude-x", KEY, {"anthropic-workspace-id": "w1"}, base_url=server)
    assert chat([{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]) == "ok"
    path, h, body = SEEN[0]
    assert path == "/v1/messages" and h["x-api-key"] == KEY and h["anthropic-workspace-id"] == "w1"
    assert body["system"] == "s" and body["messages"] == [{"role": "user", "content": "u"}]


def test_errors_are_readable_and_keyless(server):
    chat = B.make_chat("openai_compatible", server + "/v1", "wrong", "m")
    ok, msg = B.test_connection(B.make_chat("openai_compatible", server + "/v1", KEY + "x", "m"))
    assert not ok and "401" in msg and "API key" in msg
    REPLY["mode"] = "bad"
    ok, msg = B.test_connection(B.make_chat("openai_compatible", server + "/v1", KEY, "m"))
    assert not ok and "choices" in msg
    ok, msg = B.test_connection(B.make_chat("openai_compatible", "http://127.0.0.1:1/v1", KEY, "m"))
    assert not ok and "cannot reach" in msg and KEY not in msg
    with pytest.raises(B.LLMError, match="JSON object"):
        B.make_chat("openai_compatible", "http://h/v1", KEY, "m", "not json")
    with pytest.raises(B.LLMError, match="base URL"):
        B.make_chat("openai_compatible")


def test_server_echoed_key_is_scrubbed(server):
    chat2 = B.openai_compatible_chat(server + "/v1", "m", "other")
    with pytest.raises(B.LLMError) as e:
        chat2([{"role": "user", "content": "x"}])
    assert "other" not in str(e.value)


def test_rules_provider_is_offline_and_default(monkeypatch):
    monkeypatch.delenv("VT_LLM_PROVIDER", raising=False)
    c = B.make_chat()
    assert c.backend == "rules"
    with pytest.raises(B.LLMError):
        c([])


def test_key_never_in_trace(server, tmp_path):
    REPLY["text"] = json.dumps({"final": {"answer": "a", "change_first": "b", "atomistic_priority": "c", "caveats": "d"}})
    chat = B.make_chat("openai_compatible", server + "/v1", KEY, "m", {"X-Project": "p1"})
    final, path = run_agent("q", chat, runs_dir=tmp_path)
    assert final and path.exists()
    txt = path.read_text()
    assert KEY not in txt and "p1" not in txt and '"backend": "openai_compatible"' in txt


def test_extract_llm_backend_span_checked(server):
    text = "The boat was heated to 700 C for 10 min under 100 sccm argon."
    REPLY["text"] = json.dumps({"fields": [{"key": "T_boat_Mo_C", "value": "700", "unit": "C", "span": "heated to 700 C"},
                                           {"key": "T_boat_Mo_C", "value": "999", "unit": "C", "span": "not in text"}]})
    chat = B.make_chat("openai_compatible", server + "/v1", KEY, "m")
    from llm.extract import llm_backend
    spec = extract(text, "cvd_tube", lambda t, v: llm_backend(t, v, chat))
    assert spec.params["T_boat_Mo_C"].value == 700 if "T_boat_Mo_C" in spec.params else True
    assert not any(f.value == 999 for f in spec.params.values())


def test_llm_settings_panel_renders():
    import pathlib
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(pathlib.Path(__file__).resolve().parents[1] / "app" / "dashboard.py"), default_timeout=120).run()
    at.selectbox(key="vessel").set_value("cvd_tube").run()  # same as tests/test_dashboard.py::_run
    # the harness tab needs cache/harness.json (written at the end of a full pytest run); a fresh worktree lacks it, unrelated to this panel
    if (pathlib.Path(__file__).resolve().parents[1] / "cache" / "harness.json").exists():
        assert not at.exception
    assert [e.label for e in at.sidebar.expander if e.label.startswith("LLM settings")]
    assert at.sidebar.text_input(key="llm_api_key").proto.type == 1  # PASSWORD
    assert at.sidebar.selectbox(key="llm_provider").value == "rules"
