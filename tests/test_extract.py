import pytest
from bench.score import load, score
import json
from core import params as P
from core.registry import load_all
from llm.extract import extract, extract_and_solve, json_schema, detect_vessel
from llm.span_check import fabricated
from schemas.setupspec import Status

pytestmark = [pytest.mark.vessel("llm"), pytest.mark.check("extraction_accuracy")]
T = "MoS2 was grown in a 1 inch quartz tube furnace with 100 sccm Ar; MoO3 at 700 °C."


def fake(*items):  # injected backend (callable)
    return lambda text, vessel: [dict(key=k, value=v, unit=u, span=s) for k, v, u, s in items]


@pytest.mark.parametrize("which,min_prec", [("syn", 0.95), ("real", 0.9)])
def test_rules_zero_fabricated_on_bench(which, min_prec):
    procs = load(which)
    assert len(procs) >= 12
    r = score("rules", procs)["overall"]
    assert r["fabricated"] == 0 and r["unit_errors"] == 0 and r["precision"] >= min_prec
    for p in procs:
        assert fabricated(extract(p["text"], p["vessel"]), p["text"]) == 0


def test_vessel_detection():
    assert all(detect_vessel(p["text"]) == p["vessel"] for p in load("syn"))


def test_hallucinated_value_rejected():
    s = extract(T, "cvd_tube", backend=fake(("flow_sccm", 250.0, "sccm", "100 sccm Ar"), ("T_furnace_C", 800.0, "C", "furnace at 800 C")))
    assert s.params["flow_sccm"].status is Status.missing and "rejected" in s.params["flow_sccm"].note
    assert s.params["T_furnace_C"].status is Status.missing


def test_invented_key_dropped_and_missing_stays_missing():
    s = extract(T, "cvd_tube", backend=fake(("magic", 1.0, None, "1 inch")))
    assert "magic" not in s.params and s.params["T_boat_S_C"].status is Status.missing and s.params["T_boat_S_C"].value is None
    assert set(s.params) == set(load_all()["cvd_tube"].params)


def test_out_of_bounds_bounces():
    s = extract("The tube was 40 inch wide.", "cvd_tube", backend=fake(("tube_id_in", 40.0, "inch", "40 inch")))
    assert s.params["tube_id_in"].status is Status.missing and "bounds" in s.params["tube_id_in"].note
    s = extract("flow of 1 m long", "cvd_tube", backend=fake(("flow_sccm", 1.0, "m", "1 m")))  # wrong dimension
    assert s.params["flow_sccm"].status is Status.missing


def test_unit_conversion_to_canonical():
    s = extract("A 25.4 mm i.d. tube was used.", "cvd_tube")
    vals, prov = P.from_spec(load_all()["cvd_tube"].defs, s)
    assert vals["tube_id_in"] == pytest.approx(1.0) and prov["tube_id_in"] == "stated"
    s = extract(T, "cvd_tube")
    assert s.params["tube_id_in"].value == 1 and s.params["flow_sccm"].value == 100 and s.params["carrier"].value == "Ar"


def test_defaults_only_from_paramdef():
    s = extract(T, "cvd_tube", fill_defaults=True)
    d = load_all()["cvd_tube"]
    for k, f in s.params.items():
        if f.status is Status.default:
            assert f.value == next(x.default for x in d.defs if x.name == k)


def test_schema_enum_and_no_key():
    sc = json_schema("flask")
    assert sc["properties"]["fields"]["items"]["properties"]["key"]["enum"] == load_all()["flask"].params
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        extract(T, backend="anthropic")


def test_extract_and_solve():
    out = extract_and_solve(T)
    assert out["provenance"]["flow_sccm"] == "stated" and out["spec"]["vessel"] == "cvd_tube"


def test_units_and_ranges_and_offsets():
    d = load_all()
    v = lambda ves, t: P.from_spec(d[ves].defs, extract(t, ves))[0]
    assert v("ampoule", "I2 at 5 mg cm-3 in a 12 cm long ampoule")["agent_mg_per_cm3"] == pytest.approx(5)
    assert v("ampoule", "I2 at 2 g/L in a 12 cm long ampoule")["agent_mg_per_cm3"] == pytest.approx(2)
    assert v("sorbent", "feed of 30 mL/min in a column")["flow_sccm"] == pytest.approx(30)
    assert v("sorbent", "measured at 25 °C and 1 bar")["T_K"] == pytest.approx(298.15)
    s = extract("The furnace was held at 600 to 850 °C under 150-300 sccm Ar.", "cvd_tube")
    assert s.params["T_furnace_C"].status is Status.missing and s.params["flow_sccm"].status is Status.missing
    s = extract("The tube was purged at 500 sccm. Then flow was 40 sccm.", "cvd_tube")
    assert s.params["flow_sccm"].value == 40


def test_replay_backend(tmp_path):
    t = "A 1 inch tube with 100 sccm Ar."
    (tmp_path / "x.json").write_text(json.dumps({"vessel": "cvd_tube", "fields": [
        {"key": "flow_sccm", "value": "100", "unit": "sccm", "span": "100 sccm"},
        {"key": "T_furnace_C", "value": "900", "unit": "C", "span": "900 C"}]}))  # second one is fabricated
    s = extract(t, "cvd_tube", backend="replay", runs_dir=str(tmp_path), name="x")
    assert s.params["flow_sccm"].value == 100 and s.params["T_furnace_C"].status is Status.missing
