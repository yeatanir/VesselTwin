"""Does a literature excerpt support a benchmark parameter? Rule pre-registered in docs/prereg/track-c.md:
(a) the excerpt names the parameter (alias regex) and (b) it contains a number+unit within 2% of a value in the item's `change`."""
import re
from llm.units import to_unit

TOL = 0.02
ALIASES = {
    "s01": r"(carrier|gas|argon|Ar)\W+(gas\W+)?flow(\s+rate)?|flow\s+rate",
    "s02": r"substrate position|transverse|gas-flow position",
    "s03": r"(Ar|argon)\W+(gas\W+)?flow(\s+rate)?|gas\s+flow\s+rate|flow\s+rate",
    "s05": r"MoO3\s+amount|amount\s+of\s+MoO3|mg\s+(of\s+)?MoO3|MoO3\s+(powder|precursor|mass)",
    "s06": r"sul(f|ph)ur\s+amount|amount\s+of\s+sul(f|ph)ur|mg\s+(of\s+)?sul(f|ph)ur",
    "s07": r"growth\s+temperature|substrate\s+temperature",
    "s08": r"vertical\s+gap|source[- ]to[- ]substrate|gap",
    "s09": r"MoO3\s+(heating\s+)?temperature|(heating\s+)?temperature\s+of\s+(the\s+)?MoO3",
    "s11": r"sul(f|ph)ur\s+(source\s+)?temperature|temperature\s+of\s+(the\s+)?sul(f|ph)ur",
    "s12": r"MoO3\s+(film\s+)?thickness|thickness\s+of\s+(the\s+)?MoO3",
    "s14": r"nanoribbon\s+(density|concentration)|MoO3\s+source\s+density",
}
ALIASES["s04"] = ALIASES["s03"]
ALIASES["s10"] = ALIASES["s13"] = ALIASES["s07"]

NUM = r"\d+(?:\.\d+)?"
UNIT = r"sccm|mL\s*/\s*min|[°º℃]\s*C|℃|(?<![A-Za-z])C(?![A-Za-z])|mg|nm|[μµ]m|mm|cm|K(?![A-Za-z])"
_TOKEN = re.compile(rf"({NUM})\s*({UNIT})?", re.I)
# canonical target unit per dimension; a value is converted to the first target it is dimensionally compatible with
_TARGETS = ("K", "cm**3/minute", "mg", "mm")


def _canon(v: float, u: str):
    u = re.sub(r"\s+", "", u.replace("℃", "C").replace("°", "").replace("º", ""))
    u = {"C": "degC", "sccm": "cm**3/minute", "ml/min": "cm**3/minute"}.get(u if u == "C" else u.lower(), u)
    for t in _TARGETS:
        try:
            return t, to_unit(v, u, t)
        except Exception:
            continue
    return None


def numbers(text: str) -> list[tuple[str, float]]:
    """(target unit, canonical value) for every number with a unit; a bare number takes the next explicit unit (lists like '700, 750, 800 C')."""
    toks = [(float(m.group(1)), m.group(2)) for m in _TOKEN.finditer(text)]
    out, pending = [], []
    for v, u in toks:
        if u is None:
            pending.append(v)
            continue
        for x in pending + [v]:
            c = _canon(x, u)
            if c:
                out.append(c)
        pending = []
    return out


def reference_values(change: str) -> list[tuple[str, float]]:
    return numbers(change)


def supports(qid: str, change: str, excerpt: str) -> dict:
    """{'verified': bool, 'name': bool, 'value': bool, 'why': str}"""
    name = bool(qid in ALIASES and re.search(ALIASES[qid], excerpt, re.I))
    ref = reference_values(change)
    hit = next(((d, a, b) for d, a in numbers(excerpt) for d2, b in ref if d == d2 and abs(a - b) <= TOL * abs(b)), None)
    why = ("name+value match" if name and hit else "no alias for the parameter in the excerpt" if not name
           else "no number within 2% of a value in the question's change field")
    return {"verified": name and bool(hit), "name": name, "value": bool(hit), "why": why}
