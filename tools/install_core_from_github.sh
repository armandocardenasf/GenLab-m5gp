#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python "$ROOT/tools/install_core_from_github.py" --project "$ROOT" --copy-tests "$@"
