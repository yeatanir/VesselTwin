from bench import sensitivity_score as S


def test_direction_rules_and_match():
    assert S._dir([1, 2, 3, 4, 5]) == "increase" and S._dir([5, 4, 3, 2, 1]) == "decrease"
    assert S._dir([1, 1.01, 1, 1.01, 1]) == "no_change" and S._dir([1, 3, 5, 3, 1]) == "non_monotonic"
    assert S.match("non_monotonic", "class_change") and not S.match("increase", "decrease")
    rows = [{"status": "modelled", "match": m, "match_strict": m, "uncertain": False, "observed": o, "id": f"s{i}"}
            for i, (m, o) in enumerate([(True, "increase"), (False, "increase"), (True, "decrease")])]
    s = S.summary(rows)
    assert s["correct"] == 2 and s["majority_class"] == "increase" and s["majority_baseline_correct"] == 2
