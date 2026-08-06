"""Executable entry point for CashCow Launcher."""

import sys
from pathlib import Path

# Add project root to sys.path so 'launcher' package imports work cleanly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from launcher.launcher import main

if __name__ == "__main__":
    main()
