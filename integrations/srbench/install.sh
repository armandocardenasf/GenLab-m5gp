#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ $# -lt 1 ]]; then
  echo "Uso: $0 /ruta/srbench [--ref main] [--force]" >&2
  exit 2
fi
SRBENCH_ROOT="$1"
shift
exec python "$HERE/install_into_srbench.py" --srbench-root "$SRBENCH_ROOT" "$@"
