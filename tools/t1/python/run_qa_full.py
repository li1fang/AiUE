from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_t1_paths

REPO_ROOT = ensure_t1_paths()

from aiue_t1.qa_full import write_qa_full_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE QA-full nightly orchestrator.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT.resolve()))
    parser.add_argument("--profile", default=str((REPO_ROOT / "examples" / "qa" / "qa_full_nightly.example.json").resolve()))
    parser.add_argument("--output-root", default="")
    parser.add_argument("--latest-report-path", default="")
    parser.add_argument("--lane-id", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lane_ids: list[str] = []
    for item in list(args.lane_id or []):
        text = str(item or "")
        if not text:
            continue
        lane_ids.extend(part.strip() for part in text.split(",") if part.strip())
    payload, _, latest_report_path, exit_code = write_qa_full_report(
        repo_root=Path(args.repo_root).expanduser().resolve(),
        profile_path=Path(args.profile).expanduser().resolve(),
        output_root=Path(args.output_root).expanduser().resolve() if args.output_root else None,
        latest_report_path=Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else None,
        lane_ids=lane_ids,
    )
    print(
        "QA profile report written:"
        f" {latest_report_path}"
        f" | gate_id={payload['gate_id']}"
        f" | status={payload['status']}"
        f" | hard_failures={len(payload['hard_failures'])}"
        f" | soft_findings={len(payload['soft_findings'])}"
        f" | expected_watchlist={len(payload['expected_watchlist'])}"
    )
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
