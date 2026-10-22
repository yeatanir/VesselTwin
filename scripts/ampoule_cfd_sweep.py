"""Run ampoule Tier 2 (OpenFOAM) cases and extract f_CFD = CFD sink-flux rate / dilute Fick diffusion-only rate.
usage: python scripts/ampoule_cfd_sweep.py <cases.json> <out.json> <workdir> [workers<=3]
cases.json: list of {"id", "values": {ampoule + T2 params}}; out.json is appended per finished case (resumable)."""
import json, pathlib, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from core import params as P
import vessels.ampoule as amp
from tier2.openfoam import write_case, T2_DEFS, _find

RUN = str(pathlib.Path(__file__).resolve().parents[1] / "tier2" / "run.sh")
R = 8.314462618


def tend(c, L):  # ponytail: 4 diffusion times of the carrier (as the existing scan)
    return 4 * L**2 / c["D"]


def f_series(case, p):
    c = amp._core(p)
    rows = [ln.split() for ln in _find(case, "sinkFlux", "surfaceFieldValue.dat").read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    t = np.array([float(r[0]) for r in rows]); g = np.array([float(r[1].strip("()")) for r in rows])
    return t, -c["D"] * c["Ptot"] / (R * c["T"]) * g / c["J"]


def run(job, work):
    v = dict(job["values"]); case = pathlib.Path(work) / job["id"]
    p = P.validate(amp.DEFS, {k: x for k, x in v.items() if k not in {d.name for d in T2_DEFS}})
    v.setdefault("t_end_s", tend(amp._core(p), p["L_cm"] / 100))
    t0 = time.time()
    write_case("ampoule", v, case)
    r = subprocess.run(["bash", RUN, str(case)], capture_output=True, text=True, env={**__import__("os").environ, "PWD": str(case)})
    out = dict(id=job["id"], values=v, wall_s=round(time.time() - t0), ok=r.returncode == 0)
    if r.returncode:
        out["err"] = (r.stdout + r.stderr)[-400:]; return out
    t, f = f_series(case, p)
    q = len(f) // 4
    out |= dict(f_cfd=float(f[-q:].mean()), drift_last_quarter=float(abs(f[-q:].mean() - f[-2 * q:-q].mean()) / f[-q:].mean()),
                osc_last_quarter=float(f[-q:].std() / f[-q:].mean()), t_end_s=float(t[-1]))
    return out


if __name__ == "__main__":
    jobs, outp, work = json.load(open(sys.argv[1])), pathlib.Path(sys.argv[2]), sys.argv[3]
    done = {r["id"] for r in json.loads(outp.read_text())} if outp.exists() else set()
    res = json.loads(outp.read_text()) if outp.exists() else []
    with ThreadPoolExecutor(min(int(sys.argv[4]) if len(sys.argv) > 4 else 3, 3)) as ex:
        for r in ex.map(lambda j: run(j, work), [j for j in jobs if j["id"] not in done]):
            res.append(r); outp.write_text(json.dumps(res, indent=1)); print(r["id"], r.get("f_cfd"), r["wall_s"], flush=True)
