"""Capture the LEGACY cvd_tube behaviour (before Track N touches vessels/cvd_tube/__init__.py) -> bench/track_n/default_reference.json.
Run once; the test tests/test_track_n.py compares exact floats (JSON round-trips Python floats exactly)."""
import json, os
import numpy as np
from core import params as P, uq
from core.registry import load_all
from vessels import cvd_tube as T
from vessels.cvd_tube import growth, wulff

CASES = [{}, {"flow_sccm": 50.0}, {"tube_id_in": 2.0, "flow_sccm": 400.0, "T_furnace_C": 850.0}, {"carrier": "H2", "x_substrate_cm": 6.0},
         {"substrate_uptake_model": "reactive", "wall_uptake_model": "sticking"}, {"x_S_boat_cm": 20.0, "x_MoO3_cm": 45.0, "L_hot_cm": 20.0, "ramp_cm": 6.0}]


def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, np.ndarray): return clean(o.tolist())
    if isinstance(o, (np.floating, np.integer)): return o.item()
    if hasattr(o, "value") and not isinstance(o, (int, float, str)): return o.value
    return o


def capture():
    out = []
    for c in CASES:
        v = P.validate(wulff.DEFS, c)
        x, Tt, o, m = T.march(v)
        r, mg, nums = T.tier0(v)
        out.append(clean({"case": c, "x": x, "T": Tt, "o": {k: o[k] for k in ("pM", "pS", "ss", "ssg", "flux", "Tg", "Nt", "NM", "NS")},
                          "m": {k: m[k] for k in ("NM_in", "NS_in", "NM_out", "NS_out", "err", "isub", "xcen", "buoy", "dx", "d", "flow")}, "solve": T.solve(v),
                          "profile": T.profile(v), "tier0": [r.value, mg, nums], "state": growth.state(v),
                          "twall": T.twall(v, np.linspace(0, 1.0, 101))}))
    reg = load_all()["cvd_tube"]
    pas = reg.tier1(P.validate(reg.defs, {}), n=30, seed=0)
    out.append(clean({"mc_passport": json.loads(pas.model_dump_json())}))
    return out


if __name__ == "__main__":
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "default_reference.json")
    json.dump(capture(), open(f, "w"))
    print("wrote", f, os.path.getsize(f))
