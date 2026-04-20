from __future__ import annotations

import json
from pathlib import Path

from aiue_core.schema_utils import load_json, write_json
from aiue_t1.qa_full import build_qa_full_report


def _write_fake_lane_script(path: Path) -> Path:
    path.write_text(
        """
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--report")
parser.add_argument("--gate-id")
parser.add_argument("--status", default="pass")
parser.add_argument("--sequence-file", default="")
parser.add_argument("--sequence", nargs="*", default=[])
parser.add_argument("--package-id", default="pkg_alpha")
args = parser.parse_args()

status = args.status
if args.sequence_file:
    sequence_file = Path(args.sequence_file)
    index = int(sequence_file.read_text(encoding="utf-8")) if sequence_file.exists() else 0
    sequence = list(args.sequence or [args.status])
    if index >= len(sequence):
        index = len(sequence) - 1
    status = sequence[index]
    sequence_file.parent.mkdir(parents=True, exist_ok=True)
    sequence_file.write_text(str(index + 1), encoding="utf-8")

payload = {
    "gate_id": args.gate_id,
    "status": status,
    "counts": {"run_count": 1},
    "resolved_package_ids": [args.package_id],
    "per_package_results": [{"package_id": args.package_id}],
    "failed_requirements": [] if status == "pass" else [{"id": f"{args.gate_id}_failed"}],
}
report_path = Path(args.report)
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\\n", encoding="utf-8")
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _profile_path(tmp_path: Path, lanes: dict, lane_order: list[str]) -> Path:
    workspace_config = tmp_path / "workspace.local.json"
    write_json(workspace_config, {"paths": {}})
    profile_path = tmp_path / "qa_profile.json"
    write_json(
        profile_path,
        {
            "runtime_budget_class": "test",
            "workspace_refs": {
                "main": str(workspace_config),
            },
            "lane_order": lane_order,
            "lane_registry": lanes,
        },
    )
    return profile_path


def _profile_path_with_payload(tmp_path: Path, payload: dict) -> Path:
    workspace_config = tmp_path / "workspace.local.json"
    write_json(workspace_config, {"paths": {}})
    profile_path = tmp_path / "qa_profile.json"
    merged = {
        "runtime_budget_class": "test",
        "workspace_refs": {
            "main": str(workspace_config),
        },
        **payload,
    }
    write_json(profile_path, merged)
    return profile_path


def test_qa_full_passes_with_expected_soft_watchlist_only(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    write_json(
        verification_root / "latest_manual_playable_demo_validation_pv1_report.json",
        {
            "gate_id": "manual_playable_demo_validation_pv1",
            "status": "attention",
            "success": False,
            "checked_package_ids": ["pkg_alpha"],
        },
    )
    write_json(
        verification_root / "latest_test_governance_round1_report.json",
        {
            "gate_id": "test_governance_round1",
            "status": "attention",
            "checkpoint_readiness": {
                "high_priority_automation_blind_spot_ids": [],
                "high_priority_signoff_blind_spot_ids": ["manual_playable_demo_validation"],
            },
            "coverage_summary": {
                "high_priority_automation_missing_ids": [],
                "high_priority_signoff_missing_ids": ["manual_playable_demo_validation"],
            },
        },
    )
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "hard_pass": {
                "severity": "hard",
                "mode": "command",
                "group": "preflight",
                "report_gate_id": "hard_pass_gate",
                "latest_report_path": str(verification_root / "latest_hard_pass_gate_report.json"),
                "signature_paths": ["status", "counts", "@package_ids"],
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_hard_pass_gate_report.json"),
                    "--gate-id",
                    "hard_pass_gate",
                    "--status",
                    "pass",
                ],
            },
            "manual_playable_demo_validation_pv1": {
                "severity": "expected_soft",
                "mode": "snapshot",
                "group": "watchlist",
                "report_gate_id": "manual_playable_demo_validation_pv1",
            },
            "test_governance_round1": {
                "severity": "expected_soft",
                "mode": "snapshot",
                "group": "watchlist",
                "report_gate_id": "test_governance_round1",
            },
        },
        lane_order=[
            "hard_pass",
            "manual_playable_demo_validation_pv1",
            "test_governance_round1",
        ],
    )

    payload, report_path, latest_report_path, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )

    assert payload["status"] == "pass"
    assert len(payload["hard_failures"]) == 0
    assert len(payload["root_failures"]) == 0
    assert len(payload["cascade_failures"]) == 0
    assert len(payload["environment_failures"]) == 0
    assert len(payload["soft_findings"]) == 0
    assert len(payload["expected_watchlist"]) == 2
    assert payload["expected_watchlist"][0]["reason"] == "manual_signoff_pending"
    assert payload["watchlist_only"]["status"] is True
    assert exit_code == 0
    assert report_path.name == "qa_full_nightly_report.json"
    assert latest_report_path.name == "latest_qa_full_nightly_report.json"
    assert payload["gate_id"] == "qa_full_nightly"
    assert payload["run_scope"] == "full_profile"


def test_qa_full_detects_hard_failure_and_blocked_prerequisite(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "hard_fail": {
                "severity": "hard",
                "mode": "command",
                "group": "core",
                "report_gate_id": "hard_fail_gate",
                "latest_report_path": str(verification_root / "latest_hard_fail_gate_report.json"),
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_hard_fail_gate_report.json"),
                    "--gate-id",
                    "hard_fail_gate",
                    "--status",
                    "fail",
                ],
            },
            "dependent_hard": {
                "severity": "hard",
                "mode": "command",
                "group": "core",
                "prerequisite_lane_ids": ["hard_fail"],
                "report_gate_id": "dependent_hard_gate",
                "latest_report_path": str(verification_root / "latest_dependent_hard_gate_report.json"),
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_dependent_hard_gate_report.json"),
                    "--gate-id",
                    "dependent_hard_gate",
                    "--status",
                    "pass",
                ],
            },
        },
        lane_order=["hard_fail", "dependent_hard"],
    )

    payload, _, _, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )

    assert payload["status"] == "fail"
    assert [item["lane_id"] for item in payload["hard_failures"]] == ["hard_fail", "dependent_hard"]
    assert [item["lane_id"] for item in payload["root_failures"]] == ["hard_fail"]
    assert [item["lane_id"] for item in payload["cascade_failures"]] == ["dependent_hard"]
    assert payload["blocked_lanes"][0]["lane_id"] == "dependent_hard"
    assert exit_code == 2


def test_qa_full_detects_rerun_flake_and_returns_attention(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    sequence_file = tmp_path / "flake_sequence.txt"
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "flake_lane": {
                "severity": "hard",
                "mode": "command",
                "group": "core",
                "report_gate_id": "flake_gate",
                "latest_report_path": str(verification_root / "latest_flake_gate_report.json"),
                "rerun_count": 2,
                "signature_paths": ["status", "counts", "@package_ids"],
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_flake_gate_report.json"),
                    "--gate-id",
                    "flake_gate",
                    "--sequence-file",
                    str(sequence_file),
                    "--sequence",
                    "pass",
                    "attention",
                ],
            }
        },
        lane_order=["flake_lane"],
    )

    payload, _, _, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )

    assert payload["status"] == "attention"
    assert len(payload["hard_failures"]) == 0
    assert payload["soft_findings"][0]["status"] == "flake_detected"
    assert payload["rerun_comparisons"][0]["comparison_status"] == "flake_detected"
    assert exit_code == 1


def test_qa_full_classifies_missing_workspace_keys_as_environment_failure(tmp_path: Path):
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "workspace_lane": {
                "severity": "hard",
                "lane_class": "environment_or_contract",
                "mode": "command",
                "group": "source_core",
                "workspace_ref": "main",
                "requires_workspace_keys": ["paths.toy_yard_pmx_view_root"],
                "report_gate_id": "workspace_gate",
                "command": ["${python}", "-c", "print('should not run')"],
            }
        },
        lane_order=["workspace_lane"],
    )

    payload, _, _, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )

    assert payload["status"] == "fail"
    assert payload["blocked_lanes"][0]["reason"] == "workspace_keys_missing"
    assert payload["environment_failures"][0]["lane_id"] == "workspace_lane"
    assert payload["hard_failures"][0]["failure_kind"] == "environment_failure"
    assert exit_code == 2


def test_qa_full_written_report_can_be_loaded(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "hard_pass": {
                "severity": "hard",
                "mode": "command",
                "group": "preflight",
                "report_gate_id": "written_gate",
                "latest_report_path": str(verification_root / "latest_written_gate_report.json"),
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_written_gate_report.json"),
                    "--gate-id",
                    "written_gate",
                    "--status",
                    "pass",
                ],
            }
        },
        lane_order=["hard_pass"],
    )

    payload, report_path, latest_report_path, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )
    write_json(report_path, payload)
    write_json(latest_report_path, payload)

    reloaded = load_json(latest_report_path)
    assert reloaded["gate_id"] == "qa_full_nightly"
    assert reloaded["status"] == "pass"
    assert exit_code == 0


def test_qa_full_selected_lanes_use_separate_gate_id(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    profile_path = _profile_path(
        tmp_path,
        lanes={
            "hard_pass": {
                "severity": "hard",
                "mode": "command",
                "group": "preflight",
                "report_gate_id": "hard_pass_gate",
                "latest_report_path": str(verification_root / "latest_hard_pass_gate_report.json"),
                "command": [
                    "${python}",
                    str(fake_lane),
                    "--report",
                    str(verification_root / "latest_hard_pass_gate_report.json"),
                    "--gate-id",
                    "hard_pass_gate",
                    "--status",
                    "pass",
                ],
            }
        },
        lane_order=["hard_pass"],
    )

    payload, report_path, latest_report_path, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
        lane_ids=["hard_pass"],
    )

    assert payload["gate_id"] == "qa_full_nightly_selected"
    assert payload["profile_gate_id"] == "qa_full_nightly"
    assert payload["run_scope"] == "selected_lanes"
    assert payload["selected_lane_ids"] == ["hard_pass"]
    assert report_path.name == "qa_full_nightly_selected_report.json"
    assert latest_report_path.name == "latest_qa_full_nightly_selected_report.json"
    assert exit_code == 0


def test_qa_full_profile_gate_id_is_respected(tmp_path: Path):
    verification_root = tmp_path / "Saved" / "verification"
    verification_root.mkdir(parents=True, exist_ok=True)
    fake_lane = _write_fake_lane_script(tmp_path / "fake_lane.py")
    profile_path = _profile_path_with_payload(
        tmp_path,
        {
            "profile_id": "qa_lite_daily",
            "gate_id": "qa_lite_daily",
            "selected_lanes_gate_id": "qa_lite_selected_lanes",
            "schema_family": "aiue_qa_lite_daily_report",
            "lane_order": ["hard_pass"],
            "lane_registry": {
                "hard_pass": {
                    "severity": "hard",
                    "mode": "command",
                    "group": "preflight",
                    "report_gate_id": "hard_pass_gate",
                    "latest_report_path": str(verification_root / "latest_hard_pass_gate_report.json"),
                    "command": [
                        "${python}",
                        str(fake_lane),
                        "--report",
                        str(verification_root / "latest_hard_pass_gate_report.json"),
                        "--gate-id",
                        "hard_pass_gate",
                        "--status",
                        "pass",
                    ],
                }
            },
        },
    )

    payload, report_path, latest_report_path, exit_code = build_qa_full_report(
        repo_root=tmp_path,
        profile_path=profile_path,
    )

    assert payload["gate_id"] == "qa_lite_daily"
    assert payload["profile_id"] == "qa_lite_daily"
    assert report_path.name == "qa_lite_daily_report.json"
    assert latest_report_path.name == "latest_qa_lite_daily_report.json"
    assert payload["compatibility"]["schema_family"] == "aiue_qa_lite_daily_report"
    assert exit_code == 0
