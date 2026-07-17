from _bootstrap import CORE_SRC  # noqa: F401
from pathlib import Path


def main() -> None:
    source = CORE_SRC / "m5gp" / "m5gp.py"
    if not source.is_file():
        raise SystemExit(
            "Falta core/src/m5gp/m5gp.py. Ejecute: "
            "python ../../tools/install_core_from_github.py --copy-tests"
        )
    from m5gp import m5gpRegressor, m5gpClassifier
    print("m5gpRegressor:", m5gpRegressor)
    print("m5gpClassifier:", m5gpClassifier)
    print("Importación correcta desde:", source)


if __name__ == "__main__":
    main()
