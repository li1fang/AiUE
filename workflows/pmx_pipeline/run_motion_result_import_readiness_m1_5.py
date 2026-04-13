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


GATE_ID = "motion_result_import_readiness_m1_5"
SOURCE_GATE_ID = "motion_consumer_baseline_m1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether motion consumer results are ready for toy-yard result import.")
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
    raise FileNotFoundError(f"Latest M1 report is missing: {candidate}")


def _existing_file(path_text: str | None) -> bool:
    text = str(path_text or "").strip()
    if not text:
        return False
    return Path(text).expanduser().exists()


def _non_empty_string(path: list[str], payload: dict[str, Any], failed_requirements: list[dict[str, Any]], requirement_id: str, message: str, **details) -> str:
    cursor: Any = payload
    for segment in path:
        cursor = cursor.get(segment) if isinstance(cursor, dict) else None
    text = str(cursor or "").strip()
    if not text:
        failed_requirements.append(make_failed_requirement(requirement_id, message, **details))
    return text


def evaluate_iteration_readiness(iteration_payload: dict[str, Any], expected_package_id: str, expected_sample_id: str) -> dict[str, Any]:
    failed_requirements: list[dict[str, Any]] = []
    iteration_index = int(iteration_payload.get("iteration_index") or 0)
    report_path = str(((iteration_payload.get("artifacts") or {}).get("report_path")) or "")
    if not _existing_file(report_path):
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_iteration_report_missing",
                f"Iteration {iteration_index} report path is missing.",
                iteration_index=iteration_index,
                report_path=report_path,
            )
        )
    report_payload = load_json(report_path) if _existing_file(report_path) else {}
    consumer_result = dict(report_payload.get("consumer_result") or {})
    packet_ref = dict(consumer_result.get("packet_ref") or {})
    communication_signal = dict(consumer_result.get("communication_signal") or {})
    preview_evidence = dict(consumer_result.get("preview_evidence") or {})
    artifacts = dict(consumer_result.get("artifacts") or {})
    generated_assets = dict(consumer_result.get("generated_assets") or {})

    status = "pass"
    if str(consumer_result.get("schema_version") or "") != "motion_consumer_result_v0":
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_result_schema_version_invalid",
                f"Iteration {iteration_index} consumer result schema version is invalid.",
                iteration_index=iteration_index,
                schema_version=str(consumer_result.get("schema_version") or ""),
            )
        )
    if str(consumer_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_consumer_result_not_pass",
                f"Iteration {iteration_index} consumer result did not pass.",
                iteration_index=iteration_index,
                consumer_result_status=str(consumer_result.get("status") or ""),
            )
        )
    if str(consumer_result.get("operation") or "") != "animation_preview":
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_operation_not_animation_preview",
                f"Iteration {iteration_index} operation was not animation_preview.",
                iteration_index=iteration_index,
                operation=str(consumer_result.get("operation") or ""),
            )
        )

    manifest_path = _non_empty_string(
        ["packet_ref", "packet_manifest_path"],
        consumer_result,
        failed_requirements,
        "m1_5_packet_manifest_missing",
        f"Iteration {iteration_index} packet manifest path is missing.",
        iteration_index=iteration_index,
    )
    package_id = _non_empty_string(
        ["packet_ref", "package_id"],
        consumer_result,
        failed_requirements,
        "m1_5_packet_package_id_missing",
        f"Iteration {iteration_index} package id is missing.",
        iteration_index=iteration_index,
    )
    sample_id = _non_empty_string(
        ["packet_ref", "sample_id"],
        consumer_result,
        failed_requirements,
        "m1_5_packet_sample_id_missing",
        f"Iteration {iteration_index} sample id is missing.",
        iteration_index=iteration_index,
    )
    if package_id and package_id != expected_package_id:
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_package_id_drift",
                f"Iteration {iteration_index} package id drifted from the M1 target package.",
                iteration_index=iteration_index,
                expected_package_id=expected_package_id,
                actual_package_id=package_id,
            )
        )
    if sample_id and sample_id != expected_sample_id:
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_sample_id_drift",
                f"Iteration {iteration_index} sample id drifted from the M1 expected sample.",
                iteration_index=iteration_index,
                expected_sample_id=expected_sample_id,
                actual_sample_id=sample_id,
            )
        )
    if manifest_path and not _existing_file(manifest_path):
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_packet_manifest_not_found",
                f"Iteration {iteration_index} packet manifest path does not exist.",
                iteration_index=iteration_index,
                packet_manifest_path=manifest_path,
            )
        )

    if str(communication_signal.get("owner") or "") != "none":
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_owner_not_none",
                f"Iteration {iteration_index} consumer result owner is not none.",
                iteration_index=iteration_index,
                owner=str(communication_signal.get("owner") or ""),
            )
        )
    if bool(communication_signal.get("should_contact_toy_yard")):
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_should_contact_toy_yard_true",
                f"Iteration {iteration_index} still requests toy-yard contact.",
                iteration_index=iteration_index,
            )
        )

    generated_animation_asset = _non_empty_string(
        ["generated_assets", "animation_asset_path"],
        consumer_result,
        failed_requirements,
        "m1_5_generated_animation_asset_missing",
        f"Iteration {iteration_index} generated animation asset path is missing.",
        iteration_index=iteration_index,
    )
    _non_empty_string(
        ["generated_assets", "retargeted_animation_asset_path"],
        consumer_result,
        failed_requirements,
        "m1_5_retargeted_animation_asset_missing",
        f"Iteration {iteration_index} retargeted animation asset path is missing.",
        iteration_index=iteration_index,
    )
    _non_empty_string(
        ["preview_evidence", "result_json_path"],
        consumer_result,
        failed_requirements,
        "m1_5_preview_result_json_missing",
        f"Iteration {iteration_index} preview result json path is missing.",
        iteration_index=iteration_index,
    )

    for artifact_key in (
        "result_json_path",
        "before_image_path",
        "after_image_path",
    ):
        artifact_path = str(preview_evidence.get(artifact_key) or "")
        if not _existing_file(artifact_path):
            failed_requirements.append(
                make_failed_requirement(
                    f"m1_5_preview_artifact_missing_{artifact_key}",
                    f"Iteration {iteration_index} preview artifact is missing: {artifact_key}.",
                    iteration_index=iteration_index,
                    artifact_key=artifact_key,
                    artifact_path=artifact_path,
                )
            )

    for artifact_key in (
        "import_action_path",
        "preview_action_path",
        "motion_import_report_path",
        "motion_preview_report_path",
    ):
        artifact_path = str(artifacts.get(artifact_key) or "")
        if not _existing_file(artifact_path):
            failed_requirements.append(
                make_failed_requirement(
                    f"m1_5_artifact_missing_{artifact_key}",
                    f"Iteration {iteration_index} required motion artifact is missing: {artifact_key}.",
                    iteration_index=iteration_index,
                    artifact_key=artifact_key,
                    artifact_path=artifact_path,
                )
            )

    if not bool(preview_evidence.get("subject_visible")):
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_subject_not_visible",
                f"Iteration {iteration_index} subject visibility evidence is false.",
                iteration_index=iteration_index,
            )
        )
    if not bool(preview_evidence.get("pose_changed")):
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_pose_not_changed",
                f"Iteration {iteration_index} pose change evidence is false.",
                iteration_index=iteration_index,
            )
        )

    if failed_requirements:
        status = "fail"

    return {
        "iteration_index": iteration_index,
        "status": status,
        "package_id": package_id,
        "sample_id": sample_id,
        "animation_asset_path": generated_animation_asset,
        "import_mode": str(generated_assets.get("import_mode") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "artifact_presence": {
            "packet_manifest": _existing_file(manifest_path),
            "preview_result_json": _existing_file(str(preview_evidence.get("result_json_path") or "")),
            "before_image": _existing_file(str(preview_evidence.get("before_image_path") or "")),
            "after_image": _existing_file(str(preview_evidence.get("after_image_path") or "")),
            "import_action": _existing_file(str(artifacts.get("import_action_path") or "")),
            "preview_action": _existing_file(str(artifacts.get("preview_action_path") or "")),
            "motion_import_report": _existing_file(str(artifacts.get("motion_import_report_path") or "")),
            "motion_preview_report": _existing_file(str(artifacts.get("motion_preview_report_path") or "")),
        },
        "import_ready_artifacts": {
            "packet_manifest_path": manifest_path,
            "consumer_result_report_path": report_path,
            "preview_result_json_path": str(preview_evidence.get("result_json_path") or ""),
            "import_action_path": str(artifacts.get("import_action_path") or ""),
            "preview_action_path": str(artifacts.get("preview_action_path") or ""),
            "motion_import_report_path": str(artifacts.get("motion_import_report_path") or ""),
            "motion_preview_report_path": str(artifacts.get("motion_preview_report_path") or ""),
            "before_image_path": str(preview_evidence.get("before_image_path") or ""),
            "after_image_path": str(preview_evidence.get("after_image_path") or ""),
        },
        "failed_requirements": failed_requirements,
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

    expected_package_id = str(source_report.get("target_package_id") or "")
    expected_sample_id = str(source_report.get("expected_sample_id") or "")
    iteration_payloads = list(source_report.get("iteration_results") or [])
    iteration_results = [
        evaluate_iteration_readiness(item, expected_package_id, expected_sample_id)
        for item in iteration_payloads
    ]
    failed_requirements = [
        requirement
        for item in iteration_results
        for requirement in list(item.get("failed_requirements") or [])
    ]
    if str(source_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_source_m1_not_pass",
                "Source M1 report is not pass.",
                source_report_path=str(source_report_path),
                source_status=str(source_report.get("status") or ""),
            )
        )
    if not iteration_results:
        failed_requirements.append(
            make_failed_requirement(
                "m1_5_iteration_results_missing",
                "Source M1 report does not contain iteration results.",
                source_report_path=str(source_report_path),
            )
        )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        latest_report_path if latest_report_path.exists() else None,
        "m1_5_motion_result_import_readiness_first_pass",
    )
    counts = {
        "iteration_count": len(iteration_results),
        "iteration_passes": sum(1 for item in iteration_results if item["status"] == "pass"),
        "import_ready_iterations": sum(1 for item in iteration_results if item["status"] == "pass"),
        "failed_iterations": sum(1 for item in iteration_results if item["status"] != "pass"),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_report": str(source_report_path),
            "source_gate_id": SOURCE_GATE_ID,
            "expected_package_id": expected_package_id,
            "expected_sample_id": expected_sample_id,
            "fixed_execution_profile": {
                "source_mode": "latest_m1_report",
                "readiness_focus": "toy_yard_result_import",
                "required_consumer_result_schema": "motion_consumer_result_v0",
                "required_operation": "animation_preview",
            },
            "counts": counts,
            "iteration_results": iteration_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "source_report_path": str(source_report_path),
                "iteration_consumer_result_paths": [item["import_ready_artifacts"]["consumer_result_report_path"] for item in iteration_results],
            },
        },
        "motion_result_import_readiness_m1_5_report",
        workflow_pack="pmx_pipeline",
        tool_name="AiUE",
        compatibility=make_compatibility_block(
            schema_family="motion_result_import_readiness_m1_5_report",
            notes=["internal_gate_runner", "motion_result_import_readiness", "toy_yard_result_import"],
        ),
    )

    report_path = output_root / f"{GATE_ID}_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"M1.5 motion result import readiness report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
