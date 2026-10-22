"""Harness: every test is tagged @pytest.mark.vessel("x") / .check("name"); results land in harness.json for the dashboard."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

_results = []


def pytest_configure(config):
    config.addinivalue_line("markers", "vessel(name): which vessel (or 'core'/'llm') this test belongs to")
    config.addinivalue_line("markers", "check(name): credibility-test category from the plan")


def pytest_runtest_logreport(report):
    if report.when != "call" and not (report.when == "setup" and report.failed):
        return
    _results.append({"test": report.nodeid, "outcome": report.outcome, "duration": round(report.duration, 4)})


def pytest_collection_modifyitems(items):
    global _marks
    _marks = {i.nodeid: {m.name: (m.args[0] if m.args else "") for m in i.iter_markers()} for i in items}


def pytest_sessionfinish(session):
    for r in _results:
        r.update({k: v for k, v in _marks.get(r["test"], {}).items() if k in ("vessel", "check")})
    out = pathlib.Path(__file__).resolve().parents[1] / "cache" / "harness.json"
    out.write_text(json.dumps(_results, indent=1))
