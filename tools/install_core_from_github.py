#!/usr/bin/env python3
"""Install the original M5GP 2.0 source from GitHub into the canonical core."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_REPO = "https://github.com/armandocardenasf/m5gp-2.0.git"
SOURCE_FILES = (
    "m5gp.py",
    "m5gpGlobals.py",
    "m5gpCudaMethods.py",
    "m5gpCumlMethods.py",
    "m5gpCumlMethods2.py",
    "m5gpMod1.py",
    "m5gpMod2.py",
    "m5gpMod3.py",
    "m5gpSymBuilder.py",
)
TEST_FILES = (
    "m5gp_Test.py",
    "m5gp_Test2.py",
    "m5gp_Test_Classifier.py",
    "m5gp_Digen.py",
    "clasificacion_diabetes.py",
)


def run(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def clone(repo: str, ref: str, destination: Path) -> str:
    try:
        run(["git", "clone", "--depth", "1", "--branch", ref, repo, str(destination)])
    except subprocess.CalledProcessError:
        run(["git", "clone", repo, str(destination)])
        run(["git", "checkout", ref], cwd=destination)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=destination, text=True
    ).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_test_bootstrap(text: str) -> str:
    """Add only the import path needed for direct ``python script.py`` use."""
    marker = "from _bootstrap import CORE_SRC"
    if marker not in text:
        lines = text.splitlines()
        index = 0
        if lines and lines[0].startswith("#!"):
            index = 1
        if index < len(lines) and "coding" in lines[index]:
            index += 1
        while index < len(lines) and lines[index].startswith("from __future__ import"):
            index += 1
        lines[index:index] = ["", marker + "  # noqa: F401"]
        text = "\n".join(lines) + "\n"
    text = text.replace(
        "import m5gpGlobals as gpG",
        "from m5gp import m5gpGlobals as gpG",
    )
    return text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--ref", default="main")
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--copy-tests", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    package = project / "core" / "src" / "m5gp"
    tests = project / "core" / "tests"
    package.mkdir(parents=True, exist_ok=True)
    tests.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="genlab-m5gp-") as temp:
        checkout = Path(temp) / "m5gp-2.0"
        commit = clone(args.repo, args.ref, checkout)
        missing = [name for name in SOURCE_FILES if not (checkout / name).is_file()]
        if missing:
            raise SystemExit("Faltan archivos en el repositorio: " + ", ".join(missing))

        installed = {}
        for name in SOURCE_FILES:
            target = package / name
            shutil.copy2(checkout / name, target)
            installed[name] = sha256(target)

        if args.copy_tests:
            for name in TEST_FILES:
                source = checkout / name
                if source.is_file():
                    (tests / name).write_text(
                        add_test_bootstrap(source.read_text(encoding="utf-8")),
                        encoding="utf-8",
                    )

        info = {
            "repository": args.repo,
            "ref": args.ref,
            "commit": commit,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "files": installed,
        }
        (package / "SOURCE_INFO.json").write_text(
            json.dumps(info, indent=2), encoding="utf-8"
        )
        print(f"M5GP instalado en: {package}")
        print(f"Commit: {commit}")
        if args.copy_tests:
            print(f"Pruebas instaladas en: {tests}")


if __name__ == "__main__":
    main()
