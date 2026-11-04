#!/usr/bin/env bash
# kp-status.sh: one screen for the knowledge pipeline (local only, no API calls). Usage: ./kp-status.sh [seconds] | --once
exec python3 "$(dirname "$(readlink -f "$0")")/tools/hw.py" "$@"
