import json
import pytest
from bench import shape_score as S

L = ["triangle", "truncated_triangle", "hexagon", "mixed", "other"]


def test_score_hand_case():
    refs = ["triangle", "triangle", "triangle", "hexagon", "mixed"]
    preds = ["triangle", "hexagon", None, "hexagon", "triangle"]
    r = S.score(refs, preds, L)
    assert r["accuracy"] == pytest.approx(2 / 5)  # abstention counts as wrong
    assert r["majority_class"] == "triangle" and r["majority_baseline"] == pytest.approx(3 / 5)
    assert r["answered"] == 4 and r["accuracy_answered"] == pytest.approx(2 / 4)
    c = r["confusion"]
    assert c["triangle"]["triangle"] == 1 and c["triangle"]["hexagon"] == 1 and c["triangle"]["abstain"] == 1
    assert c["hexagon"]["hexagon"] == 1 and c["mixed"]["triangle"] == 1
    assert sum(sum(row.values()) for row in c.values()) == 5


def test_labels_and_provenance_well_formed():
    d = S.load()
    ids = [c["id"] for c in d["cases"]]
    assert len(ids) == len(set(ids)) >= 12
    for c in d["cases"]:
        assert c["reported"]["label"] in L and c["figure"]["label"] in L + [None]
        assert c["doi"] and c["licence"] and c["reported"]["phrase"] in (c["reported"]["phrase"],)
        assert all(m["span"] for m in c["manual"])  # every manual completion quotes the paper


def test_stored_inputs_and_predictions_reproduce():
    inputs = json.load(open(f"{S.SH}/inputs.json"))
    preds = json.load(open(f"{S.SH}/predictions.json"))
    for c in S.load()["cases"]:
        inp = S.build_inputs(c)
        assert inp == inputs[c["id"]]
        p = S.predict(inp["values"])
        assert {k: p[k] for k in ("label", "abstain")} == {k: preds[c["id"]][k] for k in ("label", "abstain")}
