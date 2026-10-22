"""Stage chain used by `make demo` and the smoke test: spec -> span check -> tier0 -> tier1 -> passport."""
from core import api
from core.registry import REGISTRY, load_all
from llm.span_check import check_spec
from schemas.setupspec import SetupSpec


def run(spec: SetupSpec, text: str = "", n_mc: int = 50, **kw):
    load_all()
    v = REGISTRY[spec.vessel]
    unknown = set(spec.params) - set(v.params)
    if unknown:
        raise ValueError(f"params not in {v.name} template: {sorted(unknown)}")
    spec = check_spec(spec, text) if text else spec
    out = api.solve(spec.vessel, spec=spec, n_mc=n_mc, **kw)
    out["spec"] = spec
    return out


if __name__ == "__main__":
    for name in load_all():
        o = run(SetupSpec(vessel=name, params={}, synthetic=True))
        print(f"{name:9s} {o['regime']:20s} margin={o['margin']:.2f} tier={o['passport']['tier']} synthetic={o['passport']['synthetic']}")
    print("default case OK through every stage")
