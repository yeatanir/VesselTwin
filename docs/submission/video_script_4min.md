# VesselTwin: 4-minute video script

Total about 560 words at a calm pace (about 140 words per minute). Format and length are unconfirmed (a reviewer said four minutes; our plan said two): check the event Slack. A 2-minute cut is marked **[2-MIN]**. Screen: the Home page at http://localhost:8501 (or the hosted URL), browser zoom 125%, light theme, sidebar collapsed. Do the click path once off-camera first; the demo procedures load instantly from a stored snapshot.

## 0:00-0:25  Hook  [2-MIN]
*Screen: title card, then the Home page.*
"You read a synthesis paper, copy the recipe, and the result changes. The experimentalist cannot see which hidden variable mattered. The simulation scientist cannot tell which calculation to run. VesselTwin sits in between: it reads the procedure, models the vessel, and tells each of them what to do next. And it tells you how far to trust it."

## 0:25-1:05  Step 1: Procedure  [2-MIN]
*Click: MoS2 CVD tube card. Click 'Read procedure'.*
"This is a real MoS2 recipe. VesselTwin reads it and highlights what it found: blue for stated values, orange for defaults it had to fill in, pink for what is missing. Nothing is invented: every stated value is checked against the sentence it came from."

## 1:05-1:45  Step 2: Vessel  [2-MIN]
*Click Next. Linger on the hero figure.*
"Here is the vessel: boats, substrate, flow, and the temperature field behind it. This picture comes from our own OpenFOAM run. Three numbers matter most, each with its unit and a status dot: model, CFD or synthetic."

## 1:45-2:20  Step 3: What matters  [2-MIN]
*Click Next. Point at the top bar.*
"Which knob should the experimentalist change first? One chart, with uncertainty bars. Behind it is a result that depends on one assumption: if the tube wall soaks up the vapour, a far-away substrate barely feels the boat temperature; if the wall is reflecting, it does. The tool points at that wall behaviour as the thing to measure."

## 2:20-2:50  Step 4: What to calculate
*Click Next.*
"For the simulation scientist: three ranked calculations, with cost labels. These are the atomistic results that would change the prediction most. Not 'run more DFT', but 'run this one'."

## 2:50-3:35  Step 5: How far to trust  [2-MIN]
*Click Next. Show the three-light meter.*
"Now the part that matters most. We tested ourselves. On fourteen literature observations our direction-of-change calls were right on one to three of nine, and a blind agent without our tool got six. Shape prediction is no better than always saying triangle. So every number here is labelled hypothesis, and the tool says so. Where it does work: a sorbent bed within ten percent of published curves, a photoreactor within pre-registered bounds of measured actinometry, and a check that caught a thirty-to-sixty-fold error in a published constant."
*Click 'See the reasoning'.*

## 3:35-3:55  Under the hood
*Open Advanced > Furnace and flow (tube): edit the zone setpoint, click Update. Then sidebar LLM settings for two seconds.*
"For the tube you can edit the furnace itself: zones, boat and substrate positions, flow. The model computes gas, boat and substrate temperature along the tube and flags the flow regime. It agrees with our CFD on the gas side in 45 of 52 stored cases, and no measured temperature has validated it yet. The vessels are drop-in files, and the language model is optional and provider-agnostic: your own key, or fully offline."

## 3:55-4:00  Close  [2-MIN: place after 'How far to trust']
"VesselTwin: the tool that tells you what its own numbers are worth. Next, a pre-registered test on new experiments."

## Click path
1. Home, MoS2 CVD tube card, Read procedure.
2. Next x4, pausing on each step (Vessel hero, bar chart, three cards, trust meter).
3. See the reasoning (opens Reasoning trace).
4. Advanced, Vessel view (scroll to the CFD centrepiece), then Furnace and flow (edit a zone setpoint, Update).
5. Sidebar, LLM settings (show it, do not enter a key on camera).

## Say it straight if asked
- "Does it predict growth?" No. It models transport and flags uncertainty; our direction-of-change score is below a no-tool baseline on a small development set.
- "Is the coupling of reactor and atomistic scales new?" No. Momeni et al. 2018 did it; ours is the reusable, uncertainty-aware, procedure-in workflow.
- "Why trust the CFD?" We do not take it as proof: its wall law resembles Tier 1's, so agreement is not independent evidence. We varied the wall assumption in the model: the boat-temperature response comes back only with a reflecting wall.
- "What did the LLM do?" Read procedures (checked against source spans), and drove a recorded tool loop; the demo itself replays stored runs and needs no API.
