import pathlib
import pytest
from streamlit.testing.v1 import AppTest

APP = str(pathlib.Path(__file__).parent / "brief_tab_app.py")


@pytest.mark.vessel("core")
@pytest.mark.parametrize("vessel", ["ampoule", "cvd_tube"])
def test_brief_tab_renders(vessel):
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["vessel"] = vessel
    at.run()
    assert not at.exception
    assert len(at.dataframe) >= 2 and at.warning  # conditions + ranking tables, SYNTHETIC banner
    assert "Simulation brief" in at.markdown[0].value
