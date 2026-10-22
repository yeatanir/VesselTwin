# Track I progress
Branch track-i (from origin/polish). Deadline Oct 21 17:00 ET. Edison credits 0. No OpenFOAM. No long-running PIDs.

## Files I will touch
vessels/cvd_tube/thermo.py, vessels/cvd_tube/__init__.py (psat_model choices only), vessels/cvd_tube/wulff.py, vessels/cvd_tube/momeni_edges.py (new),
bench/track_i_score.py (new, imports track_a_score), bench/track_i/ (new), tests/test_track_i.py (new), docs/prereg/track-i.md, docs/track_i_results.md,
docs/progress/track-i.md, docs/handoff/requests-i.md.
- committed prereg cdeac2d; scorer bench/track_i_score.py; tests fixed. Next: run scorer once (--write), results doc.
- scored once (after prereg cdeac2d): bench/track_i/results.json, docs/track_i_results.md written. Neither part passes. Next: make test, push track-i.
- Addendum B: read supplied PDFs; found ZZS2 orientation error (Cao 2015 p.4296), implemented v2 as momeni_eq (v1 kept as momeni_eq_v1), pre-registered then ran --addendum; D1 0/6, D2 only v1 (accidental); M5 fails. Next: make test, push.
