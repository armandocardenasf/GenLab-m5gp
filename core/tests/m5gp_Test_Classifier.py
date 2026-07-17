"""This historical script is installed from the official M5GP Git repository."""
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    raise SystemExit(
        "Este archivo se reemplaza por su versión original desde GitHub. Ejecute:\n"
        f"  cd {root}\n"
        "  python tools/install_core_from_github.py --ref main --copy-tests"
    )


if __name__ == "__main__":
    main()
