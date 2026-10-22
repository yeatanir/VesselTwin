"""B3 scoring (run once, after pre-registration a060deb). Writes tier2/verification/b3_results.json. See docs/prereg/track-b.md."""
import json, pathlib, sys
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from core import params as P
import vessels.ampoule as amp
import vessels.cvd_tube as T
import tube_cfd_verification as TV
from tier2.verification.tier0 import f_variant, tube_tier0_new

SEEDS = (0, 1, 2, 3, 4)


def conf(lab, pred, classes):
    return {c: {d: int(sum((l == c) and (p == d) for l, p in zip(lab, pred))) for d in classes} for c in classes}


def acc(lab, pred): return float(np.mean([l == p for l, p in zip(lab, pred)]))


def halves(lab, seed):
    """Stratified random half split by label: returns (train_idx, test_idx)."""
    rng = np.random.default_rng(seed)
    lab = np.asarray(lab)
    tr, te = [], []
    for c in sorted(set(lab)):
        ix = rng.permutation(np.where(lab == c)[0])
        k = (len(ix) + 1) // 2
        tr += list(ix[:k]); te += list(ix[k:])
    return np.array(sorted(tr)), np.array(sorted(te))


def fit_threshold(logda, lab, pos="transport_limited"):
    """Threshold on log10 Da maximising train accuracy (label pos iff logda >= thr); ties -> midpoint of the longest tied run."""
    z = np.sort(np.unique(logda))
    cand = np.r_[z[0] - 1, (z[:-1] + z[1:]) / 2, z[-1] + 1]
    a = np.array([np.mean([(l == pos) == (x >= t) for x, l in zip(logda, lab)]) for t in cand])
    best = np.where(a == a.max())[0]
    runs, cur = [], [best[0]]
    for i in best[1:]:
        if i == cur[-1] + 1: cur.append(i)
        else: runs.append(cur); cur = [i]
    runs.append(cur)
    run = max(runs, key=len)
    return float((cand[run[0]] + cand[run[-1]]) / 2)


res = {}
# ---------------- tube
sw = [r for r in json.load(open(ROOT / "docs/tube_cfd_verification.json"))["sweep"] if r["ok"]]
lab = [r["regime_cfd"] for r in sw]
cls = ["heat_limited", "transport_limited", "reaction_limited"]
base, new, dab, dae = [], [], [], []
for r in sw:
    p = P.validate(T.DEFS, TV.trim(r["values"]))
    r0, _, nums = T.tier0(p)
    assert r0.value == r["regime_tier0"], r["id"]  # stored Tier 0 call reproduced
    rn, de = tube_tier0_new(p)
    base.append(r0.value); new.append(rn.value); dab.append(nums["Da_wall"]); dae.append(de)
res["tube"] = dict(n=len(sw), cfd_counts={c: lab.count(c) for c in cls}, base=dict(acc=acc(lab, base), confusion=conf(lab, base, cls)),
                   new_threshold1=dict(acc=acc(lab, new), confusion=conf(lab, new, cls)))
for name, da in (("base", dab), ("new", dae)):
    ld = np.log10(np.maximum(da, 1e-300))
    held = []
    for s in SEEDS:
        tr, te = halves(lab, s)
        thr = fit_threshold(ld[tr], [lab[i] for i in tr])
        pr = ["transport_limited" if ld[i] >= thr else "reaction_limited" for i in te]
        held.append(dict(seed=s, thr_log10=thr, acc_test=acc([lab[i] for i in te], pr), n_test=len(te), confusion=conf([lab[i] for i in te], pr, cls[1:])))
    a = [h["acc_test"] for h in held]
    res["tube"][f"{name}_fitted_threshold_halfsplit"] = dict(mean=float(np.mean(a)), sd=float(np.std(a)), per_seed=held)
res["tube"]["Da_eff_log10_summary"] = dict(by_label={c: [float(np.median(np.log10(np.maximum([d for d, l in zip(dae, lab) if l == c], 1e-300)))), int(lab.count(c))] for c in cls if c in lab})
res["tube"]["misses_new"] = [dict(id=r["id"], cfd=l, new=n, Da_eff=d, frac_upstream_uptake=r["frac_upstream_uptake"]) for r, l, n, d in zip(sw, lab, new, dae) if l != n]
# ---------------- ampoule
rows = [r for r in json.load(open(ROOT / "docs/ampoule_cfd_verification.json"))["sweep"] if r["ok"]]
ps = [P.validate(amp.DEFS, {k: v for k, v in r["values"].items() if k not in ("cells_per_cm", "n_cross")}) for r in rows]
F = {s: np.array([f_variant(p, s) for p in ps]) for s in ("none", "legacy_L3", "duct")}
fc = np.array([r["f_cfd"] for r in rows])
ac = ["convection_assisted", "transport_limited"]
res["ampoule"] = dict(n=len(rows))
cands = [("duct", 1.1), ("duct", 1.05), ("duct", 1.2), ("legacy_L3", 1.05), ("legacy_L3", 1.1), ("legacy_L3", 1.2), ("none", 1.05), ("none", 1.1), ("none", 1.2)]
for th in (1.1, 1.2):
    L = ["convection_assisted" if x > th else "transport_limited" for x in fc]
    pred = lambda s, c: ["convection_assisted" if x > c else "transport_limited" for x in F[s]]
    d = dict(n_cfd_convection=L.count("convection_assisted"), fixed={}, halfsplit=[])
    for s in F:
        for c in (1.05, 1.1, 1.2):
            d["fixed"][f"{s}@{c}"] = dict(acc=acc(L, pred(s, c)), confusion=conf(L, pred(s, c), ac))
    for sd in SEEDS:
        tr, te = halves(L, sd)
        a_tr = {c: acc([L[i] for i in tr], [pred(*c)[i] for i in tr]) for c in cands}
        best = max(cands, key=lambda c: (a_tr[c], -cands.index(c)))  # ties -> earlier in the priority list (shipped first)
        d["halfsplit"].append(dict(seed=sd, chosen=f"{best[0]}@{best[1]}", acc_train=a_tr[best], acc_test=acc([L[i] for i in te], [pred(*best)[i] for i in te]),
                                   shipped_acc_test=acc([L[i] for i in te], [pred("duct", 1.1)[i] for i in te]),
                                   legacy_acc_test=acc([L[i] for i in te], [pred("legacy_L3", 1.1)[i] for i in te]),
                                   none_acc_test=acc([L[i] for i in te], [pred("none", 1.1)[i] for i in te])))
    for k in ("acc_test", "shipped_acc_test", "legacy_acc_test", "none_acc_test"):
        d[f"{k}_mean"], d[f"{k}_sd"] = float(np.mean([h[k] for h in d["halfsplit"]])), float(np.std([h[k] for h in d["halfsplit"]]))
    res["ampoule"][f"cfd_threshold_{th}"] = d
OUT = pathlib.Path(__file__).with_name("b3_results.json")
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items()}, indent=1)[:9000])
