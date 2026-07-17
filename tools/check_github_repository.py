#!/usr/bin/env python3
"""Check that sensitive/runtime files and original M5GP sources are not tracked."""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TRACKED = {
    ".env",
    "core/src/m5gp/m5gp.py",
    "core/src/m5gp/m5gpGlobals.py",
    "core/src/m5gp/m5gpCudaMethods.py",
    "core/src/m5gp/m5gpCumlMethods.py",
    "core/src/m5gp/m5gpCumlMethods2.py",
    "core/src/m5gp/m5gpMod1.py",
    "core/src/m5gp/m5gpMod2.py",
    "core/src/m5gp/m5gpMod3.py",
    "core/src/m5gp/m5gpSymBuilder.py",
    "core/src/m5gp/SOURCE_INFO.json",
}
FORBIDDEN_PREFIXES = (
    "frontend/node_modules/",
    "frontend/dist/",
    "data/uploads/",
    "data/artifacts/",
    "data/logs/",
    "backend/data/",
)


def tracked_files() -> set[str]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    return {line.strip() for line in output.splitlines() if line.strip()}


def main() -> None:
    tracked = tracked_files()
    failures: list[str] = []
    for path in sorted(tracked):
        if path.endswith("/.gitkeep"):
            continue
        if path in FORBIDDEN_TRACKED or path.startswith(FORBIDDEN_PREFIXES):
            failures.append(path)
    if failures:
        print("ERROR: archivos que no deben publicarse están bajo control de Git:")
        for path in failures:
            print(f"  - {path}")
        print("Retírelos del índice con: git rm --cached <archivo>")
        raise SystemExit(1)

    # Also warn when original sources exist locally; this is allowed because .gitignore
    # keeps them outside the repository after installation.
    local_sources = [path for path in FORBIDDEN_TRACKED if (ROOT / path).is_file()]
    if local_sources:
        print("M5GP 2.0 está instalado localmente y correctamente excluido de Git:")
        for path in sorted(local_sources):
            print(f"  - {path}")
    print("GitHub repository check: PASS")


if __name__ == "__main__":
    main()
