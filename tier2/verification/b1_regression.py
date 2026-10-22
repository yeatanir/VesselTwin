"""B1: re-run stored ampoule cases (coarse mesh level 0 of the mesh study: diffusion, weak, tilted, strong) with the CURRENT tier2/openfoam.py
and compare f_CFD with the stored values (scratch ampoule2/mout_*.json, same case definitions).
usage: python tier2/verification/b1_regression.py <workdir> <stored_json...>   (<=3 solver processes at once, PIDs logged by scripts/ampoule_cfd_sweep)"""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from concurrent.futures import ThreadPoolExecutor
import ampoule_cfd_sweep as A

if __name__ == "__main__":
    work, stored = pathlib.Path(sys.argv[1]), {}
    for f in sys.argv[2:]:
        stored |= {r["id"]: r for r in json.load(open(f))}
    ids = [i for i in stored if i.endswith("_L0")]
    jobs = [{"id": i, "values": stored[i]["values"]} for i in ids]
    with ThreadPoolExecutor(3) as ex:
        new = list(ex.map(lambda j: A.run(j, work), jobs))
    rows = [dict(id=r["id"], f_stored=stored[r["id"]]["f_cfd"], f_now=r.get("f_cfd"), rel_diff_pct=100 * (r["f_cfd"] / stored[r["id"]]["f_cfd"] - 1) if r.get("f_cfd") else None,
                 ok=r["ok"]) for r in new]
    json.dump(rows, open(work / "b1_result.json", "w"), indent=1)
    print(json.dumps(rows, indent=1))
