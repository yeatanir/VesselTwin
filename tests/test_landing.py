import pathlib
from streamlit.testing.v1 import AppTest
from app import landing

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_copy_limits():
    assert len(landing.COPY["headline"].split()) <= 10
    for k, v in landing.COPY.items():
        if k != "headline":
            assert len(v.split()) <= 14, k
    for key, title, line, chip, _ in landing.VESSELS:
        assert len(line.split()) <= 14 and len(chip.split()) <= 14, key


def test_footer_and_trust_text():
    f = landing.COPY["footer"]
    for part in ("VesselTwin", "Anirban Phukan", "MIT License", "github.com/yeatanir/VesselTwin"):
        assert part in f
    assert "Valency" in landing.COPY["thanks"] and "Edison Scientific" in landing.COPY["thanks"]
    assert landing.COPY["proto"] == "Research prototype"


def test_icons_distinct_and_hero_has_all_parts():
    svgs = {v[0]: landing.icon(v[0]) for v in landing.VESSELS}
    assert len(set(svgs.values())) == 5 and all(s.startswith("<svg") for s in svgs.values())
    h = landing.hero_svg()
    for w in ("RECIPE", "WHICH KNOB MATTERS", "WHICH CALCULATION", "offset-path"):
        assert w in h


def test_five_vessels_and_trust_numbers():
    assert len(landing.VESSELS) == 5
    assert "blind agent" in landing.trust_facts()


def _page():
    from app import landing
    landing.render()


def test_landing_renders():
    at = AppTest.from_function(_page, default_timeout=30).run()
    assert not at.exception
    assert [b.key for b in at.button if b.key.startswith("open_")] == [f"open_{v[0]}" for v in landing.VESSELS]


def test_entry_point_and_navigation():
    at = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=60).run()
    assert not at.exception
    assert any(b.key == "open_sorbent" for b in at.button)
    from app import theme
    assert set(theme.PAGES) == {"Home", "Workspace", "Evidence", "Advanced"}
