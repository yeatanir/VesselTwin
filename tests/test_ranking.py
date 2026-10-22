import json, re
import pytest
from atomistic import brief as B, ranking as R

VESSELS = ["cvd_tube", "ampoule", "flask", "sorbent"]
_NUM = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:e[+-]?\d+)?(?![\w])")


def _nums(o, acc):
    if isinstance(o, dict):
        [_nums(v, acc) for v in o.values()]
    elif isinstance(o, (list, tuple)):
        [_nums(v, acc) for v in o]
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        acc.add(B._g(float(o)))
        acc.add(str(o))
    return acc


@pytest.fixture(scope="module")
def briefs():
    return {v: B.make_brief(v, n_mc=20) for v in VESSELS}


@pytest.mark.vessel("core")
@pytest.mark.parametrize("vessel", VESSELS)
def test_every_vessel_has_brief(briefs, vessel):
    b = briefs[vessel]
    assert b["conditions"] and b["text"] and B.to_markdown(b).startswith("# Simulation brief")
    assert all(r["low_tail"] is not None for r in b["conditions"])
    assert [r["rank"] for r in b["ranking"]] == list(range(1, len(b["ranking"]) + 1))
    assert all(a["delta"] >= c["delta"] for a, c in zip(b["ranking"], b["ranking"][1:]))
    json.dumps(b)


@pytest.mark.vessel("core")
def test_templates_have_no_literal_numbers():
    for t in list(B.T.values()) + [R.RATIONALE]:
        assert not re.search(r"(?<![\w{])\d", re.sub(r"\{[^}]*\}", "", t)), t


@pytest.mark.vessel("core")
@pytest.mark.parametrize("vessel", VESSELS)
def test_text_numbers_trace_to_solver(briefs, vessel):
    b = briefs[vessel]
    known = _nums({k: v for k, v in b.items() if k != "text"}, set())
    found = set(_NUM.findall(b["text"]))
    assert found - known == set(), found - known


@pytest.mark.vessel("core")
def test_brief_deterministic():
    a, b = B.make_brief("ampoule", n_mc=20, seed=3), B.make_brief("ampoule", n_mc=20, seed=3)
    assert a == b


@pytest.mark.vessel("core")
@pytest.mark.check("ranking_benefit")
@pytest.mark.parametrize("vessel", VESSELS)
def test_top_ranked_beats_random(vessel, capsys):
    """Over 50 draws of actual 1-sigma parameter errors, does the top-ranked calc move the outcome more than a random one?"""
    out = [R.benchmark(vessel, n_seeds=50, pool=p) for p in ("candidates", "all")]
    with capsys.disabled():
        for r in out:
            print(f"\nranking_benefit {r}")
    c, a = out
    assert a["top3_win"] is not None and a["top3_win"] >= 0.8, a  # top-3 atomistic calcs vs median of ALL uncertain params
    assert c["rank1_win"] >= 0.5 if len(R.rank_calculations(vessel)) > 1 else True, c
