"""Passport -> brief for the simulation person: the conditions the chemistry sees (distributions AND tails) and a ranking of
the atomistic calculations that would most change the experimental outcome. Every number in the text is filled by code from
solver outputs; sentences are fixed templates (the LLM, if used, only writes around the placeholders).
Tails: the most probable point of the 95% outcome tail, found by shifting every uncertain input along the outcome gradient
(in sigma units, total length 1.645) and re-solving. ponytail: linearised tail, not a full tail MC."""
import numpy as np
from core import api
from atomistic import ranking as R

Z95 = 1.645
T = {
    "head": "Brief for {vessel} at site {site}: Tier {tier} solver ({source}).",
    "synthetic": "SYNTHETIC: the reduced-model constants are illustrative placeholders, so these numbers show the workflow, not a prediction.",
    "real": "Inputs are not flagged synthetic.",
    "outcome": "Outcome of interest: {label}. Nominal {p50} {unit}; at the low tail {lo} {unit}; at the high tail {hi} {unit}.",
    "cond": "{name}: p05 {p05}, p50 {p50}, p95 {p95} {unit}. At the low-outcome tail {lo}; at the high-outcome tail {hi}.",
    "rank": "Rank {rank}: {calc} for {param} [{cost}]. Its one-sigma uncertainty ({sigma} {unit}) moves the {outcome} by {delta} {ounit}.",
    "na": "n/a means the solver finds no value there, for example no shape boundary inside the mapped region.",
    "norank": "No editable parameter of this vessel maps to an atomistic calculation with a nonzero effect on the outcome.",
}


def _key(vessel, outcome):
    return R._outcome(vessel, outcome)[0]


def _g(x):
    return R._g(x)


def _flat(res):
    p = res["passport"]
    d = {"T_K": p["T_K"]["p50"]}
    for s, q in p["species"].items():
        for k, v in q.items():
            d[f"{s}.{k}"] = v["p50"]
    d |= {k: v["p50"] for k, v in p["derived"].items()}
    return d


def _tails(vessel, values, outcome, seed):
    """Re-solve at the +-1.645-sigma points along the outcome gradient. Returns (low_result, high_result, shifts)."""
    sl = [r for r in R.slopes(vessel, values, outcome, 1, seed) if r["delta"] > 0]
    base, by = R._base(vessel, values), {d["name"]: d for d in api.schema(vessel)}
    norm = np.sqrt(sum(r["delta"] ** 2 for r in sl)) or 1.0
    out = []
    for sign in (-1, 1):
        ov = dict(values or {})
        for r in sl:
            d = by[r["param"]]
            x = base[r["param"]] + sign * Z95 * np.sign(r["slope"]) * r["delta"] / norm * r["sigma"]
            ov[r["param"]] = min(max(x, d["lo"] if d["lo"] is not None else -np.inf), d["hi"] if d["hi"] is not None else np.inf)
        out.append(R.solve(vessel, ov, _key(vessel, outcome), 1, seed))
    return out[0], out[1]


def make_brief(vessel, values=None, n_mc=60, seed=0, outcome=None) -> dict:
    key, label, ounit = R._outcome(vessel, outcome)
    res = api.solve(vessel, values, n_mc=n_mc, seed=seed)
    p = res["passport"]
    lo_r, hi_r = _tails(vessel, values, outcome, seed)
    nom = R.outcome_value(R.solve(vessel, values or {}, key, 1, seed), key)
    ot = [R.outcome_value(lo_r, key), R.outcome_value(hi_r, key)]
    flo, fhi = _flat(lo_r), _flat(hi_r)
    rows = []

    def row(name, d, unit):
        rows.append({"name": name, "unit": unit or d.get("unit", ""), "p05": d["p05"], "p50": d["p50"], "p95": d["p95"],
                     "low_tail": flo.get(name), "high_tail": fhi.get(name)})

    row("T_K", p["T_K"], "K")
    for s, q in p["species"].items():
        for k, v in q.items():
            row(f"{s}.{k}", v, v["unit"])
    for k, v in p["derived"].items():
        row(k, v, v["unit"])
    ranking = R.rank_calculations(vessel, values, outcome, 1, seed)
    b = {"vessel": vessel, "site": p["site"], "tier": p["tier"], "source": p["source"], "synthetic": p["synthetic"],
         "regime": res["regime"], "seed": seed, "n_mc": n_mc, "values": res["values"],
         "outcome": {"key": key, "label": label, "unit": ounit, "p50": nom, "low_tail": ot[0], "high_tail": ot[1],
                     "z": Z95, "note": "tails = most probable point of the 95% outcome tail (linearised), re-solved"},
         "conditions": rows, "ranking": ranking}
    b["text"] = _text(b)
    return b


def _text(b):
    o = b["outcome"]
    L = [T["head"].format(vessel=b["vessel"], site=b["site"], tier=b["tier"], source=b["source"]),
         T["synthetic"] if b["synthetic"] else T["real"],
         T["outcome"].format(label=o["label"], p50=_g(o["p50"]), lo=_g(o["low_tail"]), hi=_g(o["high_tail"]), unit=o["unit"] or "-")]
    L += [T["cond"].format(name=r["name"], p05=_g(r["p05"]), p50=_g(r["p50"]), p95=_g(r["p95"]), unit=r["unit"] or "-",
                           lo=_g(r["low_tail"]), hi=_g(r["high_tail"])) for r in b["conditions"]]
    L += [T["na"]] if any(v is None or not np.isfinite(v) for v in (o["low_tail"], o["high_tail"])) else []
    L += [T["rank"].format(rank=r["rank"], calc=r["calc"], param=r["param"], cost=r["cost"], sigma=_g(r["sigma"]), unit=r["unit"],
                           outcome=r["outcome"], delta=_g(r["delta"]), ounit=r["outcome_unit"] or "-") for r in b["ranking"]] or [T["norank"]]
    return "\n".join(L)


def to_markdown(b) -> str:
    o = b["outcome"]
    t = ["| condition | unit | p05 | p50 | p95 | low tail | high tail |", "|---|---|---|---|---|---|---|"]
    t += [f"| {r['name']} | {r['unit'] or '-'} | {_g(r['p05'])} | {_g(r['p50'])} | {_g(r['p95'])} | {_g(r['low_tail'])} | {_g(r['high_tail'])} |"
          for r in b["conditions"]]
    k = ["| rank | calculation | parameter | cost | one-sigma | expected change in outcome |", "|---|---|---|---|---|---|"]
    k += [f"| {r['rank']} | {r['calc']} | {r['param']} | {r['cost']} | {_g(r['sigma'])} {r['unit']} | {_g(r['delta'])} {r['outcome_unit']} |"
          for r in b["ranking"]]
    return (f"# Simulation brief: {b['vessel']}" + (" (SYNTHETIC)" if b["synthetic"] else "") + "\n\n"
            + "\n".join(f"- {l}" for l in b["text"].split("\n"))
            + "\n\n## Conditions the chemistry sees\n\n" + "\n".join(t) + "\n\n## Ranked atomistic calculations\n\n" + "\n".join(k) + "\n")
