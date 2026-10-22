# Track P progress
Files touched: streamlit_app.py, .streamlit/config.toml, app/theme.py, app/landing.py, tests/test_landing.py, app/dashboard.py (set_page_config guard + skip old Home tab when embedded), docs/deploy.md (Community Cloud section only), this file.
- Built theme, landing, entry point, tests.
- tests pass for landing/dashboard/home; full make test run next
- Footer set per user (VesselTwin · Anirban Phukan · MIT License · github.com/yeatanir/VesselTwin, linked).
- make test under heavy machine load: 329 passed, 18 failed (test_dashboard/test_vessel_view AppTest timeouts); rerun alone: test_dashboard 5/5, test_vessel_view + test_landing 32/32 pass.
- Not done: no real-browser check (no browser available); Workspace/Evidence show placeholders until Tracks Q lands app/workspace.py and app/evidence.py (render()); workspace must read st.session_state['vt_vessel'].
