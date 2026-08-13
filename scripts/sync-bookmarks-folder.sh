#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PROJECT_ROOT="$(pwd)"
PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
    PYTHON_BIN="python3"
fi

BOOKMARKS_URL="${BOOKMARKS_URL:-${LEEKNOWLEDGE_BOOKMARKS_URL:-https://x.com/i/bookmarks}}"
CDP_ENDPOINT="${CDP_ENDPOINT:-${LEEKNOWLEDGE_CHROME_CDP_ENDPOINT:-http://127.0.0.1:9222}}"
RAW_OUTPUT_DIR="${RAW_OUTPUT_DIR:-data/raw}"
DB_PATH="${DB_PATH:-state/app.db}"
VAULT_DIR="${VAULT_DIR:-vault}"

if [ "$#" -gt 0 ]; then
    BOOKMARKS_URL="$1"
fi

export PYTHONPATH=src

"${PYTHON_BIN}" -m leeknowledge sync \
  --cdp-endpoint "${CDP_ENDPOINT}" \
  --bookmarks-url "${BOOKMARKS_URL}" \
  --raw-output-dir "${RAW_OUTPUT_DIR}" \
  --db-path "${DB_PATH}" \
  --vault-dir "${VAULT_DIR}"
