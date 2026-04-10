from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
for entry in (
    REPO_ROOT / "core" / "python",
    REPO_ROOT / "adapters" / "unreal" / "python",
    REPO_ROOT / "tools" / "t1" / "python",
    REPO_ROOT / "tools" / "t2" / "python",
):
    text = str(entry)
    if text not in sys.path:
        sys.path.insert(0, text)
