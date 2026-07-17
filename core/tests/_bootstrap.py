"""Allow historical test scripts to run directly with ``python file.py``."""
from pathlib import Path
import sys

CORE_SRC = Path(__file__).resolve().parents[1] / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))
