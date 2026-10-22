# VesselTwin: overview and animation brief

Purpose: a 60-75 second animated introduction that plays before the live demo. It states the problem and how VesselTwin bridges it. It is not a demo and shows no real dashboard numbers.

## 1. Overview of the work (plain language)

**The problem.** A paper gives a recipe. You repeat it and the result changes. The experimentalist cannot see what the vessel actually did to the chemistry (local temperature, flow, where the vapour went, how much light reached the sample), so tuning is trial and error. The atomistic simulation scientist has the opposite problem: they can compute almost anything, but do not know which calculation, under which local conditions, would change the experimental outcome. Between the two sits the vessel, and nobody models it.

**What VesselTwin does.**
1. Reads a synthesis procedure as plain text. Every extracted value is tagged stated, default or missing, and checked against the sentence it came from.
2. Models the vessel with physics: a fast regime check, fast reduced-order models with uncertainty bands, and OpenFOAM CFD. Five vessels share one core: MoS2 CVD tube furnace, sealed ampoule, stirred flask, sorbent bed, photoreactor. A new vessel is one added file.
3. Tells the experimentalist which knob moves the outcome, and the simulation scientist which atomistic calculation to run next.
4. Labels every claim benchmarked, uncertain or hypothesis, so the user sees how far to trust it.

**What the language model does.** It reads the procedure and drives a tool loop (extract, solve, rank, look up literature). Literature tools supply sourced parameters. It is optional and provider-agnostic: any provider with your own key, or fully offline.

**Honest state (do not contradict this in the animation).** The tool is a research prototype. It does not predict MoS2 growth outcomes: on our literature benchmark its direction-of-change calls were no better than a no-tool baseline, and shape prediction equals always answering "triangle". Verified strengths: sorbent breakthrough within about 10% of published curves, photoreactor within pre-registered tolerance of measured actinometry, diffusion-limited ampoule cases match CFD, and a verification harness that catches errors, including its own. The claim is the bridge and the honesty, not accuracy.

## 2. Animation: style and constraints

- Length 60-75 s, 16:9, 1920x1080, 24 or 30 fps. Silent-readable (captions on screen) with voice-over.
- Style: clean scientific motion graphics, blue and white (primary blue #1F5FBF, navy #0B2545, pale blue #EEF4FC, one orange accent #F28C28 used only for "the unknown"). Flat vector look, soft glow, generous white space. No photorealistic faces, no logos, no brand names of other products, no real paper figures.
- On-screen text must be exact. AI video models garble text and labels, so do all text, diagrams and the VesselTwin reveal as vector motion graphics, and use AI video only for short atmospheric clips without text.
- Do not show invented numbers, accuracy claims, or dashboard screenshots. Show the app only as a stylised UI shape.

## 3. Shot list and voice-over (about 170 words, 65-70 s at a calm pace)

| # | Time | Visual | On-screen text | Voice-over |
|---|---|---|---|---|
| 1 | 0-8 s | Dark-to-light blue. A glowing quartz tube furnace in cross-section, gas dashes flowing through it, a small boat inside. A faint orange question mark pulses at the substrate. | "What is happening inside?" | "Every synthesis happens inside a vessel. And inside it, almost nothing is visible." |
| 2 | 8-20 s | Left half: stylised experimentalist at a bench (silhouette), a paper recipe on a desk, a failed sample, a notebook with crossed-out numbers. Dials labelled with temperature, flow, position turning in a loop. | "Why did the recipe change?" | "The experimentalist copies a published recipe. The result changes. Was it the local temperature? The flow? Where the vapour went? They tune by trial and error." |
| 3 | 20-32 s | Right half: simulation scientist silhouette at a screen with a molecule or crystal edge and a long queue of calculation icons, most greyed out. A single orange question mark above them. | "Which calculation matters?" | "The simulation scientist can compute almost anything. But which calculation, under which real conditions, would change the experiment? Nobody can tell." |
| 4 | 32-38 s | The two halves slide apart; a gap opens between them filled with an orange blur labelled by the vessel icon. | "Between them: the vessel" | "Between the two sits the vessel. And nobody models it." |
| 5 | 38-50 s | Blue bridge builds across the gap. VesselTwin appears: a procedure text card flows in, a tube model lights up with temperature and flow lines (a CFD-style field), then two outputs split to the two sides: a ranked knob bar chart to the experimentalist, a ranked list of calculations to the simulation scientist. | "VesselTwin" / "Read the procedure -> Model the vessel -> Say what matters" | "VesselTwin reads the procedure, models the vessel with physics, and tells each of them what to do next. Which knob matters. Which calculation matters." |
| 6 | 50-60 s | Five vessel icons light in sequence: tube furnace, sealed ampoule, stirred flask, sorbent bed, photoreactor, each with a tiny animated hint (gas flow, convection, swirl, front moving, light rays). A small AI chip icon labelled "any model or none" connects to the stack. | "Five vessels, one core" / "Bring your own LLM, or none" | "Five vessels, one plug-and-play core. Language models read the procedure and call the physics. Bring your own model, or run offline." |
| 7 | 60-70 s | A three-light trust meter (benchmarked, uncertain, hypothesis) glows beneath the output cards. Feedback loop arrow: better calculation -> better model -> better next experiment, closing the circle. End on the VesselTwin wordmark and the line below. | "Know how far to trust it" / "Better experiments. Better simulations." | "And it always says how far to trust itself. So experiments are tuned with physics, simulations are aimed where they matter, and each improves the other. VesselTwin." |

Total voice-over word count is about 175. If it runs long, cut the second sentence of shot 2 and the whole of shot 6's second sentence.

## 4. Master prompt for an agent (paste as is)

"""
Create a 65-70 second 16:9 scientific explainer animation titled 'VesselTwin' using the shot list below. Style: flat vector motion graphics, blue and white palette (primary #1F5FBF, navy #0B2545, pale blue #EEF4FC, orange accent #F28C28 only for the unknown or the question mark), soft glow, lots of white space, no photorealistic people (use simple silhouettes), no logos or brand names, no real paper figures. All on-screen text must be exactly as written and set as vector text, not generated inside AI video. Include captions for all narration. Keep a calm, clear, non-hype tone. Do not show any numbers, accuracy claims or real software screenshots. The story: an experimentalist and an atomistic simulation scientist each cannot see what happens inside the reaction vessel (temperature, flow, where vapour travels, light dose); between them is an unmodelled gap; VesselTwin bridges it by reading a synthesis procedure, modelling the vessel with physics, and telling the experimentalist which knob matters and the simulation scientist which calculation matters, with a trust meter showing how far to trust each claim, across five vessels (tube furnace, sealed ampoule, stirred flask, sorbent bed, photoreactor), working with any language model or none, creating a loop of better experiments and better simulations. Shots and narration: [paste the table in section 3]. Deliver: a silent video with captions, a separate narration script, and an editable project file.
"""

## 5. What to use (verify current availability and licensing yourself; I could not check live)

- **Best result, most control: motion graphics for everything with text or diagrams.** Manim (free, Python, designed for scientific explainers), Remotion (code-based video), or Keynote/PowerPoint exported to video. Animate the tube, gas dashes, bridge, trust meter and wordmark here. It is exact and you can edit it tonight.
- **AI video only for short mood clips (shots 1-3 backgrounds, 3-5 s each, no text):** current text-to-video tools such as Runway, Google Veo, Kling, Luma or Pika. Prompt them for abstract blue glowing tube furnace and silhouette lab scenes, then overlay text yourself. Expect to regenerate several times.
- **Voice-over:** your own voice (best for a hackathon), or an AI voice tool such as ElevenLabs. Record to a click-free room, 140 words per minute.
- **Assembly and captions:** DaVinci Resolve (free) or CapCut. Export 1080p MP4, then place before the demo.
- **Fastest safe route given the time (about 90 minutes):** build shots 1, 4, 5, 6, 7 in Keynote or Manim, use two or three AI clips for shots 2 and 3 or simple silhouettes drawn in vector, record your voice, assemble in CapCut.

## 6. Checks before you publish

- Every number or claim in the voice-over is covered by the honest-state paragraph above. Nothing says VesselTwin predicts growth or beats experiments.
- No third-party logos, no paper figures, no real people.
- Narration under 70 s. Captions readable on a phone.
- Footer line: VesselTwin, Anirban Phukan, MIT License.
