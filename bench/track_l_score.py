"""Track L scoring, exactly as pre-registered in docs/prereg/track-l.md. python -m bench.track_l_score [--write]
Re-scores the sensitivity benchmark with each paper's own stated geometry (bench/track_l/items.json). Reuses bench.track_a_score (MC, call rules)
and bench.track_i_score.tables. Nothing here is tuned; psat_model default and smolik_liquid_cc are both reported."""
import argparse, json, os
from contextlib import contextmanager
import numpy as np
from bench import track_a_score as A, track_i_score as I
from core import params as P, uq
from vessels.cvd_tube import growth, thermo, wulff

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = f"{HERE}/track_l"
PSATS = {"default_smolik_hsc": {}, "smolik_liquid_cc": {"MoO3.psat_model": "smolik_liquid_cc"}}
NEAR_CM = 4.0  # Track K: boat-to-substrate NTU < ~4 (about 4 cm at the default flow) is needed for boat-temperature response
ITEMS_L = json.load(open(f"{HERE}/track_l/items.json"))


def spec(sid):
    """-> (overrides, tied) for this item; items with no verified geometry get ({}, {})."""
    it = ITEMS_L["items"].get(sid, {"overrides": {}, "tied": {}})
    return it["overrides"], it["tied"]


def x_sub_cm(sid):
    o, _ = spec(sid)
    return o.get("x_substrate_cm", 12.0)  # 12.0 = repo default (vessels/cvd_tube DEFS)


def sens_item(sid, extra, paper_geometry):
    """Same as track_a_score.sensitivity_item plus: item overrides, tied parameters, E_eff corners also when T_furnace is tied to the sweep."""
    st, par, lo, hi, base, obs, label, cls = A.ITEMS[sid]
    ov, tied = spec(sid) if paper_geometry else ({}, {})
    assert par not in ov, (sid, par)
    base = base | ov | extra
    xs = np.linspace(lo, hi, A.NPTS)
    v0 = P.validate(wulff.DEFS, base)
    rng = np.random.default_rng(0)
    draws = [v0] + [uq.sample(wulff.DEFS, v0, rng) for _ in range(A.NMC - 1)]
    corners = A.ECORN if (par == "T_furnace_C" or "T_furnace_C" in tied) else (0.0,)
    Y = {(i, e): [] for i in A.IS for e in corners}
    zero = True
    for dv in draws:
        try:
            sts = [growth.state(P.validate(wulff.DEFS, dv | {par: float(x)} | {k: float(x) for k, src in tied.items() if src == par})) for x in xs]
        except (ValueError, FloatingPointError):
            continue
        zero &= all(s["F"] <= 0 for s in sts)
        for i in A.IS:
            for e in corners:
                Y[(i, e)].append([growth.observables(s, i, e)[obs] for s in sts])
    calls, diag = {}, {}
    for i in A.IS:
        calls[i], diag[i] = A.call_from([np.array(Y[(i, e)]) for e in corners])
    final = calls[1] if len(set(calls.values())) == 1 else "uncertain"
    return {"id": sid, "param": par, "sweep": [lo, hi], "observable": obs, "label": label, "class": cls, "calls_by_i": {str(k): v for k, v in calls.items()},
            "call": final, "diag_i1": diag[1], "zero_flux": bool(zero), "n_draws": len(Y[(1, corners[0])])}


@contextmanager
def _defaults(ov):
    old = A.api_defaults
    A.api_defaults = lambda: old() | ov
    try:
        yield
    finally:
        A.api_defaults = old


def run(extra, paper_geometry):
    rows = {}
    with thermo.with_liq_sigma(extra):
        for sid in A.ITEMS:
            if A.ITEMS[sid][5] == "shape":
                ov = spec(sid)[0] if paper_geometry else {}
                with _defaults(ov):
                    r = A.shape_item(sid, extra)
            else:
                r = sens_item(sid, extra, paper_geometry)
            r["set"] = "dev (j1-j3: formerly held-out, now seen)" if sid.startswith("j") else "dev"
            rows[sid] = r
    blind = {x["id"]: x["predicted_direction"] for x in json.load(open(f"{A.HERE}/sensitivity/blind_dev_s01_s14.json")) + json.load(open(f"{A.HERE}/sensitivity/blind_heldout_jian.json"))}
    for sid, r in rows.items():
        r["blind"], r["always_increase"] = blind[sid], "increase"
    return rows


def notes(sid):
    ov, _ = spec(sid)
    flag = ITEMS_L["flags"].get(sid, "")
    if ov.get("gap_mm", 0) > 0 or sid == "s08":
        return "face-down gap model (not the tube march)" + ("; " + flag if flag else "")
    x = x_sub_cm(sid)
    far = f"substrate {x:g} cm from the boat: farther than ~{NEAR_CM:g} cm, boat-temperature response suppressed by construction (Track K)" if x > NEAR_CM else f"substrate {x:g} cm from the boat"
    return far + ("; " + flag if flag else "")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--write", action="store_true"); a = ap.parse_args()
    out = {"items_used": {s: spec(s) for s in A.ITEMS}}
    for pname, extra in PSATS.items():
        before, after = run(extra, False), run(extra, True)
        out[pname] = {"before": before, "after": after, "tables_before": I.tables(before), "tables_after": I.tables(after)}
        print("==", pname)
        for sid in A.ITEMS:
            b, f = before[sid], after[sid]
            print(sid, "label", b["label"], "before", b["call"], "after", f["call"], "blind", b["blind"], "| zero", f["zero_flux"], "|", notes(sid))
        for t in ("T1_dev_primary_s", "T2_original8", "T4_j1_j3", "T5_all_primary_incl_j"):
            print(t, "before", json.dumps(out[pname]["tables_before"][t]["call"]), "after", json.dumps(out[pname]["tables_after"][t]["call"]))
        print("T3 before", out[pname]["tables_before"]["T3_secondary"], "after", out[pname]["tables_after"]["T3_secondary"])
    out["notes"] = {s: notes(s) for s in A.ITEMS}
    try:  # consistency check of the "before" rerun against the stored Track A numbers (default psat)
        stored = json.load(open(f"{A.OUT}/results.json"))["items"]
        out["before_matches_track_a"] = {s: stored[s]["call"] == out["default_smolik_hsc"]["before"][s]["call"] for s in stored}
        print("before == stored Track A:", out["before_matches_track_a"])
    except Exception as e:  # noqa: BLE001
        print("stored comparison failed:", e)
    if a.write:
        os.makedirs(OUT, exist_ok=True)
        json.dump(out, open(f"{OUT}/results.json", "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
