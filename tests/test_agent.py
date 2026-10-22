import json
import pytest
from llm import agent as A

pytestmark = pytest.mark.vessel("llm")
Q = "A 1 inch quartz tube furnace with MoO3 at 650 C and 100 sccm Ar. What should I change first?"


def scripted(*outs):
    it = iter(outs)
    f = lambda msgs: next(it)
    f.model, f.backend = "test-model", "test"
    return f


def J(**k):
    return json.dumps(k)


FINAL = {"answer": "a", "change_first": "b", "atomistic_priority": "c", "caveats": "d"}


def test_loop_calls_tools_logs_and_stops_on_final(tmp_path):
    chat = scripted(J(tool="extract_setup", args={"text": Q}),
                    J(tool="solve", args={"vessel": "cvd_tube", "spec": {"flow_sccm": 100}, "tier": 1}),
                    J(tool="lookup_parameter", args={"name": "flow rate"}),
                    J(final=FINAL))
    final, path = A.run_agent(Q, chat, tmp_path)
    assert final == FINAL
    ev = [json.loads(l) for l in path.read_text().splitlines()]
    kinds = [e["kind"] for e in ev]
    assert kinds[0] == "meta" and ev[0]["model"] == "test-model" and kinds.count("tool_call") == 3 and kinds[-1] == "final"
    assert all("seconds" in e for e in ev if e["kind"] in ("model_output", "tool_output"))
    r = A.load_run(path)
    assert [s["tool"] for s in r["steps"]] == ["extract_setup", "solve", "lookup_parameter"] and r["complete"]
    assert "run_id" in json.loads(r["steps"][1]["output"])


def test_schema_violations_bounce_back_and_cost_a_step(tmp_path):
    chat = scripted("not json", J(tool="solve", args={"vessel": "cvd_tube"}), J(tool="nope", args={}), J(final=FINAL))
    final, path = A.run_agent(Q, chat, tmp_path)
    ev = [json.loads(l) for l in path.read_text().splitlines()]
    assert [e["kind"] for e in ev].count("schema_error") == 2 and final == FINAL
    assert any(e["kind"] == "tool_call" and e["schema_errors"] for e in ev)  # missing 'spec'/'tier' reported


def test_max_8_steps(tmp_path):
    chat = scripted(*[J(tool="lookup_parameter", args={"name": "x"})] * 20)
    final, path = A.run_agent(Q, chat, tmp_path)
    ev = [json.loads(l) for l in path.read_text().splitlines()]
    assert final is None and sum(e["kind"] == "model_output" for e in ev) == 8 and ev[-1]["kind"] == "stopped"


def test_unknown_param_and_unknown_run_id_are_errors_not_crashes():
    assert "error" in A._wrap_solve("cvd_tube", {"bogus": 1}, 1)
    assert "error" in A._wrap_rank("nope")


def test_lookup_is_cache_only_known_answer():
    r = A._wrap_lookup("carrier gas flow rate")
    assert r["found"] >= 1 and "10 sccm" in r["excerpts"][0]["excerpt"]
    assert A._wrap_lookup("zzzz-not-a-parameter")["found"] == 0


def test_test_backend_runs_never_reach_the_dashboard(tmp_path):
    A.run_agent(Q, scripted(J(final=FINAL)), tmp_path)
    assert A.recorded_runs(tmp_path) == []


def test_recorded_run_renders_with_recorded_label(tmp_path):
    import pathlib
    from streamlit.testing.v1 import AppTest
    final, path = A.run_agent(Q, scripted(J(tool="solve", args={"vessel": "cvd_tube", "spec": {}, "tier": 0}), J(final=FINAL)), tmp_path)
    run = {**A.load_run(path), "file": path.name}
    at = AppTest.from_file(str(pathlib.Path(__file__).parent / "recorded_app.py"), default_timeout=60)
    at.session_state["run"] = run
    at.run()
    assert not at.exception
    assert any("Recorded run · test-model" in m.value for m in at.markdown) and A.final_label(run) == "hypothesis"
