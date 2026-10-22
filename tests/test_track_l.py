"""Track L: items.json integrity and scorer wiring (does not run the full benchmark)."""
import json, os
from bench import track_l_score as L, track_a_score as A
from core import params as P
from vessels.cvd_tube import wulff

IT = json.load(open(os.path.join(os.path.dirname(L.__file__), "track_l", "items.json")))


def test_quotes_short_and_present():
    for pid, p in IT["papers"].items():
        for e in p["params"]:
            assert len(e["quote"].split()) <= 40, (pid, e["model_key"])
            if e["value"] is not None:
                assert e["quote"], (pid, e["model_key"])


def test_overrides_are_valid_model_params_and_exclude_swept():
    names = {d.name for d in wulff.DEFS}
    for sid, it in IT["items"].items():
        assert set(it["overrides"]) <= names, sid
        assert A.ITEMS[sid][1] not in it["overrides"], sid
        P.validate(wulff.DEFS, it["overrides"])  # inside bounds


def test_unverified_papers_keep_default_geometry():
    assert IT["items"]["s09"]["overrides"] == {} and "not verified" in IT["flags"]["s09"]


def test_tied_parameter_follows_sweep():  # known answer: T_boat_Mo follows T_furnace, so the item with tie differs from the untied run
    r = L.sens_item("s13", {}, True)
    assert r["n_draws"] > 0 and r["call"] in ("increase", "decrease", "non_monotonic", "no_change", "uncertain")
    assert L.spec("s13")[1] == {"T_boat_Mo_C": "T_furnace_C"}


def test_far_substrate_note():
    assert "farther" in L.notes("s14") and "farther" not in L.notes("s01")
