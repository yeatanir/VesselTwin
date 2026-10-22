# VesselTwin: live 4-minute demo script (you speak, you drive the site)

About 560 spoken words at 140 words per minute. Click path, timings and what to say are in each row. The animated intro video plays before this and covers the problem, so you start on the product.

## Before you record (5 minutes)

- Open the Cloud site in a fresh browser window, zoom 110-125%, light theme, one tab, notifications off. Open it once 2 minutes before and click through Home, Workspace, Studio, Evidence so the app is warm (a cold Cloud app is slow).
- Start on **Home**. Do not enter any API key on camera. Do not open Advanced.
- Do one dry run. Moving a slider takes about a second; wait for the number to change before you talk about it.
- If something is slow, keep talking about what you will show; never say "it's loading" for more than a beat.

## Script

| Time | On screen and what to click | What to say |
|---|---|---|
| 0:00-0:25 | **Home.** Stay on the hero. Let the animation run: recipe lines flow into the glowing tube, out to the two cards. Point at the left card, then the two right cards. | "This is VesselTwin. A synthesis recipe goes in on the left. The vessel in the middle is modelled with physics. Out come two answers: which knob matters, for the experimentalist, and which calculation matters, for the simulation scientist." |
| 0:25-0:50 | Scroll slowly past the two-people section, then the three steps, to **the five vessel cards**. Hover one card so it lifts. | "Most failures are the vessel, not the chemistry, and each audience sees half of it. Five vessels share one core: a CVD tube furnace, a sealed ampoule, a stirred flask, a sorbent bed and a photoreactor. Adding a vessel is one file." |
| 0:50-1:05 | Click **Open** on the tube furnace card. You land in the **Workspace** with the tube selected. | "Let's open the flagship, a tube furnace for MoS2 growth." |
| 1:05-1:35 | Workspace top: point at the **vessel cards**, then the big figure and the three **big-number tiles** (gas temperature, MoO3 reaching the substrate, and so on). | "The workspace gives you the vessel, live. Here are the gas temperature and how much of the MoO3 vapour reaches the substrate. Every number has its unit and a status dot that says whether it is a model result, from CFD, or from a synthetic input." |
| 1:35-2:10 | Move **Furnace temperature** with its slider, wait for the tiles to change and for the small "solved in … s" badge. Then move **Carrier flow**. Point at the effect bars next to the knobs. | "Now I change the furnace temperature. This is Tier 1: a fast physics model that recomputes as I move a slider, with uncertainty bands. The tiles move, and the bars show which knob moves the result most. That is the question the experimentalist cannot answer by eye." |
| 2:10-2:30 | Click the **Live model | Stored CFD** control and switch to **Stored CFD**. Point at the flow field with streamlines. Switch back. | "For deeper checks there are OpenFOAM CFD fields. The hosted site shows stored runs, labelled as stored, not re-run. On a workstation the same pipeline runs the solver." |
| 2:30-2:45 | Click the **Photoreactor** card in the picker. The figure and knobs change. Move **Lamp power** or **Lamp distance** once. | "Switch vessels and the physics changes: here, light dose in a photoreactor. Lamp power, distance, wall thickness." |
| 2:45-3:10 | Click **Studio** in the top bar. On **Ask the agent**, click one of the example procedures, press **Run agent**. Let the timeline play. (If no model is connected it replays a recorded run and says so.) | "The language model's role is visible here. It reads the procedure, calls the physics tools, and explains. It never invents a number. Here is a recorded run; with your own key it runs live, with any provider or none." |
| 3:10-3:25 | Click the **Add a vessel** tab. Point at the five template cards and the form. Do not fill it in. | "And you can add your own vessel: pick a physics template, set its dimensions, and it runs with borrowed physics, honestly labelled as unvalidated, with a stub file for a developer to make it real." |
| 3:25-3:50 | Click **Evidence & literature** in the top bar. Show the **Reasoning trace** tab, then the **Benchmarks** tab (point at the table), then the **Literature** tab (the Edison and Valency cards). | "Here is why you can trust it, or not. Every claim is labelled benchmarked, uncertain or hypothesis. Our own tests are published, including the ones we fail: on literature benchmarks the tube model does not beat a no-tool baseline. Literature agents, Edison Scientific and Valency, supply the sourced parameters." |
| 3:50-4:00 | Click **Home** (logo or Home link). Hold on the logo. | "VesselTwin. Physics for the vessel, your choice of language model, and honest labels on every number. Thank you." |

## Safe things to say if asked

- **"Does it predict growth?"** "No. It models transport and flags uncertainty. Our direction-of-change score is below a no-tool baseline on a small development set, and we publish that."
- **"Is the reactor-to-atomistic coupling new?"** "No: Momeni and colleagues did it in 2018 and validated it on MoS2 islands. Ours is reusable across vessels, uncertainty-aware, and starts from procedure text."
- **"Why is the CFD stored?"** "The hosted site cannot run OpenFOAM. Locally the Tier 2 cases run; the tube and ampoule fields shown are from our runs."
- **"What does the LLM do?"** "Reads procedures with every value checked against its source sentence, and drives the tool loop. Physical numbers come from the models, never from the LLM."

## Things not to say or show

- Do not say "validated", "accurate", "predicts" or "beats experiments".
- Do not claim the photoreactor or flask are validated. The photoreactor matched two actinometry setups within pre-registered tolerance; the flask CFD is not mesh-converged.
- Do not enter keys; do not open Advanced; do not run the sorbent bed's knob-effects toggle on camera (about 20 seconds).
- The stored CFD figure for the tube can appear under "Live model": if it does, say "the field behind is a stored CFD result".

## Trim to 2 minutes

Keep: 0:00-0:25 hero, 1:05-1:35 workspace, 1:35-2:10 knobs, 3:25-3:50 evidence (shortened to the benchmarks tab), 3:50-4:00 close. Drop the vessel cards tour, Stored CFD, Photoreactor and Studio.
