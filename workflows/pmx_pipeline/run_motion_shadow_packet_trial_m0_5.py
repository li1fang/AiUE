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
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402
from aiue_unreal.action_runner import run_action  # noqa: E402
from toy_yard_view import (  # noqa: E402
    build_toy_yard_motion_manifest_index,
    resolve_toy_yard_motion_communication_signal_path,
    resolve_toy_yard_motion_packet_check_path,
    resolve_toy_yard_motion_registry_path,
    resolve_toy_yard_motion_summary_path,
    resolve_toy_yard_motion_view_root,
)


GATE_ID = "motion_shadow_packet_trial_m0_5"
PREFERRED_PACKAGE_ID = "pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7"
EXPECTED_SAMPLE_ID = "sample_route-a-3s-turn-hand-ready_797943f40a"
FIXED_EXECUTION_PROFILE = {
    "source_mode": "toy_yard_motion_shadow_packet",
    "mode": "cmd_nullrhi",
    "lane": "motion",
    "default_source_required": True,
    "raw_motion_discovery_allowed": False,
    "toy_yard_sqlite_required": False,
    "communication_signal_enabled": True,
    "trial_node": "m0_5_motion_shadow_packet_trial",
}

SEAM_BLOCKING_FAILURE_IDS = {
    "m0_5_view_root_missing",
    "m0_5_summary_path_missing",
    "m0_5_registry_path_missing",
    "m0_5_packet_check_missing",
    "m0_5_packet_handoff_not_ready",
    "m0_5_candidate_missing",
    "m0_5_candidate_scope_mismatch",
    "m0_5_consumer_request_missing",
    "m0_5_consumer_result_missing",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE M0.5 motion shadow packet trial.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--summary-path")
    parser.add_argument("--registry-path")
    parser.add_argument("--packet-check-path")
    parser.add_argument("--output-root")
    parser.add_argument("--state-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--target-package-id")
    return parser.parse_args()


def resolve_motion_summary_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Summary path does not exist: {candidate}")
    candidate = resolve_toy_yard_motion_summary_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard motion suite summary could be resolved from workspace paths.toy_yard_motion_view_root.")


def resolve_motion_registry_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Registry path does not exist: {candidate}")
    candidate = resolve_toy_yard_motion_registry_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard motion clip registry could be resolved from workspace paths.toy_yard_motion_view_root.")


def resolve_motion_packet_check_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Packet check path does not exist: {candidate}")
    candidate = resolve_toy_yard_motion_packet_check_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard motion packet check could be resolved from workspace paths.toy_yard_motion_view_root.")


def select_motion_clip(
    registry_payload: dict[str, Any],
    manifest_index: dict[str, Path],
    target_package_id: str | None = None,
) -> dict[str, Any] | None:
    candidates = []
    for entry in list(registry_payload.get("clips") or []):
        package_id = str(entry.get("package_id") or "").strip()
        if not package_id or package_id not in manifest_index:
            continue
        if target_package_id and package_id != target_package_id:
            continue
        if not bool(entry.get("selection_ready")):
            continue
        candidate = dict(entry)
        candidate["manifest_path"] = str(manifest_index[package_id])
        candidates.append(candidate)
    if not candidates:
        return None
    if target_package_id:
        return candidates[0]
    for candidate in candidates:
        if str(candidate.get("package_id") or "") == PREFERRED_PACKAGE_ID:
            return candidate
    candidates.sort(key=lambda item: str(item.get("package_id") or ""))
    return candidates[0]


def run_workflow_action(workspace: dict, command: str, params: dict[str, Any], output_path: Path, *, mode: str | None = None) -> tuple[dict[str, Any], str]:
    payload, resolved_output_path = run_action(
        {
            "command": command,
            "mode": mode or str(FIXED_EXECUTION_PROFILE["mode"]),
            "params": params,
            "output_path": str(output_path.resolve()),
        },
        workspace,
    )
    return payload, resolved_output_path


def evaluate_action_payload(action_payload: dict[str, Any]) -> tuple[bool, list[str], dict[str, Any]]:
    status = str(action_payload.get("status") or "")
    success = bool(action_payload.get("success")) and status == "pass"
    warnings = [str(item) for item in list(action_payload.get("warnings") or []) if str(item)]
    result = dict(action_payload.get("result") or {})
    return success, warnings, result


def first_preview_images(preview_result: dict[str, Any]) -> tuple[str, str]:
    for shot in list(preview_result.get("shots") or []):
        before_path = str(((shot.get("before") or {}).get("image_path")) or "")
        after_path = str(((shot.get("after") or {}).get("image_path")) or "")
        if before_path or after_path:
            return before_path, after_path
    return "", ""


def build_retarget_preview_params(import_result: dict[str, Any], bootstrap_result: dict[str, Any]) -> dict[str, Any]:
    imported_assets = dict(import_result.get("imported_assets") or {})
    target_selection = dict(bootstrap_result.get("target_ik_rig_selection") or {})
    return {
        "retarget_source_ik_rig_asset_path": str(bootstrap_result.get("target_ik_rig_asset_path") or ""),
        "retarget_target_ik_rig_asset_path": str(bootstrap_result.get("source_ik_rig_asset_path") or ""),
        "retarget_source_mesh_asset_path": str(
            imported_assets.get("skeletal_mesh_asset_path")
            or target_selection.get("skeletal_mesh_asset_path")
            or ""
        ),
        "retarget_target_mesh_asset_path": str(bootstrap_result.get("source_mesh_asset_path") or ""),
        "retargeter_asset_path": str(bootstrap_result.get("retargeter_asset_path") or ""),
    }


def should_run_retarget_author_chains(bootstrap_result: dict[str, Any]) -> bool:
    return int(bootstrap_result.get("mapped_chain_count") or 0) == 0 or int(
        (bootstrap_result.get("source_ik_rig_profile") or {}).get("chain_count") or 0
    ) == 0


def normalize_motion_execution_warnings(
    import_payload: dict[str, Any],
    bootstrap_payload: dict[str, Any] | None,
    author_chains_payload: dict[str, Any] | None,
    preview_payload: dict[str, Any],
) -> list[str]:
    _, _, import_result = evaluate_action_payload(import_payload or {})
    _, _, bootstrap_result = evaluate_action_payload(bootstrap_payload or {})
    _, _, author_chains_result = evaluate_action_payload(author_chains_payload or {})
    _, _, preview_result = evaluate_action_payload(preview_payload or {})
    import_mode = str(((import_result.get("imported_assets") or {}).get("import_mode")) or "")
    native_pose = dict(preview_result.get("native_animation_pose_evaluation") or {})

    merged = [
        *[str(item) for item in list((import_payload or {}).get("warnings") or [])],
        *[str(item) for item in list((bootstrap_payload or {}).get("warnings") or [])],
        *[str(item) for item in list((author_chains_payload or {}).get("warnings") or [])],
        *[str(item) for item in list((preview_payload or {}).get("warnings") or [])],
        *[str(item) for item in list(import_result.get("warnings") or [])],
        *[str(item) for item in list(bootstrap_result.get("warnings") or [])],
        *[str(item) for item in list(author_chains_result.get("warnings") or [])],
        *[str(item) for item in list(preview_result.get("warnings") or [])],
    ]

    author_chains_ready = bool(author_chains_result.get("ready_for_animation_retry"))
    filtered: list[str] = []
    for warning in merged:
        warning_text = str(warning or "")
        if not warning_text:
            continue
        if author_chains_ready and warning_text in {
            "source_ik_rig_has_no_retarget_chains",
            "retargeter_has_no_mapped_target_chains",
        }:
            continue
        if warning_text == "interchange_fbx_import_disabled_for_motion_import":
            continue
        if warning_text.startswith("explicit_target_skeleton_resolved_by_folder_scan:"):
            continue
        if import_mode == "source_bundle_fallback" and warning_text in {
            "import_completed_without_animsequence_object_path",
            "target_skeleton_import_failed_falling_back_to_source_bundle",
        }:
            continue
        if warning_text == "animation_blueprint_library_unavailable" and bool(native_pose.get("success")):
            continue
        filtered.append(warning_text)
    return sorted(set(filtered))


def clip_matches_trial_scope(clip: dict[str, Any]) -> bool:
    return (
        str(clip.get("sample_id") or "") == EXPECTED_SAMPLE_ID
        and str(clip.get("format_profile") or "") == "route_a_kimodo_somaskel77"
        and str(clip.get("runtime_semantics") or "") == "runtime"
        and str(clip.get("skeleton_id") or "") == "somaskel77"
        and not bool(clip.get("placeholder_motion"))
    )


def build_motion_consumer_request(
    workspace: dict,
    summary_path: Path | None,
    registry_path: Path | None,
    packet_check_path: Path | None,
    packet_signal_path: Path | None,
    selected_clip: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not selected_clip:
        return None
    paths = workspace.get("paths") or {}
    motion = workspace.get("motion") or {}
    return {
        "schema_version": "motion_consumer_request_v0",
        "operation": "animation_preview",
        "packet_manifest_path": str(Path(str(selected_clip["manifest_path"])).expanduser().resolve()),
        "summary_path": str(summary_path.resolve()) if summary_path else "",
        "registry_path": str(registry_path.resolve()) if registry_path else "",
        "packet_check_path": str(packet_check_path.resolve()) if packet_check_path else "",
        "producer_signal_path": str(packet_signal_path.resolve()) if packet_signal_path and packet_signal_path.exists() else "",
        "host_key": "demo",
        "target_package_id": str(selected_clip.get("package_id") or ""),
        "target_host_blueprint_asset_path": str(
            motion.get("preview_host_blueprint_asset_path")
            or paths.get("motion_preview_host_blueprint_asset_path")
            or ""
        ),
        "target_skeleton_asset_path": str(paths.get("motion_target_skeleton_asset_path") or ""),
        "motion_asset_root": str(paths.get("motion_asset_root") or "/Game/AiUE/MotionPackets"),
        "asset_root": str(paths.get("asset_root") or "/Game/AiUE/ImportedAssets"),
        "preview_level_path": str(motion.get("preview_level_path") or ""),
        "runtime_ready_only": bool(motion.get("runtime_ready_only", True)),
        "retarget_if_needed": True,
        "consumer_context": {
            "counterparty_system": "toy-yard",
            "source_lane": "motion",
            "default_source_required": True,
            "raw_motion_discovery_allowed": False,
            "toy_yard_sqlite_required": False,
        },
    }


def classify_motion_failure_class(
    packet_signal_payload: dict[str, Any],
    seam_blockers: list[dict[str, Any]],
    import_payload: dict[str, Any],
    preview_payload: dict[str, Any],
) -> str | None:
    blocker_ids = {str(item.get("id") or "") for item in seam_blockers}
    if not bool(packet_signal_payload.get("handoff_ready")) or blocker_ids & {
        "m0_5_view_root_missing",
        "m0_5_summary_path_missing",
        "m0_5_registry_path_missing",
        "m0_5_packet_check_missing",
        "m0_5_candidate_missing",
    }:
        return "producer_contract_issue"

    import_success, _, import_result = evaluate_action_payload(import_payload) if import_payload else (False, [], {})
    preview_success, _, preview_result = evaluate_action_payload(preview_payload) if preview_payload else (False, [], {})
    import_errors = [str(item) for item in list(import_payload.get("errors") or [])] + [str(item) for item in list(import_result.get("errors") or [])]
    preview_errors = [str(item) for item in list(preview_payload.get("errors") or [])] + [str(item) for item in list(preview_result.get("errors") or [])]
    all_errors = import_errors + preview_errors

    if any("motion_import_source_missing" in error or "motion_bvh_missing" in error for error in all_errors):
        return "packet_artifact_missing"
    if any("unsupported_format_profile" in error or "unsupported_runtime_semantics" in error or "unsupported_skeleton_id" in error or "motion_validation_not_pass" in error for error in all_errors):
        return "producer_contract_issue"
    if any("motion_bvh_conversion" in error for error in all_errors):
        return "conversion_failed"
    if any("target_skeleton" in error for error in all_errors):
        return "target_resolution_failed"
    if import_payload and not import_success:
        return "unreal_import_failed"
    preview_failed_requirements = {str(item) for item in list(preview_result.get("failed_requirements") or [])}
    if preview_errors and ("animation_skeleton_incompatible" in preview_failed_requirements or "retarget_generate_failed" in preview_failed_requirements):
        return "retarget_failed"
    if preview_payload and not preview_success:
        if "capture_failed" in preview_failed_requirements or "subject_not_reliably_visible" in preview_failed_requirements:
            return "preview_failed"
        return "runtime_validation_failed"
    return None


def build_motion_communication_signal(
    packet_signal_payload: dict[str, Any],
    seam_blockers: list[dict[str, Any]],
    failure_class: str | None,
    consumer_result_status: str,
) -> dict[str, Any]:
    if not bool(packet_signal_payload.get("handoff_ready")):
        return {
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": "motion_packet_contract_or_selection_issue",
            "recommended_node": "toy_yard_motion_packet_followup",
        }
    blocker_ids = {str(item.get("id") or "") for item in seam_blockers}
    if blocker_ids & {
        "m0_5_view_root_missing",
        "m0_5_summary_path_missing",
        "m0_5_registry_path_missing",
        "m0_5_packet_check_missing",
        "m0_5_candidate_missing",
    }:
        return {
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": "motion_default_source_resolution_issue",
            "recommended_node": "toy_yard_motion_default_source_followup",
        }
    if failure_class in {"producer_contract_issue", "packet_artifact_missing"}:
        return {
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": str(failure_class),
            "recommended_node": "toy_yard_motion_contract_followup",
        }
    if consumer_result_status == "pass":
        return {
            "should_contact_toy_yard": False,
            "owner": "none",
            "reason": "motion_consumed_and_previewed",
            "recommended_node": None,
        }
    return {
        "should_contact_toy_yard": False,
        "owner": "aiue",
        "reason": str(failure_class or "aiue_motion_consumer_or_preview_issue"),
        "recommended_node": "aiue_motion_runtime_followup",
    }


def build_motion_consumer_result(
    request_payload: dict[str, Any] | None,
    selected_clip: dict[str, Any] | None,
    import_payload: dict[str, Any],
    import_action_path: str,
    preview_payload: dict[str, Any],
    preview_action_path: str,
    failure_class: str | None,
    communication_signal: dict[str, Any],
    bootstrap_payload: dict[str, Any] | None = None,
    bootstrap_action_path: str = "",
    author_chains_payload: dict[str, Any] | None = None,
    author_chains_action_path: str = "",
) -> dict[str, Any] | None:
    if not request_payload or not selected_clip:
        return None

    manifest_dir = Path(str(request_payload.get("packet_manifest_path") or "")).expanduser().resolve().parent
    import_success, _, import_result = evaluate_action_payload(import_payload) if import_payload else (False, [], {})
    preview_success, _, preview_result = evaluate_action_payload(preview_payload) if preview_payload else (False, [], {})
    _, _, bootstrap_result = evaluate_action_payload(bootstrap_payload or {})
    _, _, author_chains_result = evaluate_action_payload(author_chains_payload or {})
    operation = "animation_preview" if preview_payload else "import_motion_packet"
    result_status = "pass" if preview_payload and preview_success else "pass" if (not preview_payload and import_success) else "fail"
    animation_asset_path = str(
        import_result.get("imported_animation_asset_path")
        or ((import_result.get("imported_assets") or {}).get("animation_asset_path") or "")
    )
    before_image_path, after_image_path = first_preview_images(preview_result)
    pose_probe_delta = dict(preview_result.get("pose_probe_delta") or {})
    native_pose = dict(preview_result.get("native_animation_pose_evaluation") or {})
    imported_assets = dict(import_result.get("imported_assets") or {})
    target_host_asset_path = str(
        import_result.get("target_host_asset_path")
        or ((import_result.get("retarget_refs") or {}).get("target_host_asset_path") or "")
    )
    target_skeleton_asset_path = str(
        import_result.get("target_skeleton_asset_path")
        or ((import_result.get("retarget_refs") or {}).get("target_skeleton_asset_path") or "")
        or request_payload.get("target_skeleton_asset_path")
        or ""
    )
    return {
        "schema_version": "motion_consumer_result_v0",
        "status": result_status,
        "operation": operation,
        "packet_ref": {
            "packet_manifest_path": str(request_payload.get("packet_manifest_path") or ""),
            "package_id": str(selected_clip.get("package_id") or ""),
            "sample_id": str(selected_clip.get("sample_id") or ""),
            "clip_id": str(selected_clip.get("clip_id") or ""),
            "pack_version": str(selected_clip.get("pack_version") or ""),
        },
        "generated_assets": {
            "animation_asset_path": animation_asset_path,
            "import_mode": str(imported_assets.get("import_mode") or ""),
            "ik_rig_asset_path": str(
                author_chains_result.get("source_ik_rig_asset_path")
                or bootstrap_result.get("target_ik_rig_asset_path")
                or bootstrap_result.get("source_ik_rig_asset_path")
                or ""
            ),
            "retargeter_asset_path": str(
                author_chains_result.get("retargeter_asset_path") or bootstrap_result.get("retargeter_asset_path") or ""
            ),
            "retargeted_animation_asset_path": str(preview_result.get("resolved_animation_asset_path") or ""),
        },
        "host_resolution": {
            "host_key": str(request_payload.get("host_key") or "demo"),
            "target_host_asset_path": target_host_asset_path,
            "target_skeleton_asset_path": target_skeleton_asset_path,
        },
        "preview_evidence": {
            "result_json_path": str(preview_action_path or ""),
            "before_image_path": before_image_path,
            "after_image_path": after_image_path,
            "subject_visible": bool(
                native_pose.get("pose_changed")
                or pose_probe_delta.get("moving_bone_count")
                or any(
                    bool(((shot.get("before") or {}).get("subject_visible")))
                    or bool(((shot.get("after") or {}).get("subject_visible")))
                    for shot in list(preview_result.get("shots") or [])
                )
            ),
            "pose_changed": bool(native_pose.get("pose_changed")),
            "probe_delta": pose_probe_delta,
        },
        "failure_class": failure_class,
        "communication_signal": communication_signal,
        "warnings": normalize_motion_execution_warnings(
            import_payload,
            bootstrap_payload,
            author_chains_payload,
            preview_payload,
        ),
        "errors": sorted(
            set(
                [str(item) for item in list(import_payload.get("errors") or [])]
                + [str(item) for item in list((bootstrap_payload or {}).get("errors") or [])]
                + [str(item) for item in list((author_chains_payload or {}).get("errors") or [])]
                + [str(item) for item in list(preview_payload.get("errors") or [])]
                + [str(item) for item in list(import_result.get("errors") or [])]
                + [str(item) for item in list(bootstrap_result.get("errors") or [])]
                + [str(item) for item in list(author_chains_result.get("errors") or [])]
                + [str(item) for item in list(preview_result.get("errors") or [])]
            )
        ),
        "artifacts": {
            "import_action_path": str(import_action_path or ""),
            "bootstrap_action_path": str(bootstrap_action_path or ""),
            "author_chains_action_path": str(author_chains_action_path or ""),
            "preview_action_path": str(preview_action_path or ""),
            "motion_import_report_path": str((manifest_dir / "motion_import_report.local.json").resolve()),
            "motion_preview_report_path": str((manifest_dir / "motion_preview_report.local.json").resolve()),
        },
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    if args.state_root:
        state_root = Path(args.state_root).expanduser().resolve()
    elif args.output_root:
        state_root = output_root
    else:
        state_root = repo_root / "Saved" / "demo" / "m0_5" / "latest"
    state_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    seam_blockers: list[dict[str, Any]] = []
    motion_view_root = resolve_toy_yard_motion_view_root(workspace)
    if motion_view_root is None:
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_view_root_missing",
                "M0.5 requires paths.toy_yard_motion_view_root to resolve to a valid toy-yard motion packet root.",
            )
        )

    try:
        summary_path = resolve_motion_summary_path(workspace, args.summary_path)
    except FileNotFoundError as exc:
        summary_path = None
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_summary_path_missing",
                "M0.5 requires a resolvable toy-yard motion suite summary path.",
                error=str(exc),
            )
        )
    try:
        registry_path = resolve_motion_registry_path(workspace, args.registry_path)
    except FileNotFoundError as exc:
        registry_path = None
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_registry_path_missing",
                "M0.5 requires a resolvable toy-yard motion clip registry path.",
                error=str(exc),
            )
        )
    try:
        packet_check_path = resolve_motion_packet_check_path(workspace, args.packet_check_path)
    except FileNotFoundError as exc:
        packet_check_path = None
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_packet_check_missing",
                "M0.5 requires a resolvable toy-yard motion packet check path.",
                error=str(exc),
            )
        )

    summary_payload = load_json(summary_path) if summary_path and summary_path.exists() else {}
    registry_payload = load_json(registry_path) if registry_path and registry_path.exists() else {}
    packet_check_payload = load_json(packet_check_path) if packet_check_path and packet_check_path.exists() else {}
    packet_signal_path = resolve_toy_yard_motion_communication_signal_path(workspace)
    packet_signal_payload = load_json(packet_signal_path) if packet_signal_path and packet_signal_path.exists() else {}

    if not bool(packet_signal_payload.get("handoff_ready")):
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_packet_handoff_not_ready",
                "M0.5 requires the toy-yard producer signal to declare handoff_ready=true before AiUE consumes the packet.",
                packet_signal_path=str(packet_signal_path.resolve()) if packet_signal_path and packet_signal_path.exists() else "",
            )
        )

    if summary_path and summary_path.exists():
        clips_root, manifest_index = build_toy_yard_motion_manifest_index(summary_path)
    else:
        clips_root, manifest_index = None, {}

    selected_clip = select_motion_clip(registry_payload, manifest_index, args.target_package_id) if manifest_index else None
    if not selected_clip:
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_candidate_missing",
                "M0.5 requires at least one selection-ready motion clip resolvable from the toy-yard motion packet.",
                registry_path=str(registry_path.resolve()) if registry_path else None,
            )
        )
    elif not clip_matches_trial_scope(selected_clip):
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_candidate_scope_mismatch",
                "M0.5 is locked to the current controlled motion fixture scope and the selected clip did not match it.",
                package_id=str(selected_clip.get("package_id") or ""),
                sample_id=str(selected_clip.get("sample_id") or ""),
            )
        )

    consumer_request = build_motion_consumer_request(
        workspace,
        summary_path,
        registry_path,
        packet_check_path,
        packet_signal_path,
        selected_clip,
    )
    if not consumer_request:
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_consumer_request_missing",
                "M0.5 requires a motion_consumer_request_v0 payload to be materialized before execution.",
            )
        )

    consumer_request_path = output_root / "motion_consumer_request_v0.json"
    if consumer_request:
        write_json(consumer_request_path, consumer_request)

    import_payload: dict[str, Any] = {}
    import_action_path = ""
    bootstrap_payload: dict[str, Any] = {}
    bootstrap_action_path = ""
    author_chains_payload: dict[str, Any] = {}
    author_chains_action_path = ""
    preview_payload: dict[str, Any] = {}
    preview_action_path = ""
    if consumer_request:
        manifest_path = Path(str(consumer_request["packet_manifest_path"])).expanduser().resolve()
        import_payload, import_action_path = run_workflow_action(
            workspace,
            "import-motion-packet",
            {
                "manifest": str(manifest_path),
                "motion_asset_root": str(consumer_request.get("motion_asset_root") or ""),
                "asset_root": str(consumer_request.get("asset_root") or ""),
                "target_skeleton_asset_path": str(consumer_request.get("target_skeleton_asset_path") or ""),
                "host_blueprint_asset_path": str(consumer_request.get("target_host_blueprint_asset_path") or ""),
                "sample_id": str(selected_clip.get("sample_id") or ""),
                "package_id": str(selected_clip.get("package_id") or ""),
                "runtime_ready_only": bool(consumer_request.get("runtime_ready_only", True)),
            },
            output_root / "motion" / "import_motion_packet.action.json",
        )
        write_json(manifest_path.parent / "motion_import_report.local.json", import_payload)
        import_success, _, import_result = evaluate_action_payload(import_payload)
        imported_animation_asset_path = str(
            import_result.get("imported_animation_asset_path")
            or ((import_result.get("imported_assets") or {}).get("animation_asset_path") or "")
        )
        if import_success and imported_animation_asset_path:
            bootstrap_payload, bootstrap_action_path = run_workflow_action(
                workspace,
                "retarget-bootstrap",
                {
                    "animation_asset_path": imported_animation_asset_path,
                    "host_blueprint_asset_path": str(consumer_request.get("target_host_blueprint_asset_path") or ""),
                    "sample_id": str(selected_clip.get("sample_id") or ""),
                    "package_id": str(selected_clip.get("package_id") or ""),
                    "runtime_ready_only": bool(consumer_request.get("runtime_ready_only", True)),
                    "asset_root": str(consumer_request.get("asset_root") or ""),
                },
                output_root / "motion" / "retarget_bootstrap.action.json",
            )
            bootstrap_success, _, bootstrap_result = evaluate_action_payload(bootstrap_payload)
            if bootstrap_success and should_run_retarget_author_chains(bootstrap_result):
                author_chains_payload, author_chains_action_path = run_workflow_action(
                    workspace,
                    "retarget-author-chains",
                    {
                        "source_ik_rig_asset_path": str(bootstrap_result.get("source_ik_rig_asset_path") or ""),
                        "target_ik_rig_asset_path": str(bootstrap_result.get("target_ik_rig_asset_path") or ""),
                        "retargeter_asset_path": str(bootstrap_result.get("retargeter_asset_path") or ""),
                    },
                    output_root / "motion" / "retarget_author_chains.action.json",
                )
            preview_payload, preview_action_path = run_workflow_action(
                workspace,
                "animation-preview",
                {
                    "animation_asset_path": imported_animation_asset_path,
                    "level_path": str(consumer_request.get("preview_level_path") or ""),
                    "host_blueprint_asset_path": str(consumer_request.get("target_host_blueprint_asset_path") or ""),
                    "sample_id": str(selected_clip.get("sample_id") or ""),
                    "package_id": str(selected_clip.get("package_id") or ""),
                    "runtime_ready_only": bool(consumer_request.get("runtime_ready_only", True)),
                    "retarget_if_needed": bool(consumer_request.get("retarget_if_needed", True)),
                    "output_root": str((output_root / "motion" / "preview").resolve()),
                    **(build_retarget_preview_params(import_result, bootstrap_result) if bootstrap_success else {}),
                },
                output_root / "motion" / "animation_preview.action.json",
            )
            write_json(manifest_path.parent / "motion_preview_report.local.json", preview_payload)

    failure_class = classify_motion_failure_class(packet_signal_payload, seam_blockers, import_payload, preview_payload)
    communication_signal = build_motion_communication_signal(packet_signal_payload, seam_blockers, failure_class, "pass")
    consumer_result = build_motion_consumer_result(
        consumer_request,
        selected_clip,
        import_payload,
        import_action_path,
        preview_payload,
        preview_action_path,
        failure_class,
        communication_signal,
        bootstrap_payload,
        bootstrap_action_path,
        author_chains_payload,
        author_chains_action_path,
    )
    if consumer_result:
        communication_signal = build_motion_communication_signal(
            packet_signal_payload,
            seam_blockers,
            failure_class,
            str(consumer_result.get("status") or "fail"),
        )
        consumer_result["communication_signal"] = communication_signal
    else:
        communication_signal = build_motion_communication_signal(packet_signal_payload, seam_blockers, failure_class, "fail")

    consumer_result_path = output_root / "motion_consumer_result_v0.json"
    if consumer_result:
        write_json(consumer_result_path, consumer_result)
    else:
        seam_blockers.append(
            make_failed_requirement(
                "m0_5_consumer_result_missing",
                "M0.5 requires a motion_consumer_result_v0 payload to be written even when execution fails.",
            )
        )

    context_payload = {
        "generated_at_utc": now_utc(),
        "motion_view_root": str(motion_view_root.resolve()) if motion_view_root else "",
        "summary_path": str(summary_path.resolve()) if summary_path else "",
        "registry_path": str(registry_path.resolve()) if registry_path else "",
        "packet_check_path": str(packet_check_path.resolve()) if packet_check_path else "",
        "packet_signal_path": str(packet_signal_path.resolve()) if packet_signal_path and packet_signal_path.exists() else "",
        "packet_signal": packet_signal_payload,
        "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
    }
    selection_payload = dict(selected_clip or {})
    state_payload = {
        "generated_at_utc": now_utc(),
        "status": "pass" if not ({str(item.get('id') or '') for item in seam_blockers} & SEAM_BLOCKING_FAILURE_IDS) and consumer_result else "fail",
        "consumer_result_status": str((consumer_result or {}).get("status") or ""),
        "owner": str(communication_signal.get("owner") or ""),
        "failure_class": failure_class,
        "import_action_path": import_action_path,
        "bootstrap_action_path": bootstrap_action_path,
        "author_chains_action_path": author_chains_action_path,
        "preview_action_path": preview_action_path,
        "import_status": str(import_payload.get("status") or ""),
        "bootstrap_status": str(bootstrap_payload.get("status") or ""),
        "author_chains_status": str(author_chains_payload.get("status") or ""),
        "preview_status": str(preview_payload.get("status") or ""),
        "m1_upgrade_ready": bool(
            consumer_result
            and consumer_result.get("status") == "pass"
            and communication_signal.get("owner") == "none"
        ),
    }
    context_path = state_root / "motion_consumer_context.json"
    selection_path = state_root / "motion_clip_selection.json"
    state_path = state_root / "motion_consumer_state.json"
    latest_request_path = state_root / "latest_motion_consumer_request_v0.json"
    latest_result_path = state_root / "latest_motion_consumer_result_v0.json"
    write_json(context_path, context_payload)
    write_json(selection_path, selection_payload)
    write_json(state_path, state_payload)
    if consumer_request:
        write_json(latest_request_path, consumer_request)
    if consumer_result:
        write_json(latest_result_path, consumer_result)

    seam_blocker_ids = {str(item.get("id") or "") for item in seam_blockers}
    seam_status = "pass" if not (seam_blocker_ids & SEAM_BLOCKING_FAILURE_IDS) and consumer_result else "fail"
    counts = {
        "manifest_count": len(manifest_index),
        "selection_ready_clips": int((packet_check_payload.get("counts") or {}).get("selection_ready_count", 0) or 0),
        "seam_blockers": len(seam_blockers),
        "consumer_result_written": 1 if consumer_result else 0,
        "consumer_execution_pass": 1 if consumer_result and consumer_result.get("status") == "pass" else 0,
        "consumer_execution_fail": 1 if consumer_result and consumer_result.get("status") != "pass" else 0,
    }
    discussion_signal = build_discussion_signal(
        seam_status,
        seam_blockers,
        previous_report,
        previous_report_path,
        "m0_5_first_seam_pass",
    )
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "generated_at_utc": now_utc(),
            "status": seam_status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "toy_yard_motion_view_root": str(motion_view_root.resolve()) if motion_view_root else "",
            "resolved_summary_path": str(summary_path.resolve()) if summary_path else "",
            "resolved_registry_path": str(registry_path.resolve()) if registry_path else "",
            "resolved_packet_check_path": str(packet_check_path.resolve()) if packet_check_path else "",
            "resolved_packet_signal_path": str(packet_signal_path.resolve()) if packet_signal_path and packet_signal_path.exists() else "",
            "resolved_clips_root": str(clips_root.resolve()) if clips_root else "",
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "selected_clip": dict(selected_clip or {}),
            "packet_signal": packet_signal_payload,
            "consumer_request": consumer_request or {},
            "consumer_result": consumer_result or {},
            "consumer_execution": {
                "import_action": {
                    "status": str(import_payload.get("status") or ""),
                    "output_path": str(import_action_path),
                },
                "preview_action": {
                    "status": str(preview_payload.get("status") or ""),
                    "output_path": str(preview_action_path),
                },
                "bootstrap_action": {
                    "status": str(bootstrap_payload.get("status") or ""),
                    "output_path": str(bootstrap_action_path),
                },
                "author_chains_action": {
                    "status": str(author_chains_payload.get("status") or ""),
                    "output_path": str(author_chains_action_path),
                },
                "owner": str(communication_signal.get("owner") or ""),
                "failure_class": failure_class,
                "m1_upgrade_ready": bool(
                    consumer_result
                    and consumer_result.get("status") == "pass"
                    and communication_signal.get("owner") == "none"
                ),
            },
            "counts": counts,
            "failed_requirements": seam_blockers,
            "discussion_signal": discussion_signal,
            "communication_signal": communication_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "motion_consumer_request_path": str(consumer_request_path.resolve()) if consumer_request else "",
                "motion_consumer_result_path": str(consumer_result_path.resolve()) if consumer_result else "",
                "motion_consumer_context_path": str(context_path.resolve()),
                "motion_clip_selection_path": str(selection_path.resolve()),
                "motion_consumer_state_path": str(state_path.resolve()),
            },
        },
        "motion_shadow_packet_trial_m0_5_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "motion_shadow_packet_trial_m0_5_report",
            notes=["internal_gate_runner", "motion_shadow_packet_trial", "toy_yard_motion_consumer_seam_v0"],
        ),
    )

    report_path = output_root / "motion_shadow_packet_trial_m0_5_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    fixed_latest_report_path = repo_root / "Saved" / "verification" / "latest_motion_shadow_packet_trial_m0_5_report.json"
    write_json(fixed_latest_report_path, report_payload)
    print(f"M0.5 motion shadow packet report written to: {report_path}")
    return 0 if seam_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
