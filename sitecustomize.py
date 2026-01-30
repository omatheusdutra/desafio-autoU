from pathlib import Path
import sys

# Ensure backend/src is importable for tools like RQ workers.
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "backend" / "src"
if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
