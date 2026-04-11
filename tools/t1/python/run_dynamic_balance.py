from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_t1.dynamic_balance import write_dynamic_balance_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the AiUE dynamic balance report.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT.resolve()))
    parser.add_argument("--verification-root", default=str((REPO_ROOT / "Saved" / "verification").resolve()))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = write_dynamic_balance_report(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        verification_root=Path(args.verification_root).expanduser().resolve(),
    )
    print(
        "Dynamic balance report written:"
        f" {payload['artifacts']['latest_report_path']}"
        f" | recommendation={payload['recommendation']['next_round_kind']}"
        f" | status={payload['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
