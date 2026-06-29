"""Ensure dashboard package root is on sys.path for multipage imports."""

import sys
from pathlib import Path

_DASHBOARD_ROOT = Path(__file__).resolve().parent
if str(_DASHBOARD_ROOT) not in sys.path:
    sys.path.insert(0, str(_DASHBOARD_ROOT))
