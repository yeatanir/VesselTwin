"""Regenerate presets/sorbent__*.json from sorbent_data.json: python -m vessels.sorbent.build_presets"""
import json, pathlib
from vessels.sorbent import DATA, preset

OUT = pathlib.Path(__file__).resolve().parents[2] / "presets"
NAMES = {"13X_Z1002ND": "sorbent__13X_CO2", "13X_Z1002": "sorbent__13X_Z1002_CO2", "CALF20": "sorbent__CALF20_CO2"}


def build() -> dict:
    return {f: {k: (round(float(v), 10) if not isinstance(v, str) else v) for k, v in preset(m).items()} for m, f in NAMES.items()}


META = {"sorbent__13X_CO2": ("Zeolite 13X Z10-02ND, CO2 (dual-site Langmuir)", "Wilkins MSc thesis, U Alberta 2017, Table 4.1"),
        "sorbent__13X_Z1002_CO2": ("Zeolite 13X Z10-02, CO2 (dual-site Langmuir)", "Wilkins MSc thesis, U Alberta 2017, Table 4.1"),
        "sorbent__CALF20_CO2": ("CALF-20, CO2 (dual-site Langmuir)", "Nguyen PhD thesis, U Alberta 2021, Tables 2.1, 2.3, 3.1, 4.3")}


if __name__ == "__main__":
    for f, v in build().items():
        (OUT / f"{f}.json").write_text(json.dumps({"_meta": dict(zip(("title", "source"), META[f])), **v}, indent=1) + "\n")
        print("wrote", f)
