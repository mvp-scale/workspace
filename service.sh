#!/usr/bin/env bash
# service.sh -- central start / stop / restart / status for everything in service.yaml.
# The logic is in tools/service.py; what exists and what is "on" lives in service.yaml.  ./service.sh help
cd "$(dirname "${BASH_SOURCE[0]}")" && exec python3 tools/service.py "$@"
