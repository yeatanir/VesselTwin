import ast
import pytest
from app import custom_vessel as cv


@pytest.mark.parametrize("k", list(cv.TEMPLATES))
def test_clone_solve_label(k):
    f = cv.fields(k)
    assert 6 <= len(f) <= 8
    d0 = f[0]
    e = cv.make(k, "Test Vessel", {d0.name: d0.default}, "notes")
    assert e["id"] == "custom_test_vessel" and e["name"] == "Test Vessel"
    r = cv.run(e, n_mc=4)
    assert r["label"] == "hypothesis" and r["derived"]
    assert r["note"].startswith("Custom vessel: borrowed physics from the ") and r["note"].endswith("not validated for this geometry.")
    ast.parse(cv.stub(e))


def test_user_default_is_applied_and_original_untouched():
    from core.registry import load_all
    e = cv.make("ampoule", "A", {"L_cm": 33.0})
    assert {d.name: d.default for d in e["defs"]}["L_cm"] == 33.0
    assert {d.name: d.default for d in load_all()["ampoule"].defs}["L_cm"] == 15.0
    assert "custom_a" not in load_all()


def test_bounds_rejected():
    with pytest.raises(ValueError):
        cv.make("ampoule", "A", {"L_cm": 1e6})


def test_stub_executes_and_registers():
    e = cv.make("photo", "Stub Photo", {"dist_cm": 6.0})
    ns = {}
    exec(cv.stub(e), ns)
    from core.registry import REGISTRY
    try:
        assert "dist_cm" in REGISTRY["custom_stub_photo"].params
    finally:
        REGISTRY.pop("custom_stub_photo", None)
