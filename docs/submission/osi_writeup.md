VesselTwin is an LLM-plus-physics tool that turns a synthesis procedure into the real conditions inside the reactor, then into a ranked list of the atomistic calculations worth running next, with the provenance of every number shown. The flagship model fails our own benchmark, and the tool says so. That is the point.

## Approach

**The gap.** A recipe that worked once often does not work twice, because the vessel hides the variables that decide the outcome. The experimentalist cannot see the local gas temperature, where the vapour went, or the light dose that reached the sample. The simulation scientist cannot tell which calculation, under which local conditions, would change the experiment.

**The tool.** VesselTwin reads a procedure as plain text; every extracted value is tagged *stated*, *default* or *missing* and checked against the sentence it came from. It models the vessel at three levels: an instant regime call, a fast reduced-order physics model with Monte Carlo uncertainty bands that recomputes as you move a slider, and OpenFOAM CFD. Five vessels share one core: a MoS2 CVD tube furnace, a sealed ampoule, a stirred flask, a sorbent bed and a photoreactor; a new vessel is one file. It then tells the experimentalist which knob moves the result most, and the simulation scientist which atomistic calculation to run, and labels every claim *benchmarked*, *uncertain* or *hypothesis*.

**Where the language model fits.** It reads the procedure, calls the physics and literature tools, and explains the result. It never produces a physical number. Any provider works with your own key, or nothing at all: everything runs offline. Edison Scientific and Valency supplied sourced parameters, and every sourced value carries its reference.

![Workspace](docs/screens/site_workspace.png)

## Results

What works, with numbers:

- **Sorbent bed:** breakthrough times for CALF-20 match published curves to -3%, +2% and +10% (n = 3).
- **Photoreactor:** predicted versus measured ferrioxalate actinometer slope is 0.88 and 0.69 for two setups, inside tolerances we pre-registered, with inputs taken from the paper and not fitted.
- **Ampoule:** diffusion-limited cases agree with OpenFOAM within 2%.
- **Extraction:** 33 real procedures, precision 0.97 and recall 0.83 with no fabricated values (scored with a stand-in model; the offline reader gets 0.95 and 0.73).
- **A concrete, counter-intuitive finding in the tube model:** with the substrate more than about 4 cm from the MoO3 boat, boat temperature barely changes what the substrate sees, because the tube wall takes about 98% of the vapour first. This depends on the wall-uptake assumption: with a reflecting wall the response returns, and our CFD uses a similar wall law. The tool points at that wall behaviour as the thing worth measuring.
- **The verification harness caught real errors,** including a 30 to 60 times error in a published vapour-pressure constant and a wrong edge orientation in one of our own edge-energy models.

What does not work, stated plainly: on 14 literature observations the tube model's direction-of-change calls score 1/9 to 3/9 against 6/9 for a no-tool baseline; MoS2 shape class equals always answering "triangle" (0.50); the CFD surrogates miss their 5% target. All benchmark items are development data, and no held-out set exists yet.

425 automated tests pass (6 skipped without OpenFOAM, 1 expected failure). The closest precedent is Momeni et al., *npj 2D Mater. Appl.* 2:27 (2018), which coupled reactor transport to phase-field growth and validated it on MoS2 islands. What VesselTwin adds is a reusable, uncertainty-aware workflow that starts from procedure text, spans several vessels, and ends in a ranked next calculation.

![What matters most](docs/screens/site_workspace_knobs.png)

## Next steps

1. A pre-registered, held-out test: predictions declared first for a two-factor design (carrier flow and sulfur-boat temperature, three levels each) on one tube.
2. Measure what the model says matters: wall uptake of MoO3, and the substrate temperature offset, which no paper states.
3. Measured furnace temperature profiles to validate the boat and substrate temperatures, which only agree with our own CFD today.
4. Live Tier 2 CFD behind the app, and more vessels from the template.

Code, MIT licence: https://github.com/yeatanir/VesselTwin · Live app: [DEMO_URL] · Author: Anirban Phukan
