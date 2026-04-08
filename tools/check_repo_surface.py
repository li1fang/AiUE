from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FILES = [
    "README.md",
    "WHITEPAPER.md",
    "ROADMAP.md",
    "GOVERNANCE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "LICENSE",
    "CHANGELOG.md",
    "docs/aiue_architecture.md",
    "docs/aiue_capture_lab.md",
    "docs/aiue_landscape_positioning.md",
    "docs/aiue_quickstart.md",
    "docs/release_policy.md",
    "docs/schema_handbook.md",
    "docs/test_lanes_and_triplines.md",
    "docs/community_workflow.md",
    "docs/adr/ADR-0001-aiue-product-boundary.md",
    "docs/adr/ADR-0002-stable-cli-and-schema-surface.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/DISCUSSION_TEMPLATE.md",
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/workflow_pack_proposal.yml",
    ".github/ISSUE_TEMPLATE/regression_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/workflows/docs-and-schema.yml",
    ".github/workflows/bundle-audit.yml",
    ".github/workflows/guard-checks.yml",
    ".github/workflows/workspace-dry-run.yml",
    ".github/workflows/hosted-regression.yml",
]


def main():
    parser = argparse.ArgumentParser(description="Check AiUE repo surface files.")
    parser.add_argument("--repo-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    missing = [item for item in REQUIRED_FILES if not (repo_root / item).exists()]
    report = {
        "status": "pass" if not missing else "fail",
        "required_files": len(REQUIRED_FILES),
        "missing_files": missing,
    }
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(1 if missing else 0)


if __name__ == "__main__":
    main()
