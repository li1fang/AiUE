from __future__ import annotations

from _bootstrap import ensure_t2_paths

ensure_t2_paths()

from aiue_t2.app import main


if __name__ == "__main__":
    raise SystemExit(main())
