# VesselTwin: a tool that tells you what its own numbers are worth

**Author:** Anirban Phukan · **Licence:** MIT · **Repo:** https://github.com/yeatanir/VesselTwin · **Demo:** https://vesseltwin.streamlit.app

## The problem

A synthesis paper reports a recipe. You reproduce it, and the outcome changes. The experimentalist cannot see which hidden variable mattered (local temperature, flow, precursor position, light dose). The simulation scientist cannot tell which atomistic calculation would reduce the uncertainty. Between the two sits the vessel, and nobody models it.

## What VesselTwin does

1. **Reads a procedure** (text) and extracts the setup. Every value is tagged stated, default or missing, and each stated value is checked against its source span.
2. **Models the vessel** at three levels: a dimensionless regime call, fast reduced-order models with Monte Carlo uncertainty, and OpenFOAM CFD. Five vessels share one core: MoS2 CVD tube, sealed ampoule, stirred flask, sorbent bed, photoreactor. Adding a vessel is one file.
3. **Tells two people two things.** The experimentalist: which knob moves the outcome and which does not. The simulation scientist: a ranked list of atomistic calculations whose result would change the prediction most.
4. **Labels every claim** as benchmarked, uncertain or hypothesis. A label is capped by its weakest evidence and is never upgraded.

## What we can show

- **Sorbent bed:** CALF-20 breakthrough within -3% to +10% of published curves (n = 3).
- **Photoreactor:** predicted/measured actinometer slope 0.88 and 0.69 for two setups, inside pre-registered tolerances, inputs taken from the paper and not fitted.
- **Ampoule:** diffusion-limited cases match OpenFOAM within 2%.
- **Extractor:** 33 real procedures, precision 0.97, recall 0.83, no fabricated values (a stand-in model scored it; the offline rules backend scores 0.95 / 0.73).
- **A model-dependent finding for the experimentalist:** in our model, with equilibrium condensation on the tube wall, a substrate more than about 4 cm from the MoO3 boat sees almost none of the boat's temperature change (the wall takes about 98% of the vapour first). This depends on the wall-uptake assumption: with a reflecting wall the response returns. The stored CFD uses a similar wall law, so it is not independent evidence. Which wall behaviour is real is the open question the tool points to.
- **Furnace and flow physics for the tube:** an editable furnace profile (or a measured one), a quartz-tube network, gas temperature and velocity along the tube, and computed boat and substrate temperatures. Gas-side agreement with the stored CFD is 45 of 52 cases (legacy 35), but the CFD imposes the wall temperature and is not independent, and no measured temperature validates the absolute boat and substrate values.
- **A verification harness that finds errors:** it caught a 30-60x error in a literature constant, a wrong edge orientation and stale claims in our own interface.

## What we cannot claim

We do **not** predict MoS2 growth outcomes. On 14 literature observations the tube model's direction-of-change calls scored 1/9 to 3/9, a blind no-tool baseline scored 6/9, and shape-class prediction equals always answering "triangle" (0.50). The CFD surrogates miss their 5% target. All benchmark items are development data; no held-out set exists yet. Coupling reactor transport to growth morphology is not new: Momeni et al. (npj 2D Mater. Appl. 2018) did it and validated it on MoS2 islands.

## Why it matters

The contribution is the workflow and its honesty: a procedure goes in; a vessel model, an uncertainty band, a next calculation and a trust label come out, and the tool says when not to trust itself. It runs offline, works with any LLM provider (or none), and a new vessel or chemistry is a drop-in file. The next step is a pre-registered, held-out test: predictions declared before new experiments, for a two-factor design on one tube (flow and sulfur temperature, three levels each).

## Method notes

Reduced models: Hertz-Knudsen sources, laminar plug flow, wall condensation, Schafer transport, Villermaux-Dushman mixing, LDF/Langmuir columns, Beer-Lambert photoreactor. CFD: OpenFOAM v2512 (custom buoyant species solver for the ampoule). Atomistic inputs: MACE-MP-0 and DFT values from Rosen et al. 2018 and Cao et al. 2015, labelled by source. Literature: Edison Scientific and Valency, one credit per question, claims verified against opened sources. 424 automated tests.
