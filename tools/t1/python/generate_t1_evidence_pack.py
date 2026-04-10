from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_t1.evidence_pack import build_evidence_pack


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the AiUE T1 static evidence pack.")
    parser.add_argument("--verification-root", default=str((REPO_ROOT / "Saved" / "verification").resolve()))
    parser.add_argument("--output-root")
    parser.add_argument("--latest-root", default=str((REPO_ROOT / "Saved" / "tooling" / "t1" / "latest").resolve()))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = build_evidence_pack(
        verification_root=Path(args.verification_root).expanduser().resolve(),
        output_root=Path(args.output_root).expanduser().resolve() if args.output_root else None,
        latest_root=Path(args.latest_root).expanduser().resolve(),
        repo_root=REPO_ROOT,
    )
    print(f"T1 evidence pack written to: {manifest['artifacts']['run_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
