#!/bin/bash
# Steady stage only of tier2/run_flask.sh (mesh, checkMesh, simpleFoam) for Np mesh studies. usage: flask_np_run.sh <case_dir>
set -e
command -v blockMesh >/dev/null || source /Applications/OpenFOAM-v2512.app/Contents/Resources/etc/bashrc >/dev/null
cd "${1:?case dir}"; export PWD="$(pwd)"
echo "pid $$ $(date)" > run.pid
blockMesh > log.blockMesh; checkMesh > log.checkMesh
cp system/fvSchemes.simple system/fvSchemes; cp system/controlDict.simple system/controlDict
simpleFoam > log.simpleFoam
echo "done $(date)" >> run.pid
