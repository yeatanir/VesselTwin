#!/bin/bash
# Run one Tier 2 case. Sources the OpenFOAM v2512 app environment (mounts its volume if needed).
# usage: tier2/run.sh <case_dir>      (case_dir from tier2.openfoam.write_case)
# then:  python -c "from tier2.openfoam import read_results; print(read_results('<case_dir>','cvd_tube',{}))"
set -e
command -v blockMesh >/dev/null || source /Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc >/dev/null
here=$(cd "$(dirname "$0")" && pwd)
cd "${1:?case dir}"
[ "$(sed -n 's/^application *\([A-Za-z]*\);.*/\1/p' system/controlDict)" = ampouleBoussinesqFoam ] && ! command -v ampouleBoussinesqFoam >/dev/null && (cd "$here/foam/ampouleBoussinesqFoam" && wmake >/dev/null)  # custom solver, built once
app=$(sed -n 's/^application *\([A-Za-z]*\);.*/\1/p' system/controlDict)  # buoyantPimpleFoam (tube) or buoyantBoussinesqPimpleFoam (ampoule)
blockMesh > log.blockMesh
checkMesh > log.checkMesh
$app > log.$app
tail -n 3 log.$app
