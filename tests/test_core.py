import pytest
from pydantic import ValidationError
from core import dimensionless as d
from core.pipeline import run
from core.registry import load_all
from llm.span_check import check_spec, fabricated
from llm.units import to_unit
from schemas.setupspec import Field, SetupSpec, Status

TEXT = "The flask was stirred at 400 rpm with a 25 mm bar."


@pytest.mark.vessel("core")
@pytest.mark.check("analytic_limit")
def test_dimensionless_known_values():
    assert d.reynolds(1000, 1, 1, 1e-3) == pytest.approx(1e6)
    assert d.rayleigh(1, 1, 1, 1, 1) == pytest.approx(d.G)
    assert d.classify(100)[0] is d.Regime.transport_limited
    assert d.classify(0.01)[0] is d.Regime.reaction_limited
    assert d.classify(1.5)[1] < 1  # ambiguity band flagged


@pytest.mark.vessel("llm")
@pytest.mark.check("extraction_accuracy")
def test_span_check_rejects_fabrication():
    good = Field(value=400, unit="rpm", span="400 rpm", status=Status.stated)
    bad = Field(value=500, unit="rpm", span="400 rpm", status=Status.stated)   # number not in span
    ghost = Field(value=25, unit="mL", span="25 mL", status=Status.stated)     # span not in text
    spec = SetupSpec(vessel="flask", params={"a": good, "b": bad, "c": ghost})
    assert fabricated(spec, TEXT) == 2
    out = check_spec(spec, TEXT)
    assert fabricated(out, TEXT) == 0
    assert out.params["a"].status is Status.stated
    assert out.params["b"].status is out.params["c"].status is Status.missing


@pytest.mark.vessel("llm")
def test_field_invariants():
    for bad in (dict(status="stated", value=1), dict(status="missing", value=1), dict(status="default")):
        with pytest.raises(ValidationError):
            Field(**bad)


@pytest.mark.vessel("llm")
def test_units_bounce():
    assert to_unit(1, "inch", "mm") == pytest.approx(25.4)
    with pytest.raises(Exception):
        to_unit(1, "inch", "K")


@pytest.mark.vessel("core")
@pytest.mark.parametrize("name", ["cvd_tube", "ampoule", "flask", "sorbent"])
def test_empty_case_runs_every_stage(name):
    out = run(SetupSpec(vessel=name, params={}, synthetic=True), n_mc=4)
    assert out["passport"]["synthetic"]  # default sets carry synthetic params until sourced


@pytest.mark.vessel("core")
def test_unknown_param_rejected():
    load_all()
    f = Field(value=1.0, status=Status.default)
    with pytest.raises(ValueError):
        run(SetupSpec(vessel="flask", params={"warp_factor": f}))
