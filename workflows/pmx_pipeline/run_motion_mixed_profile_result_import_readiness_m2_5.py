from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import (  # noqa: E402
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)
from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402


GATE_ID = "motion_mixed_profile_result_import_readiness_m2_5"
SOURCE_GATE_ID = "motion_fixture_diversity_m2"
MIN_PACKAGE_COUNT = 3
MIN_DISTINCT_SCENARIOS = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check whether the current mixed motion profile is ready for result import and roundtrip handling."
    )
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--source-report")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_source_report_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Source report path does not exist: {candidate}")
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    candidate = repo_root / "Saved" / "verification" / f"latest_{SOURCE_GATE_ID}_report.json"
    if candidate.exists():
        return candidate.resolve()
    raise FileNotFoundError(f"Latest M2 report is missing: {candidate}")


def _existing_file(path_text: str | None) -> bool:
    text = str(path_text or "").strip()
    if not text:
        return False
    return Path(text).expanduser().exists()


def _load_json_if_exists(path_text: str | None) -> dict[str, Any]:
    text = str(path_text or "").strip()
    if not text:
        return {}
    candidate = Path(text).expanduser()
    if not candidate.exists():
        return {}
    return load_json(candidate)


def _collect_profile_snapshot(readiness_report: dict[str, Any], registry_payload: dict[str, Any]) -> dict[str, Any]:
    diversity_snapshot = dict(readiness_report.get("diversity_snapshot") or {})
    return {
        "profile": str(registry_payload.get("profile") or ""),
        "sample_id": str(registry_payload.get("sample_id") or ""),
        "sample_ids": [str(item) for item in list(registry_payload.get("sample_ids") or []) if str(item)],
        "scenario_id": str(registry_payload.get("scenario_id") or ""),
        "scenario_ids": [str(item) for item in list(registry_payload.get("scenario_ids") or []) if str(item)],
        "selection_ready_packages": [str(item) for item in list(diversity_snapshot.get("selection_ready_packages") or []) if str(item)],
    }


def evaluate_package_import_readiness(package_result: dict[str, Any]) -> dict[str, Any]:
    package_id = str(package_result.get("package_id") or "")
    expected_sample_id = str(package_result.get("sample_id") or "")
    expected_scenario_id = str(package_result.get("scenario_id") or "")
    report_path = str(((package_result.get("artifacts") or {}).get("report_path")) or "")
    failed_requirements: list[dict[str, Any]] = []

    if str(package_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_package_not_green",
                f"M2 package result is not green for package {package_id}.",
                package_id=package_id,
                package_status=str(package_result.get("status") or ""),
            )
        )

    if not _existing_file(report_path):
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_package_report_missing",
                f"M2 package report path is missing for package {package_id}.",
                package_id=package_id,
                report_path=report_path,
            )
        )
        return {
            "package_id": package_id,
            "sample_id": expected_sample_id,
            "scenario_id": expected_scenario_id,
            "status": "fail",
            "consumer_result_status": "",
            "owner": "",
            "scope_mismatch_only": bool(package_result.get("scope_mismatch_only")),
            "failed_requirements": failed_requirements,
            "import_ready_artifacts": {
                "package_report_path": report_path,
            },
        }

    report_payload = load_json(report_path)
    consumer_result = dict(report_payload.get("consumer_result") or {})
    packet_ref = dict(consumer_result.get("packet_ref") or {})
    preview_evidence = dict(consumer_result.get("preview_evidence") or {})
    communication_signal = dict(consumer_result.get("communication_signal") or {})
    artifacts = dict(consumer_result.get("artifacts") or {})
    top_level_artifacts = dict(report_payload.get("artifacts") or {})
    manifest_payload = _load_json_if_exists(packet_ref.get("packet_manifest_path"))

    if str(consumer_result.get("schema_version") or "") != "motion_consumer_result_v0":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_consumer_result_schema_invalid",
                f"Consumer result schema version is invalid for package {package_id}.",
                package_id=package_id,
                schema_version=str(consumer_result.get("schema_version") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_consumer_result_not_pass",
                f"Consumer result did not pass for package {package_id}.",
                package_id=package_id,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if str(consumer_result.get("operation") or "") != "animation_preview":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_operation_not_animation_preview",
                f"Operation was not animation_preview for package {package_id}.",
                package_id=package_id,
                operation=str(consumer_result.get("operation") or ""),
            )
        )
    if str(communication_signal.get("owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_owner_not_none",
                f"Owner routing was not none for package {package_id}.",
                package_id=package_id,
                owner=str(communication_signal.get("owner") or ""),
            )
        )
    if bool(communication_signal.get("should_contact_toy_yard")):
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_should_contact_toy_yard_true",
                f"Consumer result still requests toy-yard contact for package {package_id}.",
                package_id=package_id,
            )
        )
    if not bool(preview_evidence.get("subject_visible")):
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_subject_not_visible",
                f"Subject visibility evidence is false for package {package_id}.",
                package_id=package_id,
            )
        )
    if not bool(preview_evidence.get("pose_changed")):
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_pose_not_changed",
                f"Pose change evidence is false for package {package_id}.",
                package_id=package_id,
            )
        )

    actual_package_id = str(packet_ref.get("package_id") or "")
    actual_sample_id = str(packet_ref.get("sample_id") or "")
    actual_scenario_id = str(manifest_payload.get("scenario_id") or "")
    if actual_package_id and actual_package_id != package_id:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_package_id_drift",
                f"Packet package id drifted for package {package_id}.",
                package_id=package_id,
                actual_package_id=actual_package_id,
            )
        )
    if expected_sample_id and actual_sample_id and actual_sample_id != expected_sample_id:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_sample_id_drift",
                f"Packet sample id drifted for package {package_id}.",
                package_id=package_id,
                expected_sample_id=expected_sample_id,
                actual_sample_id=actual_sample_id,
            )
        )
    if expected_scenario_id and actual_scenario_id and actual_scenario_id != expected_scenario_id:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_scenario_id_drift",
                f"Manifest scenario id drifted for package {package_id}.",
                package_id=package_id,
                expected_scenario_id=expected_scenario_id,
                actual_scenario_id=actual_scenario_id,
            )
        )

    required_paths = {
        "packet_manifest_path": str(packet_ref.get("packet_manifest_path") or ""),
        "consumer_result_report_path": report_path,
        "preview_result_json_path": str(preview_evidence.get("result_json_path") or ""),
        "before_image_path": str(preview_evidence.get("before_image_path") or ""),
        "after_image_path": str(preview_evidence.get("after_image_path") or ""),
        "import_action_path": str(artifacts.get("import_action_path") or ""),
        "preview_action_path": str(artifacts.get("preview_action_path") or ""),
        "motion_import_report_path": str(artifacts.get("motion_import_report_path") or ""),
        "motion_preview_report_path": str(artifacts.get("motion_preview_report_path") or ""),
        "motion_consumer_request_path": str(top_level_artifacts.get("motion_consumer_request_path") or ""),
        "motion_consumer_result_path": str(top_level_artifacts.get("motion_consumer_result_path") or ""),
        "motion_consumer_context_path": str(top_level_artifacts.get("motion_consumer_context_path") or ""),
        "motion_consumer_state_path": str(top_level_artifacts.get("motion_consumer_state_path") or ""),
    }
    for artifact_key, artifact_path in required_paths.items():
        if not _existing_file(artifact_path):
            failed_requirements.append(
                make_failed_requirement(
                    f"m2_5_required_artifact_missing_{artifact_key}",
                    f"Required artifact is missing for package {package_id}: {artifact_key}.",
                    package_id=package_id,
                    artifact_key=artifact_key,
                    artifact_path=artifact_path,
                )
            )

    return {
        "package_id": package_id,
        "sample_id": expected_sample_id,
        "scenario_id": expected_scenario_id,
        "status": "pass" if not failed_requirements else "fail",
        "consumer_result_status": str(consumer_result.get("status") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "scope_mismatch_only": bool(package_result.get("scope_mismatch_only")),
        "subject_visible": bool(preview_evidence.get("subject_visible")),
        "pose_changed": bool(preview_evidence.get("pose_changed")),
        "manifest_scenario_id": actual_scenario_id,
        "failed_requirements": failed_requirements,
        "import_ready_artifacts": required_paths,
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    source_report_path = resolve_source_report_path(workspace, args.source_report)
    source_report = load_json(source_report_path)

    failed_requirements: list[dict[str, Any]] = []
    if str(source_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_source_m2_not_pass",
                "M2 source report is not pass.",
                source_report=str(source_report_path),
                source_status=str(source_report.get("status") or ""),
            )
        )

    readiness_report = _load_json_if_exists(source_report.get("source_report"))
    registry_payload = _load_json_if_exists(((readiness_report.get("artifacts") or {}).get("registry_path")))
    profile_snapshot = _collect_profile_snapshot(readiness_report, registry_payload)
    package_results = [
        evaluate_package_import_readiness(item)
        for item in list(source_report.get("package_results") or [])
    ]

    if len(package_results) < MIN_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_package_count_insufficient",
                "Mixed profile did not resolve enough packages for M2.5.",
                package_count=len(package_results),
                required_minimum=MIN_PACKAGE_COUNT,
            )
        )
    if len(profile_snapshot["scenario_ids"]) < MIN_DISTINCT_SCENARIOS:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_distinct_scenarios_insufficient",
                "Mixed profile does not expose enough distinct scenarios for result import readiness.",
                scenario_ids=profile_snapshot["scenario_ids"],
                required_minimum=MIN_DISTINCT_SCENARIOS,
            )
        )
    if len(profile_snapshot["sample_ids"]) < MIN_PACKAGE_COUNT:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_distinct_samples_insufficient",
                "Mixed profile does not expose enough distinct samples for result import readiness.",
                sample_ids=profile_snapshot["sample_ids"],
                required_minimum=MIN_PACKAGE_COUNT,
            )
        )
    if profile_snapshot["sample_id"]:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_mixed_profile_sample_id_not_empty",
                "Mixed profile should not collapse to a single sample_id at the top level.",
                sample_id=profile_snapshot["sample_id"],
            )
        )
    if profile_snapshot["scenario_id"]:
        failed_requirements.append(
            make_failed_requirement(
                "m2_5_mixed_profile_scenario_id_not_empty",
                "Mixed profile should not collapse to a single scenario_id at the top level.",
                scenario_id=profile_snapshot["scenario_id"],
            )
        )

    for item in package_results:
        failed_requirements.extend(list(item.get("failed_requirements") or []))

    counts = {
        "package_count": len(package_results),
        "import_ready_packages": sum(1 for item in package_results if item["status"] == "pass"),
        "package_failures": sum(1 for item in package_results if item["status"] != "pass"),
        "owner_none_packages": sum(1 for item in package_results if item["owner"] == "none"),
        "subject_visible_packages": sum(1 for item in package_results if item["subject_visible"]),
        "pose_changed_packages": sum(1 for item in package_results if item["pose_changed"]),
        "distinct_scenarios": len(profile_snapshot["scenario_ids"]),
        "distinct_samples": len(profile_snapshot["sample_ids"]),
        "scope_mismatch_only_packages": sum(1 for item in package_results if item["scope_mismatch_only"]),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m2_5_motion_mixed_profile_result_import_first_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "source_gate_id": SOURCE_GATE_ID,
            "source_readiness_report": str(source_report.get("source_report") or ""),
            "fixed_execution_profile": {
                "source_mode": "report_only",
                "package_count_required": MIN_PACKAGE_COUNT,
                "distinct_scenarios_required": MIN_DISTINCT_SCENARIOS,
                "mixed_profile_required": True,
                "acceptance_requirements": [
                    "m2_pass_source",
                    "consumer_result_pass_each_package",
                    "owner_none_each_package",
                    "subject_visible_each_package",
                    "pose_changed_each_package",
                    "mixed_profile_arrays_present",
                    "import_ready_artifacts_present",
                ],
            },
            "mixed_profile_snapshot": profile_snapshot,
            "counts": counts,
            "package_results": package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "source_report_path": str(source_report_path),
                "readiness_report_path": str(source_report.get("source_report") or ""),
                "registry_path": str(((readiness_report.get("artifacts") or {}).get("registry_path")) or ""),
            },
        },
        "motion_mixed_profile_result_import_readiness_m2_5_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_mixed_profile_result_import_readiness_m2_5_report",
            notes=["internal_gate_runner", "motion_mixed_profile", "result_import_readiness"],
        ),
    )
    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M2.5 motion mixed-profile result import readiness report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
