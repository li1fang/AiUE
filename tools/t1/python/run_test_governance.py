from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_t1.test_governance import write_test_governance_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the AiUE test governance report.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT.resolve()))
    parser.add_argument("--verification-root", default=str((REPO_ROOT / "Saved" / "verification").resolve()))
    parser.add_argument("--coverage-ledger", default=str((REPO_ROOT / "docs" / "governance" / "test_coverage_ledger_round1.json").resolve()))
    parser.add_argument("--change-source", choices=["worktree", "head"], default="worktree")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = write_test_governance_report(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        verification_root=Path(args.verification_root).expanduser().resolve(),
        coverage_ledger_path=Path(args.coverage_ledger).expanduser().resolve(),
        change_source=str(args.change_source),
    )
    print(
        "Test governance report written:"
        f" {payload['artifacts']['latest_report_path']}"
        f" | status={payload['status']}"
        f" | checkpoint_ready={payload['checkpoint_readiness']['ready']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
