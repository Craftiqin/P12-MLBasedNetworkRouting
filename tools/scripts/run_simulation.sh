#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
command -v inet >/dev/null 2>&1 || { echo "inet missing; enter opp_env shell inet-4.7.0 after installing simulation dependencies." >&2; exit 1; }
: "${INET_ROOT:?INET_ROOT missing; activate the matching INET environment.}"
cd "$ROOT/simulation/inet"
mkdir -p results
inet -u Cmdenv -n "src:$INET_ROOT/src" -f simulations/mesh/omnetpp.ini -c "${1:-Normal}" -r "${2:-0}"
