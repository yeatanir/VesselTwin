import pathlib, shutil, sys, tempfile
import pytest
import vessels
from core import api, registry


@pytest.mark.vessel("core")
def test_dropped_in_vessel_appears(monkeypatch):
    """Copy the template into a temp dir on vessels.__path__: it must list and solve with no other edit."""
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        shutil.copy(pathlib.Path(vessels.__path__[0]) / "_template.py", tmp / "dropin.py")
        shutil.copy(pathlib.Path(vessels.__path__[0]) / "_template.py", tmp / "_skipped.py")  # '_' names are not loaded
        monkeypatch.setattr(vessels, "__path__", list(vessels.__path__) + [str(tmp)])
        monkeypatch.setattr(registry, "REGISTRY", registry.REGISTRY.copy())  # REGISTRY is mutated by register()
        registry.load_all()
        assert "template_demo" in [v["name"] for v in api.list_vessels()]
        r = api.solve("template_demo", n_mc=10)
        assert r["passport"]["vessel"] == "template_demo" and r["passport"]["synthetic"]
    finally:
        sys.modules.pop("vessels.dropin", None)
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.vessel("core")
def test_preset_meta_ignored():
    info = api.preset_info("sorbent")
    assert info and all("_meta" not in i["params"] and i["source"] for i in info)
    api.solve("sorbent", preset=info[0]["name"], n_mc=3)
