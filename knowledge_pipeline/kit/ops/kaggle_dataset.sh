#!/usr/bin/env bash
# Stage a folder and create (first time) or version (later) it as a PRIVATE Kaggle dataset. One blocking call.
#   kit/ops/kaggle_dataset.sh <src-folder> <owner/slug> ["version message"]
# Staging copies <src-folder> to $STAGE (default .kaggle_stage/<slug>, gitignored by new_project.sh) without
# secrets, .git, caches or lock files, writes dataset-metadata.json with "isPrivate": true, then runs the CLI from
# INSIDE the staging folder with -p . (a nested -p path breaks the CLI upload cache on Windows). Subfolders are
# uploaded zipped (-r zip). An existing dataset-metadata.json in <src-folder> is reused only if isPrivate is true.
# Env: KAGGLE_API_TOKEN (else from $VAULT, default secrets/vault.env; never printed), KAGGLE_CMD (default kaggle),
#      PYTHON (default python), TITLE (default slug), MODE=create|version (default: auto via `datasets status`).
# Exit: 0 accepted by Kaggle, 1 CLI refused, 3 refused locally (public metadata or secret-looking file), 4 usage/token.
set -euo pipefail
[ $# -ge 2 ] || { echo 'usage: kaggle_dataset.sh <src-folder> <owner/slug> ["version message"]' >&2; exit 4; }
SRC=$1; REF=$2; MSG=${3:-update}
case "$REF" in */*) ;; *) echo "ref must be owner/slug" >&2; exit 4;; esac
SLUG=${REF#*/}; KAGGLE=${KAGGLE_CMD:-kaggle}; PY=${PYTHON:-python}; VAULT=${VAULT:-secrets/vault.env}
[ -d "$SRC" ] || { echo "no folder $SRC" >&2; exit 4; }

if [ -z "${KAGGLE_API_TOKEN:-}" ] && [ -f "$VAULT" ]; then
  KAGGLE_API_TOKEN=$(grep '^KAGGLE_API_TOKEN=' "$VAULT" | head -1 | cut -d= -f2- | tr -d '\r' || true)
fi
[ -n "${KAGGLE_API_TOKEN:-}" ] || { echo "KAGGLE_API_TOKEN not set and not in $VAULT" >&2; exit 4; }
export KAGGLE_API_TOKEN

# Refuse to upload anything that looks like a credential.
BAD=$(find "$SRC" -type f \( -name '*.env' -o -name 'vault*' -o -name '*.pem' -o -name 'kaggle.json' -o -name '*token*.txt' -o -name '*credential*' -o -name '*key*.txt' \) 2>/dev/null | head -5)
[ -z "$BAD" ] || { echo "refused: secret-looking files in $SRC:" >&2; echo "$BAD" >&2; exit 3; }

STAGE=${STAGE:-.kaggle_stage/$SLUG}
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -R "$SRC"/. "$STAGE"/                                         # cp, not tar: GNU tar reads C:/ paths as a remote host
find "$STAGE" \( -name .git -o -name __pycache__ -o -name secrets -o -name '*.lock' \) -prune -exec rm -rf {} + 2>/dev/null || true

if [ -f "$STAGE/dataset-metadata.json" ]; then
  "$PY" - "$STAGE/dataset-metadata.json" "$REF" <<'PY' || { echo "refused: dataset-metadata.json must have isPrivate true and id $REF" >&2; exit 3; }
import json, sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if d.get("isPrivate") is True and d.get("id") == sys.argv[2] else 1)
PY
else
  "$PY" - "$STAGE/dataset-metadata.json" "$REF" "${TITLE:-$SLUG}" <<'PY'
import json, sys
json.dump({"title": sys.argv[3], "id": sys.argv[2], "licenses": [{"name": "other"}], "isPrivate": True},
          open(sys.argv[1], "w"), indent=2)
PY
fi

MODE=${MODE:-}
if [ -z "$MODE" ]; then
  if $KAGGLE datasets status "$REF" >/dev/null 2>&1; then MODE=version; else MODE=create; fi
fi
cd "$STAGE"                                                      # Windows: run inside the folder with -p .
if [ "$MODE" = create ]; then P=$($KAGGLE datasets create -p . -r zip 2>&1 || true)
else P=$($KAGGLE datasets version -p . -m "$MSG" -r zip 2>&1 || true); fi
echo "$P" | tail -3
# Trust the CLI text, not its exit code: success says the dataset (version) "is being created".
echo "$P" | grep -qi 'being created' || { echo "kaggle refused the $MODE of $REF" >&2; exit 1; }
if echo "$P" | grep -qi 'public'; then echo "WARNING: CLI output mentions public; check $REF visibility now" >&2; fi
echo "$MODE ok: $REF (private) from $SRC"
