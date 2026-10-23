VesselTwin links a written synthesis procedure to the physical conditions it creates inside the vessel, and from there to the atomistic calculations worth running. A language model extracts the setup and checks every value against its source sentence. Reduced-order transport models with Monte Carlo uncertainty, and OpenFOAM CFD, then estimate local temperature, precursor flux and light dose. A sensitivity ranking shows which knob and which atomistic parameter the result depends on. Every number carries its provenance (stated, sourced, computed or synthetic) and every claim a trust label. Our photoreactor model matches published actinometry within pre-registered tolerances, and our sorbent-bed model matches published CALF-20 breakthrough curves. Our flagship MoS2 CVD model does not beat a no-tool baseline, and the tool reports that rather than hiding it.

[Figure 1: drop in docs/screens/site_home.png]
*Figure 1. The idea: recipe in; local conditions, the knob that matters, and the next calculation out.*

## The problem

A published recipe often fails to reproduce. Between the chemistry and the outcome sits the vessel. Tube diameter, boat position, carrier flow, stir rate and lamp distance set the local temperature, supersaturation and photon dose at the growing surface, and the methods section rarely reports those. Experimentalists tune them by trial and error. Atomistic modellers can compute edge energies or adsorption barriers, but cannot tell which calculation, under which local conditions, would change the experimental outcome. Reactor-scale transport coupled to growth has been done for single systems (Momeni et al., *npj 2D Mater. Appl.* 2, 27, 2018). What is missing is a reusable, procedure-in workflow across vessel types that states its own uncertainty.

## Approach

**Extraction.** A language model, or an offline rule reader, maps procedure text onto a typed schema (`SetupSpec`). Each value is tagged *stated*, *default* or *missing*, and each stated value is span-checked against the sentence it came from. The model never produces a physical number. Any LLM provider works, and the whole pipeline also runs offline.

**Vessel physics in three tiers.** Tier 0 is a regime call from dimensionless groups, for example a Damköhler number $\mathrm{Da}=k_s/k_m$ with $k_m=\mathrm{Sh}\,D/d_h$ and $\mathrm{Sh}=3.66$ for developed laminar flow. Tier 1 is a reduced-order model with Monte Carlo propagation of every parameter's uncertainty, reported as p05/p50/p95 and fast enough to recompute as a slider moves. Tier 2 is OpenFOAM v2512 CFD, including a custom buoyant species solver for the ampoule, with grid-convergence indices where a case was meshed three times. The reduced-order models are:

- **CVD tube:** Hertz–Knudsen evaporation, plug flow with wall condensation.
- **Sealed ampoule:** Schäfer chemical vapour transport.
- **Stirred flask:** a Villermaux–Dushman micromixing time scale.
- **Sorbent bed:** an LDF/Langmuir non-isothermal column.
- **Photoreactor:** Beer–Lambert absorption, giving the actinometer rate $d[\mathrm{Fe^{2+}}]/dt=\Phi\,q_{abs}/V$.

**Bridge to atomistic simulation.** Each atomistic input, such as an edge energy or a binding energy, enters through a `Closure` object with its source and uncertainty. A one-at-a-time sensitivity of the headline output ranks which of these calculations would move the prediction most. For the MoS2 tube the headline output, a shape boundary, comes from an unvalidated edge-rate model, so that ranking is labelled *hypothesis*.

**Honesty by construction.** Five vessels share one core, and a new vessel is one Python file. Benchmarks were pre-registered before scoring. A claim's label (*benchmarked*, *uncertain* or *hypothesis*) is capped by its weakest input.

[Figure 2: drop in docs/screens/site_workspace.png]
*Figure 2. Workspace for the MoS2 tube. The field shown is a stored OpenFOAM result. The tiles mark whether each number is a model estimate, a CFD result or rests on synthetic inputs.*

## Results

[Figure 3: drop in fig_evidence.png]
*Figure 3. (A) Predicted/measured ratio against published experiments. (B) MoS2 direction-of-change calls against two baselines. All MoS2 items are development data.*

- **Sorbent bed (validation).** CALF-20 CO2 breakthrough times match three published curves to −3%, +2% and +10%. The curves are three feed compositions on one column, and the parameters come from the same thesis (Nguyen, 2021). For zeolite 13X the model is 38–39% early, because the bed runs too hot. A wall heat-transfer fit narrowed this but missed its pre-registered threshold, so it was not adopted.
- **Photoreactor (validation).** Predicted versus measured ferrioxalate actinometer rate is 0.88 for a collimated beam and 0.69 for diffuse illumination. Both are inside tolerances set before comparison (×1.25 and ×1.5). The quantum yield comes from Hatchard & Parker (1956), and the setups from Saenz et al., *Heliyon* (2024). The model took the paper's measured irradiance as input, so this tests the absorption and actinometry chain, not the lamp-to-irradiance step. Both setups are from one lab.
- **Sealed ampoule.** In the diffusion-limited regime, Tier 1 agrees with our OpenFOAM solver within 2% (a code-to-code check). Against published WO2/HgX2 transport rates the model over-predicts by 1× to 38×.
- **Regime calls.** Tier 0 agrees with the CFD regime label in 37 of 40 tube cases. The rule was revised after we saw the original misses, and the CFD label is our own convention.
- **Extraction.** We scored 33 published procedures (113 annotated fields; the annotations were made during development, not by independent annotators). A Claude model blind to the annotations scored precision 0.97 and recall 0.83, with no fabricated values. The offline reader, which was developed on the same set, scored 0.95 and 0.73.
- **MoS2 CVD (does not work yet).** Direction-of-change calls on 9 modellable literature observations score 1/9 to 3/9, against 6/9 for a no-tool LLM and 4/9 for always answering "increase". Shape-class accuracy is 0.50, the same as always answering "triangle". CFD surrogates miss their 5% target (leave-one-out median error 24–36%).
- **A model-dependent finding worth testing.** With condensing tube walls, about 98% of the MoO3 vapour deposits on the wall before reaching a substrate more than about 4 cm downstream, so the substrate barely feels the boat temperature. With a reflecting wall the response returns. Our CFD uses a similar wall law, so it is not independent evidence. Wall uptake is therefore the measurement the tool points to.
- **What the checks caught.** A literature cross-check found that a MoO3 vapour-pressure value we had taken from an OCR'd table was 30–60× too low (it was replaced by Smolik et al., 2000). The checks also caught a wrong edge orientation in one of our edge-energy models.

## Next steps

1. Run a held-out, pre-registered test: predictions are declared before a 3×3 experiment on one tube (carrier flow × sulfur temperature).
2. Measure the quantities the model says matter: MoO3 wall uptake, the substrate temperature offset, and the furnace temperature profile.
3. Score the deployed language model on held-out procedures, and run live CFD behind the app.
4. Add more vessels from the template.

Code (MIT): https://github.com/yeatanir/VesselTwin · Live app: https://vesseltwin.streamlit.app · Development began Oct 18, 2026 in a private repository; see the README.
