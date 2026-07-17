#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="${1:-https://github.com/armandocardenasf/GenLab-m5gp.git}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "Git no está instalado." >&2
  exit 1
fi

if [[ ! -d .git ]]; then
  git init -b main
fi

python tools/check_github_repository.py

git add .

# Check the staged index after git add, before committing.
python tools/check_github_repository.py

if git diff --cached --quiet; then
  echo "No hay cambios para confirmar."
else
  git commit -m "Initial GenLab M5GP release"
fi

if git remote get-url origin >/dev/null 2>&1; then
  git remote set-url origin "$REPOSITORY_URL"
else
  git remote add origin "$REPOSITORY_URL"
fi

git push -u origin main
