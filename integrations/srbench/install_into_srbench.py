#!/usr/bin/env python3
"""Install M5GP in the SRBench v2 experiment/methods layout."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = "https://github.com/armandocardenasf/m5gp-2.0.git"
SOURCE_FILES = (
    "m5gp.py", "m5gpGlobals.py", "m5gpCudaMethods.py",
    "m5gpCumlMethods.py", "m5gpCumlMethods2.py", "m5gpMod1.py",
    "m5gpMod2.py", "m5gpMod3.py", "m5gpSymBuilder.py",
)


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def clone(repo: str, ref: str, destination: Path) -> str:
    try:
        run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(destination)])
    except subprocess.CalledProcessError:
        run(["git", "clone", repo, str(destination)])
        run(["git", "checkout", ref], cwd=destination)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=destination, text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srbench-root", type=Path, required=True)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = args.srbench_root.resolve()
    methods = root / "experiment" / "methods"
    if not methods.is_dir():
        raise SystemExit(f"No existe la carpeta SRBench esperada: {methods}")
    src_root = methods / "src"
    source_target = src_root / "m5gp"
    adapter_target = methods / "m5gpRegressor.py"
    if source_target.exists() and not args.force:
        raise SystemExit(f"Ya existe {source_target}. Use --force para reemplazarla.")

    integration = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="srbench-m5gp-") as temp:
        checkout = Path(temp) / "m5gp-2.0"
        commit = clone(args.repo, args.ref, checkout)
        missing = [name for name in SOURCE_FILES if not (checkout / name).is_file()]
        if missing:
            raise SystemExit("Faltan archivos en GitHub: " + ", ".join(missing))
        if source_target.exists():
            shutil.rmtree(source_target)
        src_root.mkdir(parents=True, exist_ok=True)
        src_init = src_root / "__init__.py"
        if not src_init.exists():
            src_init.write_text("\n", encoding="utf-8")
        source_target.mkdir(parents=True)
        (source_target / "__init__.py").write_text(
            '"""M5GP source installed from GitHub for SRBench."""\n', encoding="utf-8"
        )
        for name in SOURCE_FILES:
            shutil.copy2(checkout / name, source_target / name)
        shutil.copy2(integration / "m5gpRegressor.py", adapter_target)
        info = {
            "repository": args.repo,
            "ref": args.ref,
            "commit": commit,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }
        (source_target / "SOURCE_INFO.json").write_text(json.dumps(info, indent=2), encoding="utf-8")

    print(f"Adaptador: {adapter_target}")
    print(f"Código fuente: {source_target}")
    print(f"Commit: {commit}")


if __name__ == "__main__":
    main()
