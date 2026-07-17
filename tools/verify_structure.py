#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path

SOURCE_FILES = [
    "m5gp.py", "m5gpGlobals.py", "m5gpCudaMethods.py",
    "m5gpCumlMethods.py", "m5gpCumlMethods2.py", "m5gpMod1.py",
    "m5gpMod2.py", "m5gpMod3.py", "m5gpSymBuilder.py",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-source", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "core/src/m5gp"
    duplicates = list((root / "core").glob("**/methods/src"))
    if duplicates:
        raise SystemExit("Duplicidad detectada: " + ", ".join(map(str, duplicates)))
    required = [
        root / "core/src/m5gp/__init__.py",
        root / "integrations/srbench/m5gpRegressor.py",
        root / "integrations/srbench/install_into_srbench.py",
        root / "core/tests/m5gp_Test.py",
        root / "core/tests/m5gp_Test2.py",
        root / "core/tests/m5gp_Test_Classifier.py",
        root / "core/src/m5gp/runtime.py",
        root / "core/tests/m5gp_Test2.py",
        root / "core/tests/m5gp_Test_Classifier.py",
        root / "core/src/m5gp/runtime.py",
        root / "backend/src/genlab_api/main.py",
        root / "frontend/src/main.tsx",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if args.require_source:
        missing.extend(str(source / name) for name in SOURCE_FILES if not (source / name).is_file())
    if missing:
        raise SystemExit("Archivos faltantes:\n- " + "\n- ".join(missing))
    print("Estructura correcta. No existe core/methods/src.")
    if (source / "m5gp.py").is_file():
        print("Código fuente M5GP instalado en la única carpeta canónica.")
    else:
        print("Ejecute tools/install_core_from_github.py para instalar el motor.")


if __name__ == "__main__":
    main()
