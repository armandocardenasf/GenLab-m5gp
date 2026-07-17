"""Public package for the canonical, unmodified M5GP 2.0 engine.

The original source modules are installed in this directory by
``tools/install_core_from_github.py``.  GenLab contains no second engine copy.
"""
from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys

_CLASS_EXPORTS = {
    "m5gpRegressor": "m5gpRegressor",
    "m5gpClassifier": "m5gpClassifier",
    "M5GPRegressor": "m5gpRegressor",
    "M5GPClassifier": "m5gpClassifier",
}
_LEGACY_MODULES = {
    "m5gpGlobals",
    "m5gpCudaMethods",
    "m5gpCumlMethods",
    "m5gpCumlMethods2",
    "m5gpMod1",
    "m5gpMod2",
    "m5gpMod3",
    "m5gpSymBuilder",
}


def _engine_module():
    if not (Path(__file__).with_name("m5gp.py")).is_file():
        raise ImportError(
            "El código fuente original de M5GP 2.0 no está instalado. "
            "Ejecute desde la raíz: python tools/install_core_from_github.py "
            "--copy-tests"
        )
    # m5gp.py preserves its original absolute sibling imports and adds its own
    # directory to sys.path. This is intentional to keep the original flow.
    return import_module(".m5gp", __name__)


def __getattr__(name: str):
    if name in _CLASS_EXPORTS:
        return getattr(_engine_module(), _CLASS_EXPORTS[name])
    if name in _LEGACY_MODULES:
        _engine_module()
        module = sys.modules.get(name)
        if module is None:
            module = import_module(name)
        return module
    raise AttributeError(name)


__all__ = [*_CLASS_EXPORTS, *_LEGACY_MODULES]
