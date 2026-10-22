"""CLI: python -m core.solve cvd_tube --set T_boat_Mo_C=720 --set x_substrate_cm=15 [--preset name] [--n 50] [--json]"""
import argparse, json
from core import api


def _val(s):
    try:
        return float(s)
    except ValueError:
        return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("vessel")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VAL")
    ap.add_argument("--preset")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    o = api.solve(a.vessel, {k: _val(v) for k, v in (kv.split("=", 1) for kv in a.set)},
                  preset=a.preset, n_mc=a.n)
    if a.json:
        print(json.dumps(o, default=float))
    else:
        print(f"{o['vessel']}: {o['regime']} (margin {o['margin']:.2f})  synthetic={o['passport']['synthetic']}")
        print({k: round(float(v), 4) for k, v in o["numbers"].items()})
        for k, d in [("T_K", o["passport"]["T_K"])] + list(o["passport"]["derived"].items()):
            print(f"  {k:28s} p05={d['p05']:.4g} p50={d['p50']:.4g} p95={d['p95']:.4g} {d['unit']}")
