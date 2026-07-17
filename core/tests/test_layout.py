from pathlib import Path


def main() -> None:
    core = Path(__file__).resolve().parents[1]
    assert not (core / "methods").exists(), "No debe existir core/methods"
    assert (core / "src/m5gp/__init__.py").is_file()
    assert (core / "tests/m5gp_Test.py").is_file()
    print("Estructura core correcta y sin duplicación de fuentes.")


if __name__ == "__main__":
    main()
