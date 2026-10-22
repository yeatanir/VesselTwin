"""LLM front door: procedure text -> SetupSpec. The LLM never produces a physical number.
Every backend only PROPOSES (key, value, unit, span); extract() then enforces: key in Vessel.params, span check
(llm.span_check), unit/dimension via pint, ParamDef bounds/choices. A backend can lose recall, never fabricate."""
import json, os, re
from core import api
from core.registry import load_all
from llm.span_check import check_spec
from llm.units import to_unit
from schemas.setupspec import Field, SetupSpec, Status

# ---- vessel detection (keyword scoring) ----
KEYWORDS = {
    "cvd_tube": ["cvd", "furnace", "quartz tube", "moo3", "sulfur", "sulphur", "substrate", "sccm", "monolayer", "tube furnace"],
    "ampoule": ["ampoule", "sealed", "transport", "iodine", "i2", "chemical vapor transport", "vapour transport", "evacuated", "source zone", "sink"],
    "flask": ["flask", "stirred", "stir bar", "rpm", "round-bottom", "dropwise", "magnetic stir", "reflux", "solvent"],
    "sorbent": ["breakthrough", "sorbent", "zeolite", "mof", "packed bed", "adsorption", "bed of", "column", "co2"],
}


def detect_vessel(text: str) -> str:
    t = text.lower()
    s = {v: sum(k in t for k in ks) for v, ks in KEYWORDS.items()}
    return max(s, key=s.get)  # ponytail: ties -> first listed; no confidence output


# ---- rules backend ----
N = r"(\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
DEG = r"(?:°\s*C|º\s*C|℃|degrees?\s*C)"
GAP = r"[^.;\d()]{0,50}?"  # no digits/parens: never skips over another number
ID = r"(?:i\.?d\.?|inner diameter|(?:in )?diameter)"
FLOW = r"(sccm|mL\s*/\s*min|mL\s*min[-−]1|cm3\s*/\s*min|[Ll]\s*/\s*min|SCCM)"
# (param, regex, unit or None -> group 2). Group 1 = number. Span = whole match.
RULES = {
    "cvd_tube": [
        ("tube_id_in", rf"{N}[\s-]*(inch(?:es)?|in)\b[^.;]{{0,20}}?tube", None),
        ("tube_id_in", rf"{N}\s*(mm|cm)\s*{ID}", None),
        ("flow_sccm", rf"{N}\s*{FLOW}", None),
        ("T_boat_Mo_C", rf"MoO3{GAP}{N}\s*{DEG}", "C"),
        ("T_boat_Mo_C", rf"{N}\s*{DEG}\s*(?:for|of)\s+MoO3", "C"),
        ("T_boat_S_C", rf"(?:sulfur|sulphur|S powder)[^.;\d()]{{0,60}}?{N}\s*{DEG}", "C"),
        ("T_furnace_C", rf"(?:furnace|tube|growth|maximum temperature)(?:(?!MoO3|sulfur|sulphur)[^.;\d()]){{0,60}}?{N}\s*{DEG}", "C"),
        ("x_substrate_cm", rf"{N}\s*(cm)\s*downstream", None),
        ("pressure_Pa", rf"{N}\s*(Torr|mbar|kPa|Pa|atm)\b", None),
        ("carrier", r"\b(Ar|N2|argon|nitrogen)\b", "str"),
    ],
    "ampoule": [
        ("L_cm", rf"{N}[\s-]*(cm|mm|inch)[\s-]*(?:long|length|in length)", None),
        ("D_mm", rf"{N}\s*(mm|cm)\s*{ID}", None),
        ("D_mm", rf"{ID}\s*(?:of\s*)?{N}\s*(mm|cm)", None),
        ("T_source_C", rf"(?:source|hot){GAP}{N}\s*{DEG}", "C"),
        ("T_source_C", rf"{N}\s*{DEG}\W{{0,3}}(?:source|hot)", "C"),
        ("T_sink_C", rf"(?:sink|cold|growth){GAP}{N}\s*{DEG}", "C"),
        ("T_sink_C", rf"{N}\s*{DEG}\W{{0,3}}(?:sink|cold|growth)", "C"),
        ("agent_mg_per_cm3", rf"{N}\s*(mg\s*/\s*cm3|mg\s*cm[-−]3|mg\s*/\s*mL|g\s*/\s*L|g\s*L[-−]1)", None),
        ("gas", r"\b(?P<g>iodine|I2)\b(?:\W+\w+){0,3}?\W+(?:transport|agent)|(?:transport\w*\s+agent|agent)\W+(?:\w+\W+){0,4}?(?P<g2>iodine|I2)\b|(?:cm3|cm[-−]3)\s+(?P<g3>iodine|I2)\b", "I2"),
    ],
    "flask": [
        ("volume_mL", rf"{N}\s*(mL|L)\s+(?:[\w-]+\s+){{0,2}}?flask", None),
        ("bar_mm", rf"{N}\s*(mm)\s+(?:\w+\s+)?stir[\s-]?bar", None),
        ("stir_rpm", rf"{N}\s*(rpm)", None),
        ("T_C", rf"{N}\s*{DEG}", "C"),
        ("C0_M", rf"{N}\s*((?-i:mM|M))(?![\w/])", None),
    ],
    "sorbent": [
        ("bed_length_cm", rf"(?:length|height)\s*(?:of\s*)?{N}\s*(cm|mm)", None),
        ("bed_length_cm", rf"bed\s+of\s+{N}\s*(cm|mm)", None),
        ("bed_length_cm", rf"{N}\s*(cm|mm)[\s-]*(?:long|height|in length|bed)", None),
        ("bed_id_cm", rf"{N}\s*(mm|cm)\s*{ID}", None),
        ("bed_id_cm", rf"{ID}\s*(?:of\s*)?{N}\s*(mm|cm)", None),
        ("flow_sccm", rf"{N}\s*{FLOW}", None),
        ("T_K", rf"{N}\s*(K)\b", None),
        ("T_K", rf"{N}\s*{DEG}", "degC"),
        ("P_kPa", rf"{N}\s*(kPa|bar|atm)\b", None),
        ("particle_dp_mm", rf"{N}\s*(mm)\s*(?:particles|pellets|beads|extrudates)", None),
        ("y_feed", rf"{N}\s*(%)", "percent"),
    ],
}
# keyword-valued string params; ambiguous (>1 distinct hit, e.g. ethanol/water mix) -> not extracted
CHOICES = {"solvent": {"water": r"water", "ethanol": r"ethanol|EtOH", "DMF": r"DMF", "ethylene_glycol": r"ethylene glycol",
                       "THF": r"THF", "toluene": r"toluene", "acetonitrile": r"acetonitrile", "DMSO": r"DMSO",
                       "glycerol": r"glycerol"},
           "energy": {"isothermal": r"isothermal", "nonisothermal": r"non-?isothermal|adiabatic"}}
_ALIAS = {"argon": "Ar", "nitrogen": "N2", "iodine": "I2"}
# a number in a sentence about cleaning/drying/work-up/analysis is not the process setting
_SKIP = re.compile(r"purg|clean|flush|degas|activat|pre-?treat|remov|dried|drying|wash|centrifug|anneal|outgas|calcin", re.I)
_RANGE = re.compile(r"\d\s*(?:-|–|—|−|to|and|or)\s*$")


def _sentence(text: str, i: int) -> str:
    a = max(text.rfind(". ", 0, i), text.rfind(" [...] ", 0, i), -1)
    b = text.find(". ", i)
    return text[a + 1: b if b >= 0 else len(text)]


def _num(x: str) -> float:
    return float(re.sub(r"[ ,]", "", x))


def rules_backend(text: str, vessel: str) -> list[dict]:
    by: dict[str, list] = {}
    for key, rx, u in RULES.get(vessel, []):
        for m in re.finditer(rx, text, 0 if key == "carrier" else re.I):
            if _SKIP.search(_sentence(text, m.start())) and key not in ("tube_id_in", "bed_id_cm", "bed_length_cm", "L_cm", "D_mm", "gas", "carrier", "volume_mL", "agent_mg_per_cm3"):
                continue
            if key != "carrier" and key != "gas" and _RANGE.search(text[:m.start(1)]):
                continue  # range / alternatives ('150 to 300 sccm'): no single value stated
            if key == "gas":
                g = m.group("g") or m.group("g2") or m.group("g3")
                by.setdefault(key, []).append((_ALIAS.get(g.lower(), g), None, g))
            elif u == "str":
                by.setdefault(key, []).append((_ALIAS.get(m.group(1).lower(), m.group(1)), None, m.group(1)))
            else:
                unit = u if u in ("C", "degC", "percent") else re.sub(r"\s+", " ", m.group(2)).replace("−", "-")
                by.setdefault(key, []).append((_num(m.group(1)), unit, m.group(0)))
    out = []
    for key, c in by.items():
        if len({(v, un) for v, un, _ in c}) == 1 or key in ("carrier", "gas"):  # conflicting values -> ambiguous -> skip
            out.append(dict(key=key, value=c[0][0], unit=c[0][1], span=c[0][2]))
    names = {d.name for d in load_all()[vessel].defs}
    for key, opts in CHOICES.items():
        hits = {val: m for val, rx in opts.items() if (m := re.search(rf"\b(?:{rx})\b", text, re.I if val != "DMF" else 0))}
        if key in names and len(hits) == 1:
            val, m = next(iter(hits.items()))
            out.append(dict(key=key, value=val, unit=None, span=m.group(0)))
    return out


# ---- constrained schema (shared by LLM backends) ----
def json_schema(vessel: str) -> dict:
    """Schema from ParamDefs: key is an enum of this vessel's params, so a constrained decoder cannot invent fields.
    value is a STRING copied from the text (the LLM emits no computed numbers); we parse it and span-check it."""
    v = load_all()[vessel]
    desc = "; ".join(f"{d.name} = {d.label} [{d.unit}]" for d in v.defs)
    item = {"type": "object", "additionalProperties": False, "required": ["key", "value", "unit", "span"],
            "properties": {"key": {"type": "string", "enum": v.params},
                           "value": {"type": "string", "description": "the value exactly as written in the text"},
                           "unit": {"type": ["string", "null"], "description": "unit exactly as written, or null"},
                           "span": {"type": "string", "description": "verbatim substring of the text containing the value"}}}
    return {"type": "object", "additionalProperties": False, "required": ["fields"],
            "properties": {"fields": {"type": "array", "items": item, "description": desc}}}


_PROMPT = ("Extract experimental setup parameters from the procedure. Only include a parameter if the text states it. "
           "Copy values, units and spans verbatim. Never convert units, compute, or guess; omit unknowns.\n\nProcedure:\n")


def _coerce(items: list[dict]) -> list[dict]:
    out = []
    for i in items:
        try:
            val = float(i["value"])
        except (TypeError, ValueError):
            val = i["value"]
        out.append(dict(key=i["key"], value=val, unit=i.get("unit"), span=i["span"]))
    return out


def anthropic_backend(text: str, vessel: str, model: str = "claude-sonnet-5-5") -> list[dict]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("anthropic backend needs ANTHROPIC_API_KEY (use backend='rules' to run offline)")
    import anthropic  # lazy: not required for the rules backend
    msg = anthropic.Anthropic().messages.create(
        model=model, max_tokens=4000, messages=[{"role": "user", "content": _PROMPT + text}],
        output_config={"format": {"type": "json_schema", "schema": json_schema(vessel)}})
    return _coerce(json.loads(next(b.text for b in msg.content if b.type == "text"))["fields"])


def mlx_backend(text: str, vessel: str, model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit") -> list[dict]:
    """UNTESTED (mlx-lm not installed here). Grammar-constrained JSON via outlines if present, else prompt + parse;
    either way output goes through the same span/bounds checks."""
    try:
        from mlx_lm import load, generate
    except ImportError as e:
        raise RuntimeError("mlx backend needs `pip install mlx-lm` (and a local model)") from e
    m, tok = load(model)
    prompt = tok.apply_chat_template([{"role": "user", "content": _PROMPT + text + "\nReply with JSON matching: "
                                       + json.dumps(json_schema(vessel))}], add_generation_prompt=True, tokenize=False)
    raw = generate(m, tok, prompt=prompt, max_tokens=1500)
    # ponytail: no true grammar decoding (outlines/xgrammar); invalid JSON -> empty result (recall loss, not fabrication)
    try:
        return _coerce(json.loads(raw[raw.index("{"): raw.rindex("}") + 1])["fields"])
    except (ValueError, KeyError):
        return []


def replay_backend(text: str, vessel: str, path: str) -> list[dict]:
    """Precomputed model output ({"vessel", "fields":[{key,value,unit,span}]}); same enforcement as a live backend."""
    return _coerce(json.load(open(path))["fields"])


def llm_backend(text: str, vessel: str, chat=None) -> list[dict]:
    """Any provider via llm.backends.make_chat (VT_LLM_* env, or pass chat). Prompt + parse; same span/bounds enforcement as every backend."""
    from llm.backends import make_chat
    chat = chat or make_chat()
    raw = chat([{"role": "user", "content": _PROMPT + text + "\nReply with JSON only, matching: " + json.dumps(json_schema(vessel))}])
    try:  # invalid JSON -> empty result (recall loss, not fabrication)
        return _coerce(json.loads(raw[raw.index("{"): raw.rindex("}") + 1])["fields"])
    except (ValueError, KeyError, TypeError):
        return []


BACKENDS = {"rules": rules_backend, "anthropic": anthropic_backend, "mlx": mlx_backend, "llm": llm_backend, "openai_compatible": llm_backend}


# ---- enforcement ----
def canonical(d, value, unit):
    """Value in ParamDef unit (llm.units handles C/degC offsets, cm3, Torr...). Raises on dimension mismatch."""
    return value if d.choices is not None or not unit else to_unit(value, unit, d.unit)


def build_spec(text: str, vessel: str, items: list[dict], fill_defaults: bool = False) -> SetupSpec:
    v = load_all()[vessel]
    by = {d.name: d for d in v.defs}
    params = {d.name: Field() for d in v.defs}
    for it in items:
        d = by.get(it["key"])
        if d is None or params[d.name].status is Status.stated:
            continue  # unknown key (invented field) dropped; first proposal wins
        params[d.name] = Field(value=it["value"], unit=it.get("unit") or None, span=it["span"], status=Status.stated)
    spec = check_spec(SetupSpec(vessel=vessel, params=params, source_text=text), text)
    for k, f in spec.params.items():  # physics sanity bounce
        if f.status is not Status.stated:
            continue
        d = by[k]
        try:
            if d.choices is not None:
                ok = f.value in d.choices
            else:
                if isinstance(f.value, str):
                    raise ValueError("non-numeric")
                c = canonical(d, f.value, f.unit)
                ok = (d.lo is None or c >= d.lo) and (d.hi is None or c <= d.hi)
            why = "out of bounds"
        except Exception as e:  # pint DimensionalityError / UndefinedUnitError / non-numeric
            ok, why = False, f"unit/value error ({type(e).__name__})"
        if not ok:
            spec.params[k] = Field(status=Status.missing, note=f"rejected: {why} (was {f.value!r} {f.unit or ''})")
    if fill_defaults:
        for d in v.defs:
            if spec.params[d.name].status is Status.missing:
                spec.params[d.name] = Field(value=d.default, unit=d.unit or None, status=Status.default,
                                            note="ParamDef default" + (" (synthetic)" if d.source == "synthetic" else ""))
    return spec


def extract(text: str, vessel: str | None = None, backend: str = "rules", fill_defaults: bool = False,
            runs_dir: str | None = None, name: str | None = None) -> SetupSpec:
    """backend: name, or a callable(text, vessel)->items (test hook). 'replay' reads <runs_dir>/<name>.json (name = procedure file stem)."""
    vessel = vessel or detect_vessel(text)
    if backend == "replay":
        items = replay_backend(text, vessel, os.path.join(runs_dir, name + ".json"))
    else:
        items = BACKENDS[backend](text, vessel) if isinstance(backend, str) else backend(text, vessel)
    return build_spec(text, vessel, items, fill_defaults)


def extract_and_solve(text: str, vessel: str | None = None, backend: str = "rules", **kw) -> dict:
    """api.solve output + the spec; provenance (stated/default/synthetic) is in out['provenance']."""
    spec = extract(text, vessel, backend)
    out = api.solve(spec.vessel, spec=spec, **kw)
    out["spec"] = spec.model_dump(mode="json")
    return out
