from __future__ import annotations

import sys
from pathlib import Path


def ensure_t1_paths() -> Path:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[3]
    python_root = script_path.parent
    core_root = repo_root / "core" / "python"
    adapter_root = repo_root / "adapters" / "unreal" / "python"
    for entry in (python_root, core_root, adapter_root):
        text = str(entry)
        if text not in sys.path:
            sys.path.insert(0, text)
    return repo_root
