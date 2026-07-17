#!/usr/bin/env python3
from __future__ import annotations
import argparse
import ast
from pathlib import Path

FILES = [
    "m5gp.py", "m5gpGlobals.py", "m5gpCudaMethods.py",
    "m5gpCumlMethods.py", "m5gpCumlMethods2.py", "m5gpMod1.py",
    "m5gpMod2.py", "m5gpMod3.py", "m5gpSymBuilder.py",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srbench-root", type=Path, required=True)
    args = parser.parse_args()
    methods = args.srbench_root.resolve() / "experiment/methods"
    adapter = methods / "m5gpRegressor.py"
    source = methods / "src/m5gp"
    missing = [adapter] + [source / name for name in FILES]
    missing = [path for path in missing if not path.is_file()]
    if missing:
        raise SystemExit("Faltan:\n- " + "\n- ".join(map(str, missing)))
    tree = ast.parse(adapter.read_text(encoding="utf-8"))
    names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assigned = {target.id for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
    required = {"model", "complexity"}
    if not required.issubset(names) or "est" not in assigned:
        raise SystemExit("El adaptador no cumple el contrato: est, model y complexity")
    print("Instalación SRBench correcta:", methods)


if __name__ == "__main__":
    main()
