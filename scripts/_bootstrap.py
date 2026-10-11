"""Put src/ on sys.path for scripts run without an editable install."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"),):
    if p not in sys.path:
        sys.path.insert(0, p)
