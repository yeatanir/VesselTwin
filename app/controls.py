"""Key controls per vessel: the few knobs a chemist physically sets, each mapped to a real ParamDef (name checked in tests).
lo/hi here are the *usable* slider range and must sit inside the ParamDef bounds. Everything else is under 'Advanced parameters'.
Pure data + tiny helpers (no streamlit)."""
import numpy as np

C = lambda name, label, lo, hi, step, help, log=False: dict(name=name, label=label, lo=lo, hi=hi, step=step, help=help, log=log)
SEL = lambda name, label, help: dict(name=name, label=label, select=True, help=help)

KEY_CONTROLS = {
    "cvd_tube": [
        C("T_furnace_C", "Furnace temperature", 500, 950, 10, "Plateau temperature of the furnace wall."),
        C("flow_sccm", "Carrier flow", 10, 500, 10, "Argon (or other carrier) flow through the tube, standard cm3/min."),
        C("T_boat_Mo_C", "MoO3 boat temperature", 500, 850, 10, "Temperature of the MoO3 boat. Below about 300 C it is nearly inert."),
        C("x_substrate_cm", "Boat-to-substrate distance", 1, 40, 1, "How far downstream of the MoO3 boat the substrate leading edge sits."),
        C("boat_area_MoO3_cm2", "MoO3 boat open area", 0.2, 20, 0.2, "Open evaporating area of the MoO3 boat (sets how much vapour is supplied)."),
        C("T_boat_S_C", "Sulfur boat temperature", 120, 250, 5, "Temperature at the sulfur boat; sets the sulfur vapour pressure."),
    ],
    "ampoule": [
        C("T_source_C", "Source temperature", 500, 1200, 10, "Hot (source) end of the sealed ampoule."),
        C("T_sink_C", "Sink temperature", 400, 1200, 10, "Cold (growth) end of the ampoule."),
        C("L_cm", "Ampoule length", 5, 50, 1, "Length of the diffusion path."),
        C("D_mm", "Ampoule diameter", 5, 40, 1, "Inner diameter; large diameters allow convection."),
        C("tilt_deg", "Tilt from horizontal", 0, 90, 5, "0 is horizontal, 90 is vertical (source end low)."),
        C("agent_mg_per_cm3", "Iodine loading", 0.1, 10, 0.1, "Transport agent (I2) loaded per cm3 of ampoule volume."),
    ],
    "flask": [
        C("stir_rpm", "Stir rate", 50, 1500, 50, "Magnetic stir-bar speed."),
        C("volume_mL", "Flask volume", 50, 2000, 10, "Nominal flask volume (liquid fills a fraction of it)."),
        SEL("solvent", "Solvent", "Sets density and viscosity of the liquid."),
        C("mu_factor", "Viscosity multiplier", 0.2, 50, 0.1, "Multiplies the solvent viscosity (thickener, concentrated solution).", log=True),
        C("feed.time_s", "Feed (addition) time", 10, 3600, 10, "How long the second reagent takes to be added.", log=True),
    ],
    "sorbent": [
        C("bed_length_cm", "Bed length", 2, 50, 1, "Length of the packed sorbent bed."),
        C("flow_sccm", "Gas flow", 20, 1000, 10, "Total feed flow, standard cm3/min."),
        C("y_feed", "CO2 fraction in feed", 0.02, 0.5, 0.01, "Mole fraction of CO2 in the feed gas."),
        C("T_K", "Temperature", 273, 373, 5, "Feed and wall temperature."),
        C("P_kPa", "Pressure", 50, 1000, 10, "Outlet pressure."),
    ],
    "photoreactor": [
        C("P_rad_W", "Lamp power (radiant)", 0.1, 100, 0.1, "Optical power of the lamp in the useful band.", log=True),
        C("dist_cm", "Lamp distance", 1, 30, 0.5, "Distance from the lamp to the vessel."),
        C("lambda_nm", "Wavelength", 250, 600, 5, "Emission wavelength of the lamp."),
        C("c0_M", "Absorber concentration", 1e-4, 0.1, None, "Concentration of the light-absorbing reactant.", log=True),
        C("wall_mm", "Wall thickness", 0.5, 6, 0.5, "Thickness of the vessel wall the light passes through."),
        C("stir_rpm", "Stirring", 50, 1500, 50, "Stir or circulation rate; limits how fast fresh solution reaches the light."),
    ],
}
# extra presets for the tube (no preset files exist); illustrative starting points, not sourced recipes
EXTRA_PRESETS = {"cvd_tube": {"Default recipe": {}, "Slow flow (30 sccm)": {"flow_sccm": 30.0}, "Fast flow (300 sccm)": {"flow_sccm": 300.0},
                              "Cool MoO3 boat (600 C)": {"T_boat_Mo_C": 600.0}}}
# big-number tiles: (label, passport derived key, unit, scale)
TILES = {
    "cvd_tube": [("Gas temperature", "T_gas_K", "K", 1), ("MoO3 reaching substrate", "MoO3_to_substrate_frac", "%", 100), ("Mo:S ratio", "ratio_Mo_S", "", 1)],
    "ampoule": [("Transport rate", "transport_rate_mmol_h", "mmol/h", 1), ("Growth rate", "growth_rate_mm_day", "mm/day", 1), ("Convection boost", "convection_enhancement", "x", 1)],
    "flask": [("Mixing time", "t_mix95_s", "s", 1), ("Mixing vs reaction (Da)", "Da_micro", "", 1), ("Feed rate", "feed_mL_min", "mL/min", 1)],
    "sorbent": [("Breakthrough time", "t_break5_min", "min", 1), ("Peak bed heating", "dT_peak_K", "K", 1), ("Capacity", "capacity_mol_kg", "mol/kg", 1)],
    "photoreactor": [("Conversion", "conversion_t_irr", "%", 100), ("Irradiance", "irradiance_mW_cm2", "mW/cm2", 1), ("Mixing vs light (Da)", "Da_mix", "", 1)],
}
N_MC = {"sorbent": 4}  # Monte Carlo draws for the live solve (sorbent is the slow vessel)
TITLES = {"cvd_tube": "MoS2 tube furnace", "ampoule": "Sealed ampoule", "flask": "Stirred flask", "sorbent": "Sorbent bed", "photoreactor": "Photoreactor"}


def options(c, val):
    """Slider option list for a log control (value inserted so the current value is always selectable)."""
    xs = [float(f"{x:.3g}") for x in np.geomspace(c["lo"], c["hi"], 25)]
    return sorted(set(xs + [float(f"{val:.3g}")]))


def clamp(c, x):
    return min(max(float(x), c["lo"]), c["hi"])
