"""Extraction benchmark. python -m bench.score [--backend rules|replay] [--runs DIR] [--set real|syn|all] [-v]
Gold: {text, vessel, gold:{param:{value,unit}}}. Precision = correct stated / stated; recall = correct / gold fields.
unit_errors = stated field whose key is in gold but canonical value differs (or unit/dimension error).
extra = stated, correct-key-absent-from-gold (counts against precision; may be gold gaps, see -v).
fabricated = stated fields failing span check on the RAW backend output (target 0)."""
import argparse, glob, json, os
from core.registry import load_all
from llm import extract as X
from llm.span_check import fabricated
from schemas.setupspec import Field, SetupSpec, Status

HERE = os.path.dirname(os.path.abspath(__file__))


def load(which="all"):
    pat = {"real": "real_*", "syn": "syn_*", "all": "*"}[which]
    return [json.load(open(f)) | {"name": os.path.basename(f)[:-5]} for f in sorted(glob.glob(f"{HERE}/procedures/{pat}.json"))]


def _items(backend, p, runs):
    if backend == "replay":
        f = os.path.join(runs, p["name"] + ".json")
        return X.replay_backend(p["text"], p["vessel"], f) if os.path.exists(f) else []
    return X.BACKENDS[backend](p["text"], p["vessel"]) if isinstance(backend, str) else backend(p["text"], p["vessel"])


def _zero():
    return dict(procedures=0, gold_fields=0, stated=0, correct=0, unit_errors=0, extra=0, fabricated=0, rejected=0)


def score(backend="rules", procs=None, runs=None, verbose=False) -> dict:
    """Returns {'overall': {...}, vessel: {...}}; each with precision/recall."""
    tot = {"overall": _zero()}
    log = []
    for p in procs if procs is not None else load("all"):
        by = {d.name: d for d in load_all()[p["vessel"]].defs}
        items = _items(backend, p, runs)
        raw = SetupSpec(vessel=p["vessel"], params={i["key"]: Field(value=i["value"], unit=i.get("unit"), span=i["span"], status=Status.stated)
                                                    for i in items if i["key"] in by})
        spec = X.build_spec(p["text"], p["vessel"], items)
        for first, t in enumerate((tot["overall"], tot.setdefault(p["vessel"], _zero()))):
            t["procedures"] += 1
            t["gold_fields"] += len(p["gold"])
            t["fabricated"] += fabricated(raw, p["text"])
            t["rejected"] += sum(1 for f in spec.params.values() if (f.note or "").startswith("rejected"))
            for k, f in spec.params.items():
                if f.status is not Status.stated:
                    continue
                t["stated"] += 1
                g = p["gold"].get(k)
                if g is None:
                    t["extra"] += 1
                    first or log.append((p["name"], "extra", k, f.value, f.unit, f.span))
                    continue
                d = by[k]
                try:
                    ok = f.value == g["value"] if d.choices is not None else abs(X.canonical(d, f.value, f.unit) - X.canonical(d, g["value"], g.get("unit") or None)) <= 1e-6 * max(1, abs(g["value"]))
                except Exception:
                    ok = False
                t["correct"] += ok
                if not ok:
                    t["unit_errors"] += 1
                    first or log.append((p["name"], "wrong", k, f.value, f.unit, f"gold {g['value']} {g.get('unit')}"))
    for t in tot.values():
        t["precision"] = round(t["correct"] / max(t["stated"], 1), 3)
        t["recall"] = round(t["correct"] / max(t["gold_fields"], 1), 3)
    if verbose:
        tot["_log"] = log
    return tot


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="rules")
    ap.add_argument("--runs")
    ap.add_argument("--set", default="all", choices=["real", "syn", "all"])
    ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    for w in (["real", "syn"] if a.set == "all" else [a.set]):
        r = score(a.backend, load(w), a.runs, a.v)
        print(f"== {w} ({a.backend}) ==")
        for k, t in r.items():
            if k == "_log":
                for row in t:
                    print("  ", *row)
            else:
                print(f"{k:9}", {x: t[x] for x in ("procedures", "gold_fields", "stated", "correct", "precision", "recall", "unit_errors", "extra", "fabricated", "rejected")})
