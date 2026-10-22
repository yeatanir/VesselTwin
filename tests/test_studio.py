import json
from streamlit.testing.v1 import AppTest


def _page():
    from app import studio
    studio.render()


def _fake_chat():
    final = {"final": {"answer": "A1", "change_first": "C1", "atomistic_priority": "P1", "caveats": "V1"}}

    def chat(msgs):
        return json.dumps(final)
    chat.model, chat.backend = "fake-model", "test"
    return chat


def _click(at, key):
    next(b for b in at.button if b.key == key).click()
    return at.run()


def test_replay_without_provider(monkeypatch):
    from app import studio
    monkeypatch.setattr(studio, "STEP_DELAY", 0)
    at = AppTest.from_function(_page, default_timeout=60).run()
    assert not at.exception
    at = _click(at, "studio_ex_real_01_cvd_tube")
    assert "tube furnace" in at.text_area[0].value
    at = _click(at, "studio_run")
    assert not at.exception
    html = " ".join(m.value for m in at.markdown) + " ".join(str(getattr(e, "proto", "")) for e in at.get("html"))
    assert "No model connected" in html and "extract_setup" in html and "hypothesis" in html
    assert any("Recorded run" in c.value for c in at.caption)


def test_live_with_fake_provider(monkeypatch):
    from app import llm_settings
    monkeypatch.setattr(llm_settings, "get_chat", _fake_chat)
    at = AppTest.from_function(_page, default_timeout=60).run()
    at.text_area[0].set_value("Some procedure text").run()
    at = _click(at, "studio_run")
    assert not at.exception and not at.error
    html = " ".join(str(e.proto) for e in at.get("html"))
    assert "A1" in html and "V1" in html and "Live run" in html and "No model connected" not in html


def test_add_vessel_wizard():
    at = AppTest.from_function(_page, default_timeout=60).run()
    at = _click(at, "studio_pick_ampoule")
    at = _click(at, "studio_create")
    assert not at.exception
    html = " ".join(str(e.proto) for e in at.get("html"))
    assert "borrowed physics from the Sealed ampoule model" in html
    assert any(b.proto.label == "Download vessel stub" for b in at.get("download_button")) if hasattr(at, "get") else True
