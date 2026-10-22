#!/bin/bash
# Run one Tier 2 flask case (steady MRF flow, then frozen-flow tracer pulse). Sources the OpenFOAM v2512 app environment.
# usage: tier2/run_flask.sh <case_dir>      (case_dir from tier2.flask.write_case_flask)
# then:  python -c "from tier2.flask import read_results_flask as r; print(r('<case_dir>', {}))"   (pass the same values)
set -e
command -v blockMesh >/dev/null || source /Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc >/dev/null
cd "${1:?case dir}"
export PWD="$(pwd)"
blockMesh > log.blockMesh
checkMesh > log.checkMesh
cp system/fvSchemes.simple system/fvSchemes; cp system/controlDict.simple system/controlDict
t0=$(foamListTimes -latestTime)  # empty = only 0/ exists; a copied converged time dir skips the steady stage
[ -n "$t0" ] || { simpleFoam > log.simpleFoam; t0=$(foamListTimes -latestTime); }
postProcess -func writeCellVolumes -latestTime > log.post
postProcess -func writeCellCentres -latestTime >> log.post
postProcess -func 'grad(U)' -latestTime >> log.post
cp 0/s "$t0/s"  # simpleFoam does not write the tracer field
setFields -latestTime > log.setFields
cp system/fvSchemes.pimple system/fvSchemes; cp system/controlDict.pimple system/controlDict
pimpleFoam > log.pimpleFoam
tail -n 3 log.pimpleFoam
