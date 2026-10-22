"""Scripted dry run of the 90-second demo (README) through the dashboard with Streamlit's AppTest.
usage: python scripts/demo_dryrun.py [--cold]   (--cold clears cache/dashboard first). Prints per-step compute time and checks."""
import json, pathlib, shutil, sys, time
from streamlit.testing.v1 import AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = str(ROOT / "app" / "dashboard.py")
TEXT = json.load(open(ROOT / "bench/procedures/real_01_cvd_tube.json"))["text"]
NEWV = ROOT / "vessels" / "zz_demo_vessel.py"
rows = []


def step(name, budget, fn):
    t = time.time()
    ok, note = fn()
    dt = time.time() - t
    rows.append((name, dt, budget, ok, note))
    print(f"{'PASS' if ok else 'FAIL'}  {name:34s} {dt:6.1f}s (budget {budget}s)  {note}", flush=True)


if "--cold" in sys.argv:
    shutil.rmtree(ROOT / "cache" / "dashboard", ignore_errors=True)
at = AppTest.from_file(APP, default_timeout=300)


def s0():
    at.run(); return (not at.exception), f"{len(at.tabs)} tabs"
step("0 load dashboard", 10, s0)


def s1():
    at.selectbox(key="vessel").set_value("cvd_tube").run()
    at.text_area(key="proc").set_value(TEXT).run()
    next(b for b in at.button if b.label == "Extract").click().run()
    flow = next(w for w in at.sidebar.number_input if w.key == "cvd_tube:flow_sccm").value
    return (not at.exception) and abs(flow - 35) < 1e-6, f"flow_sccm={flow}"
step("1 paste procedure + Extract", 15, s1)


def s2():
    at.selectbox(key="tier").set_value(0).run(); a = not at.exception
    at.selectbox(key="tier").set_value(1).run()
    return a and not at.exception and bool(at.metric), f"{len(at.metric)} metrics"
step("2 tier 0 -> tier 1", 20, s2)


def s3():
    sl = next(s for s in at.slider if "Sulfur boat" in s.label)
    before = [d.value.to_json() for d in at.dataframe[:3]]
    sl.set_value(sl.value - 20).run()
    after = [d.value.to_json() for d in at.dataframe[:3]]
    return (not at.exception) and before != after, f"slider {sl.value} C"
step("3 shape slider moves", 20, s3)


def s4():
    at.run(); names = [t.label for t in at.tabs]
    return (not at.exception) and "Brief" in names, str(names)
step("4 brief tab present", 15, s4)


def s5():
    NEWV.write_text((ROOT / "vessels" / "_template.py").read_text())
    try:
        a2 = AppTest.from_file(APP, default_timeout=300).run()
        opts = list(a2.selectbox(key="vessel").options)
        return (not a2.exception) and any("Template demo" in o or "template_demo" in o for o in opts), f"{len(opts)} vessels listed"
    finally:
        NEWV.unlink(missing_ok=True)
step("5 drop-in vessel appears", 10, s5)


def s6():
    at.selectbox(key="tier").set_value(2).run()
    return (not at.exception) and any("OpenFOAM" in i.value for i in at.info), "tier 2 message"
step("6 tier 2 message", 10, s6)


def s7():
    at.run(); return (not at.exception) and any("passed" in m.value for m in at.metric), "credibility"
step("7 credibility tab", 10, s7)

tot = sum(r[1] for r in rows[1:])
print(f"\ncompute total (steps 1-7): {tot:.1f}s; failures: {sum(not r[3] for r in rows)}; over budget: {sum(r[1] > r[2] for r in rows)}")
sys.exit(any(not r[3] for r in rows))
