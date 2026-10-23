# LinkedIn (attach the video here, 4 min or less)

The recipe that worked once, and never twice.

Every synthesis chemist knows this one. You follow a published procedure and the outcome changes. Often the chemistry is the same and the vessel is what differs: a different tube diameter, boat position, stir rate or lamp distance changes the local temperature, precursor flux and light dose at the surface. Almost no methods section reports those.

For the OSI Hackathon 2026 I built VesselTwin. Paste a procedure, and it:
• extracts the setup with an LLM and checks every value against the sentence it came from (the LLM never invents a physical number)
• models the vessel with reduced-order physics, Monte Carlo uncertainty and OpenFOAM CFD, across five vessels: CVD tube furnace, sealed ampoule, stirred flask, sorbent bed and photoreactor
• ranks which knob matters, and which atomistic calculation would change the prediction most
• labels every number as stated, sourced, computed or synthetic

We pre-registered most of our benchmarks before scoring and published every result, including the failures:
✅ CALF-20 CO2 breakthrough within −3% to +10% of published curves
✅ Photoreactor within pre-registered tolerance of ferrioxalate actinometry
❌ Our MoS2 CVD trend model scores 1–3 of 9 against 6 of 9 for a no-tool LLM, and the app says so

Tools that tell you when not to trust them are rare in AI for science. I think they matter more than another confident predictor.

A research prototype. Literature search supported by Valency and Edison Scientific.

🔗 Try it: https://vesseltwin.streamlit.app
💻 Code (MIT): https://github.com/yeatanir/VesselTwin

#AIforScience #MaterialsScience #Chemistry #CFD #OpenFOAM #OSIHackathon

---

# X / Bluesky (short version)

The recipe that worked once, and never twice. Usually the vessel, not the chemistry, is why.

VesselTwin (OSI Hackathon 2026): procedure text in → vessel physics + OpenFOAM with uncertainty → which knob matters and which atomistic calculation to run next. Every number shows its provenance, including where our model fails.

🔗 https://vesseltwin.streamlit.app
💻 https://github.com/yeatanir/VesselTwin
