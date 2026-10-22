# conda env with pydantic/pint/pytest/scipy/sklearn already installed
PY ?= /Users/yeatanir/miniconda3/envs/research/bin/python

.PHONY: test demo harness dashboard dryrun
test:
	$(PY) -m pytest -q
demo:
	$(PY) -m core.pipeline
harness: test
	@cat cache/harness.json | $(PY) -c "import json,sys; r=json.load(sys.stdin); print(sum(x['outcome']=='passed' for x in r),'/',len(r),'passed')"
dashboard:
	$(PY) -m streamlit run app/dashboard.py

dryrun:
	$(PY) scripts/demo_dryrun.py --cold
