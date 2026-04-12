from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, evaluate_external_motion, resolve_report_path, run_host_command_result
from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json
from aiue_t2.state_demo import build_demo_request, load_demo_session


GATE_ID = "action_candidate_provider_a1"
SCHEMA_VERSION = "a1_candidate_manifest_v1"
SUPPORTED_CANDIDATE_PAYLOAD_KIND = "session_animation_preset_ref"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_CANDIDATE_MANIFEST_NAME = "action_candidate_manifest.json"
DEFAULT_PROVIDER_CONTEXT_NAME = "action_candidate_provider_context.json"
DEFAULT_PROVIDER_STATE_NAME = "action_candidate_provider_state.json"
DEFAULT_E2C_LATEST_NAME = "latest_playable_demo_e2c_credible_showcase_polish_report.json"
DEFAULT_DV2_LATEST_NAME = "latest_diversity_matrix_dv2_report.json"
DEFAULT_DYNAMIC_BALANCE_LATEST_NAME = "latest_dynamic_balance_governance_progress_report.json"

FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "supported_candidate_payload_kind": SUPPORTED_CANDIDATE_PAYLOAD_KIND,
    "required_engine_pass_shots": 1,
    "required_external_motion_shots": 1,
    "capture_width": 1280,
    "capture_height": 720,
    "histogram_l1_threshold": 0.015,
    "mean_abs_pixel_delta_threshold": 0.005,
    "candidate_selection_rule": "provider_first_candidate_per_package",
    "derivation_rule": "prefer_non_idle_pass_animation_preset_when_fixture_manifest_is_derived",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE A1 action-candidate provider seam.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--candidate-manifest-path")
    parser.add_argument("--e2c-report-path")
    parser.add_argument("--dv2-report-path")
    parser.add_argument("--dynamic-balance-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--latest-provider-state-path")
    parser.add_argument("--latest-provider-context-path")
    parser.add_argument("--latest-candidate-manifest-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def _a1_latest_root(repo_root: Path) -> Path:
    latest_root = repo_root / "Saved" / "demo" / "a1" / "latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    return latest_root


def default_latest_provider_state_path(repo_root: Path) -> Path:
    return _a1_latest_root(repo_root) / DEFAULT_PROVIDER_STATE_NAME


def default_latest_provider_context_path(repo_root: Path) -> Path:
    return _a1_latest_root(repo_root) / DEFAULT_PROVIDER_CONTEXT_NAME


def default_latest_candidate_manifest_path(repo_root: Path) -> Path:
    return _a1_latest_root(repo_root) / DEFAULT_CANDIDATE_MANIFEST_NAME


def _load_required_report(workspace: dict[str, Any], *, explicit_path: str | None, latest_name: str, missing_message: str) -> Path:
    return resolve_report_path(
        explicit_path,
        default_named_verification_report_path(workspace, REPO_ROOT, latest_name),
        missing_message,
    )


def _normalized_family(preset_payload: dict[str, Any]) -> str:
    return str(preset_payload.get("family") or "").strip().lower()


def _package_map(payload: dict[str, Any], key: str = "packages") -> dict[str, dict[str, Any]]:
    packages: dict[str, dict[str, Any]] = {}
    for item in list(payload.get(key) or []):
        package_payload = dict(item or {})
        package_id = str(package_payload.get("package_id") or "")
        if package_id:
            packages[package_id] = package_payload
    return packages


def _e2c_package_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return _package_map(payload, key="per_package_results")


def _slot_names(package_payload: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(item.get("slot_name") or "")
            for item in list(package_payload.get("slot_bindings") or [])
            if str(item.get("slot_name") or "")
        }
    )


def _first_action_preset_id(package_payload: dict[str, Any]) -> str:
    for preset in list(package_payload.get("action_presets") or []):
        preset_id = str(dict(preset or {}).get("preset_id") or "")
        if preset_id:
            return preset_id
    return ""


def _pick_animation_preset_for_fixture(package_payload: dict[str, Any]) -> dict[str, Any]:
    presets = [dict(item or {}) for item in list(package_payload.get("animation_presets") or [])]
    if not presets:
        return {}
    passing_non_idle = [
        preset
        for preset in presets
        if str(preset.get("status") or "") == "pass" and _normalized_family(preset) != "idle" and "idle" not in str(preset.get("preset_id") or "").lower()
    ]
    if passing_non_idle:
        return passing_non_idle[0]
    passing_any = [preset for preset in presets if str(preset.get("status") or "") == "pass"]
    if passing_any:
        return passing_any[0]
    return presets[0]


def _derive_fixture_candidate_for_package(package_payload: dict[str, Any]) -> dict[str, Any]:
    animation_preset = _pick_animation_preset_for_fixture(package_payload)
    animation_preset_id = str(animation_preset.get("preset_id") or "")
    family = str(animation_preset.get("family") or "")
    requested_animation_asset_path = str(animation_preset.get("requested_animation_asset_path") or "")
    resolved_animation_asset_path = str(
        animation_preset.get("resolved_animation_asset_path")
        or animation_preset.get("retargeted_animation_asset_path")
        or requested_animation_asset_path
        or ""
    )
    notes = ["fixture_session_derivation"]
    if animation_preset_id and _normalized_family(animation_preset) != "idle":
        notes.append("preferred_non_idle_pass_animation")
    return {
        "candidate_id": f"candidate_{animation_preset_id or 'missing_animation'}",
        "candidate_payload_kind": SUPPORTED_CANDIDATE_PAYLOAD_KIND,
        "selected_action_preset_id": _first_action_preset_id(package_payload),
        "selected_animation_preset_id": animation_preset_id,
        "family": family,
        "requested_animation_asset_path": requested_animation_asset_path,
        "resolved_animation_asset_path": resolved_animation_asset_path,
        "source_gate_id": str(animation_preset.get("source_gate_id") or ""),
        "notes": notes,
    }


def _reference_image_paths_for_package(session_package: dict[str, Any], e2c_package: dict[str, Any]) -> dict[str, Any]:
    session_evidence = dict(session_package.get("evidence") or {})
    e2c_hero = dict(e2c_package.get("hero_shot") or {})
    e2c_animation_preview = dict(e2c_package.get("animation_preview") or {})
    e2c_action_preview = dict(e2c_package.get("action_preview") or {})
    e2c_animation_images = dict(e2c_animation_preview.get("key_image_paths") or {})
    e2c_action_images = dict(e2c_action_preview.get("key_image_paths") or {})
    return {
        "hero_before_image_path": str(session_evidence.get("hero_before_image_path") or e2c_hero.get("before_image_path") or ""),
        "hero_after_image_path": str(session_evidence.get("hero_after_image_path") or e2c_hero.get("after_image_path") or ""),
        "action_before_image_path": str(e2c_action_images.get("primary_before") or ""),
        "action_after_image_path": str(e2c_action_images.get("primary_after") or ""),
        "animation_before_image_path": str(e2c_animation_images.get("primary_before") or ""),
        "animation_after_image_path": str(e2c_animation_images.get("primary_after") or ""),
    }


def _derive_fixture_candidate_manifest(
    session_payload: dict[str, Any],
    *,
    session_manifest_path: Path,
    e2c_report: dict[str, Any],
) -> dict[str, Any]:
    e2c_packages = _e2c_package_map(e2c_report)
    packages = []
    for package_payload in list(session_payload.get("packages") or []):
        package_record = dict(package_payload or {})
        package_id = str(package_record.get("package_id") or "")
        e2c_package = e2c_packages.get(package_id, {})
        packages.append(
            {
                "package_id": package_id,
                "sample_id": str(package_record.get("sample_id") or ""),
                "slot_names": _slot_names(package_record),
                "reference_image_paths": _reference_image_paths_for_package(package_record, e2c_package),
                "current_slot_state": {
                    "slot_bindings": [dict(item or {}) for item in list(package_record.get("slot_bindings") or [])],
                    "slot_attach_state": [dict(item or {}) for item in list(package_record.get("slot_attach_state") or [])],
                },
                "candidates": [_derive_fixture_candidate_for_package(package_record)],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "provider_name": "fixture_provider_v1",
        "source_id": "fixture_provider_from_session",
        "source_kind": "fixture_session_derivation",
        "generated_at_utc": now_utc(),
        "source_session_manifest": str(session_manifest_path.resolve()),
        "packages": packages,
    }


def _provider_context_payload(
    session_payload: dict[str, Any],
    *,
    session_manifest_path: Path,
    e2c_report: dict[str, Any],
) -> dict[str, Any]:
    e2c_packages = _e2c_package_map(e2c_report)
    packages = []
    for package_payload in list(session_payload.get("packages") or []):
        package_record = dict(package_payload or {})
        package_id = str(package_record.get("package_id") or "")
        e2c_package = e2c_packages.get(package_id, {})
        packages.append(
            {
                "package_id": package_id,
                "sample_id": str(package_record.get("sample_id") or ""),
                "slot_names": _slot_names(package_record),
                "reference_image_paths": _reference_image_paths_for_package(package_record, e2c_package),
                "action_presets": [
                    {
                        "preset_id": str(dict(item or {}).get("preset_id") or ""),
                        "action_kind": str(dict(item or {}).get("action_kind") or ""),
                    }
                    for item in list(package_record.get("action_presets") or [])
                ],
                "animation_presets": [
                    {
                        "preset_id": str(dict(item or {}).get("preset_id") or ""),
                        "family": str(dict(item or {}).get("family") or ""),
                        "status": str(dict(item or {}).get("status") or ""),
                        "source_gate_id": str(dict(item or {}).get("source_gate_id") or ""),
                        "requested_animation_asset_path": str(dict(item or {}).get("requested_animation_asset_path") or ""),
                        "resolved_animation_asset_path": str(
                            dict(item or {}).get("resolved_animation_asset_path")
                            or dict(item or {}).get("retargeted_animation_asset_path")
                            or ""
                        ),
                    }
                    for item in list(package_record.get("animation_presets") or [])
                ],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "provider_name": "fixture_provider_v1",
        "source_id": "fixture_provider_from_session",
        "source_kind": "fixture_session_derivation",
        "generated_at_utc": now_utc(),
        "source_session_manifest": str(session_manifest_path.resolve()),
        "packages": packages,
    }


def _validate_candidate_manifest(candidate_manifest: dict[str, Any], session_payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if str(candidate_manifest.get("schema_version") or "") != SCHEMA_VERSION:
        failures.append(
            make_failed_requirement(
                "a1_candidate_manifest_schema_mismatch",
                "A1 requires the candidate manifest to declare the supported schema version.",
                expected_schema_version=SCHEMA_VERSION,
                actual_schema_version=str(candidate_manifest.get("schema_version") or ""),
            )
        )
    manifest_packages = _package_map(candidate_manifest)
    session_packages = _package_map(session_payload)
    if len(manifest_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failures.append(
            make_failed_requirement(
                "a1_candidate_manifest_package_count_mismatch",
                "A1 requires the candidate manifest to resolve exactly two session packages.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                manifest_package_ids=sorted(manifest_packages.keys()),
            )
        )
    for package_id, session_package in session_packages.items():
        manifest_package = manifest_packages.get(package_id)
        if not manifest_package:
            failures.append(
                make_failed_requirement(
                    "a1_candidate_manifest_package_missing",
                    "A1 requires a provider package entry for every session package.",
                    package_id=package_id,
                )
            )
            continue
        candidates = [dict(item or {}) for item in list(manifest_package.get("candidates") or [])]
        if not candidates:
            failures.append(
                make_failed_requirement(
                    "a1_candidate_missing",
                    "A1 requires at least one candidate per package.",
                    package_id=package_id,
                )
            )
            continue
        first_candidate = candidates[0]
        if str(first_candidate.get("candidate_payload_kind") or "") != SUPPORTED_CANDIDATE_PAYLOAD_KIND:
            failures.append(
                make_failed_requirement(
                    "a1_candidate_payload_kind_unsupported",
                    "A1 v1 only supports session animation preset reference candidates.",
                    package_id=package_id,
                    candidate_payload_kind=str(first_candidate.get("candidate_payload_kind") or ""),
                    supported_candidate_payload_kind=SUPPORTED_CANDIDATE_PAYLOAD_KIND,
                )
            )
        animation_preset_id = str(first_candidate.get("selected_animation_preset_id") or "")
        available_animation_preset_ids = {
            str(dict(item or {}).get("preset_id") or "")
            for item in list(session_package.get("animation_presets") or [])
        }
        if not animation_preset_id or animation_preset_id not in available_animation_preset_ids:
            failures.append(
                make_failed_requirement(
                    "a1_animation_preset_missing",
                    "A1 requires each candidate to reference an existing session animation preset.",
                    package_id=package_id,
                    selected_animation_preset_id=animation_preset_id,
                    available_animation_preset_ids=sorted(item for item in available_animation_preset_ids if item),
                )
            )
        action_preset_id = str(first_candidate.get("selected_action_preset_id") or "")
        available_action_preset_ids = {
            str(dict(item or {}).get("preset_id") or "")
            for item in list(session_package.get("action_presets") or [])
        }
        if action_preset_id and action_preset_id not in available_action_preset_ids:
            failures.append(
                make_failed_requirement(
                    "a1_action_preset_missing",
                    "A1 requires selected action preset ids to resolve inside the session package when provided.",
                    package_id=package_id,
                    selected_action_preset_id=action_preset_id,
                    available_action_preset_ids=sorted(item for item in available_action_preset_ids if item),
                )
            )
    return failures


def _candidate_source_metadata(candidate_manifest: dict[str, Any]) -> list[dict[str, Any]]:
    packages = [dict(item or {}) for item in list(candidate_manifest.get("packages") or [])]
    provider_name = str(candidate_manifest.get("provider_name") or "")
    source_id = str(candidate_manifest.get("source_id") or "")
    source_kind = str(candidate_manifest.get("source_kind") or "")
    if not packages and not provider_name and not source_id and not source_kind:
        return []
    return [
        {
            "provider_name": provider_name or "unknown_provider",
            "source_id": source_id or "unknown_source",
            "source_kind": source_kind or "unknown",
            "candidate_count": sum(len(list(package.get("candidates") or [])) for package in packages),
            "package_ids": [str(package.get("package_id") or "") for package in packages if str(package.get("package_id") or "")],
        }
    ]


def _first_candidate(package_entry: dict[str, Any]) -> dict[str, Any]:
    for candidate in list(package_entry.get("candidates") or []):
        candidate_payload = dict(candidate or {})
        if candidate_payload:
            return candidate_payload
    return {}


def _find_primary_images(host_result: dict[str, Any]) -> dict[str, Any]:
    before_images: list[str] = []
    after_images: list[str] = []
    for shot in list(host_result.get("shots") or []):
        before_path = str(dict(shot.get("before") or {}).get("image_path") or "")
        after_path = str(dict(shot.get("after") or {}).get("image_path") or "")
        if before_path:
            before_images.append(before_path)
        if after_path:
            after_images.append(after_path)
    return {
        "before": before_images,
        "after": after_images,
        "primary_before": before_images[0] if before_images else "",
        "primary_after": after_images[0] if after_images else "",
    }


def _subject_visible(host_result: dict[str, Any]) -> bool:
    for shot in list(host_result.get("shots") or []):
        for phase_key in ("before", "after"):
            phase = dict(shot.get(phase_key) or {})
            coverage = dict(phase.get("subject_coverage") or {})
            coverage_ratio = float(phase.get("subject_screen_coverage") or coverage.get("coverage_ratio") or 0.0)
            if bool(phase.get("line_of_sight_clear")) and coverage_ratio > 0.0 and bool(coverage.get("in_frame", True)):
                return True
    return False


def _evaluate_candidate_result(
    *,
    repo_root: Path,
    host_result: dict[str, Any],
    host_invocation_error: str | None,
    result_path: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    failed_requirements: list[dict[str, Any]] = []
    if str(host_result.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "a1_animation_preview_failed",
                "A1 requires the selected animation preview invoke to pass.",
                host_invocation_error=host_invocation_error,
                host_errors=list(host_result.get("errors") or []),
                result_path=str(result_path.resolve()),
            )
        )
    shots = [dict(item or {}) for item in list(host_result.get("shots") or [])]
    passing_engine_shots = sum(1 for shot in shots if str(shot.get("status") or "") == "pass")
    if passing_engine_shots < int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots"]):
        failed_requirements.append(
            make_failed_requirement(
                "a1_engine_motion_preview_missing",
                "A1 requires at least one passing engine-side animation preview shot.",
                required_passing_engine_shots=int(FIXED_EXECUTION_PROFILE["required_engine_pass_shots"]),
                actual_passing_engine_shots=passing_engine_shots,
            )
        )
    external_motion_evidence, passing_external_motion_shots = evaluate_external_motion(
        repo_root,
        shots,
        capture_width=int(FIXED_EXECUTION_PROFILE["capture_width"]),
        capture_height=int(FIXED_EXECUTION_PROFILE["capture_height"]),
        histogram_l1_threshold=float(FIXED_EXECUTION_PROFILE["histogram_l1_threshold"]),
        mean_abs_pixel_delta_threshold=float(FIXED_EXECUTION_PROFILE["mean_abs_pixel_delta_threshold"]),
    )
    external_motion_verified = passing_external_motion_shots >= int(FIXED_EXECUTION_PROFILE["required_external_motion_shots"])
    if not external_motion_verified:
        failed_requirements.append(
            make_failed_requirement(
                "a1_external_motion_evidence_missing",
                "A1 requires at least one passing external motion evidence shot.",
                required_external_motion_shots=int(FIXED_EXECUTION_PROFILE["required_external_motion_shots"]),
                actual_external_motion_shots=passing_external_motion_shots,
            )
        )
    native_pose = dict(host_result.get("native_animation_pose_evaluation") or {})
    pose_probe = dict(host_result.get("pose_probe_delta") or {})
    animation_pose_verified = bool(native_pose.get("pose_changed")) or int(pose_probe.get("moving_bone_count") or 0) > 0
    if not animation_pose_verified:
        failed_requirements.append(
            make_failed_requirement(
                "a1_animation_pose_not_verified",
                "A1 requires native pose-change or probe-delta evidence for the selected candidate.",
                native_animation_pose_evaluation=native_pose,
                pose_probe_delta=pose_probe,
            )
        )
    key_images = _find_primary_images(host_result)
    before_image_present = bool(key_images["primary_before"]) and Path(key_images["primary_before"]).exists()
    after_image_present = bool(key_images["primary_after"]) and Path(key_images["primary_after"]).exists()
    if not before_image_present or not after_image_present:
        failed_requirements.append(
            make_failed_requirement(
                "a1_key_images_missing",
                "A1 requires before/after key images for the selected candidate invoke.",
                key_images=key_images,
            )
        )
    subject_visible = _subject_visible(host_result)
    if not subject_visible:
        failed_requirements.append(
            make_failed_requirement(
                "a1_subject_not_visible",
                "A1 requires the animated subject to remain visible in the selected preview shots.",
                key_images=key_images,
            )
        )
    warning_flags = list(host_result.get("warnings") or [])
    if not external_motion_verified:
        warning_flags.append("external_motion_not_verified")
    if not animation_pose_verified:
        warning_flags.append("animation_pose_not_verified")
    if not subject_visible:
        warning_flags.append("subject_not_visible")
    credibility_summary = {
        "subject_visible": subject_visible,
        "before_image_present": before_image_present,
        "after_image_present": after_image_present,
        "animation_pose_verified": animation_pose_verified,
        "external_motion_verified": external_motion_verified,
        "warning_flags": warning_flags,
        "native_animation_pose_evaluation": native_pose,
        "pose_probe_delta": pose_probe,
    }
    evaluation = {
        "status": "pass" if not failed_requirements else "fail",
        "counts": {
            "captured_shot_pairs": len(shots),
            "passing_engine_shots": passing_engine_shots,
            "passing_external_motion_shots": passing_external_motion_shots,
            "native_changed_bone_count": int(native_pose.get("changed_bone_count") or 0),
            "moving_probe_bone_count": int(pose_probe.get("moving_bone_count") or 0),
        },
        "resolved_animation_asset_path": str(host_result.get("resolved_animation_asset_path") or ""),
        "native_animation_pose_evaluation": native_pose,
        "pose_probe_delta": pose_probe,
        "shots": shots,
        "external_motion_evidence": external_motion_evidence,
        "key_images": key_images,
        "failed_requirements": failed_requirements,
        "warnings": list(host_result.get("warnings") or []),
        "errors": list(host_result.get("errors") or []),
        "artifacts": {
            "result_path": str(result_path.resolve()),
        },
    }
    return evaluation, credibility_summary


def _provider_state_payload(
    *,
    session_manifest_path: Path,
    candidate_manifest_path: Path,
    provider_context_path: Path,
    report_payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": str(report_payload.get("status") or "unknown"),
        "generated_at_utc": now_utc(),
        "source_session_manifest": str(session_manifest_path.resolve()),
        "candidate_manifest_path": str(candidate_manifest_path.resolve()),
        "provider_context_path": str(provider_context_path.resolve()),
        "counts": dict(report_payload.get("counts") or {}),
        "external_candidate_sources": [dict(item or {}) for item in list(report_payload.get("external_candidate_sources") or [])],
        "per_package_results": [
            {
                "package_id": str(item.get("package_id") or ""),
                "candidate_id": str(item.get("candidate_id") or ""),
                "status": str(item.get("status") or ""),
                "selected_animation_preset_id": str(item.get("selected_animation_preset_id") or ""),
                "credibility_summary": dict(item.get("credibility_summary") or {}),
            }
            for item in list(report_payload.get("per_package_results") or [])
        ],
        "report_path": str(dict(report_payload.get("artifacts") or {}).get("report_path") or ""),
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    workspace_config_path = Path(args.workspace_config).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    latest_provider_state_path = (
        Path(args.latest_provider_state_path).expanduser().resolve()
        if args.latest_provider_state_path
        else default_latest_provider_state_path(repo_root)
    )
    latest_provider_context_path = (
        Path(args.latest_provider_context_path).expanduser().resolve()
        if args.latest_provider_context_path
        else default_latest_provider_context_path(repo_root)
    )
    latest_candidate_manifest_path = (
        Path(args.latest_candidate_manifest_path).expanduser().resolve()
        if args.latest_candidate_manifest_path
        else default_latest_candidate_manifest_path(repo_root)
    )
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    latest_provider_state_path.parent.mkdir(parents=True, exist_ok=True)
    latest_provider_context_path.parent.mkdir(parents=True, exist_ok=True)
    latest_candidate_manifest_path.parent.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None
    failed_requirements: list[dict[str, Any]] = []

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "a1_session_manifest_missing",
                "A1 requires the latest E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload: dict[str, Any] = {}
    else:
        session_payload = load_json(session_manifest_path)

    required_reports: dict[str, dict[str, Any]] = {}
    required_report_paths: dict[str, str] = {}
    for report_key, explicit_path, latest_name, missing_message in (
        ("e2c", args.e2c_report_path, DEFAULT_E2C_LATEST_NAME, "A1 requires the latest E2C credible showcase polish report."),
        ("dv2", args.dv2_report_path, DEFAULT_DV2_LATEST_NAME, "A1 requires the latest DV2 diversity expansion report."),
        (
            "dynamic_balance",
            args.dynamic_balance_report_path,
            DEFAULT_DYNAMIC_BALANCE_LATEST_NAME,
            "A1 requires the latest Dynamic Balance governance report.",
        ),
    ):
        try:
            report_path = _load_required_report(
                workspace,
                explicit_path=explicit_path,
                latest_name=latest_name,
                missing_message=missing_message,
            )
            required_reports[report_key] = load_json(report_path)
            required_report_paths[report_key] = str(report_path.resolve())
        except FileNotFoundError as exc:
            failed_requirements.append(
                make_failed_requirement(
                    "a1_required_report_missing",
                    missing_message,
                    report_name=latest_name,
                    report_path=str(exc),
                )
            )
            required_reports[report_key] = {}
            required_report_paths[report_key] = ""

    if required_reports["e2c"] and str(required_reports["e2c"].get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "a1_e2c_not_pass",
                "A1 requires E2C to pass before motion-candidate evaluation begins.",
                report_path=required_report_paths.get("e2c", ""),
                report_status=required_reports["e2c"].get("status"),
            )
        )
    if required_reports["dv2"] and str(required_reports["dv2"].get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "a1_dv2_not_pass",
                "A1 requires DV2 automated diversity coverage to remain green.",
                report_path=required_report_paths.get("dv2", ""),
                report_status=required_reports["dv2"].get("status"),
            )
        )
    dynamic_balance_report = dict(required_reports.get("dynamic_balance") or {})
    if dynamic_balance_report:
        next_round_kind = str(dict(dynamic_balance_report.get("recommendation") or {}).get("next_round_kind") or "")
        if next_round_kind == "stabilization":
            failed_requirements.append(
                make_failed_requirement(
                    "a1_dynamic_balance_blocks_progress",
                    "A1 may not begin while Dynamic Balance recommends stabilization.",
                    report_path=required_report_paths.get("dynamic_balance", ""),
                    recommended_next_round_kind=next_round_kind,
                )
            )

    provider_context = _provider_context_payload(
        session_payload,
        session_manifest_path=session_manifest_path,
        e2c_report=dict(required_reports.get("e2c") or {}),
    )
    provider_context_path = output_root / DEFAULT_PROVIDER_CONTEXT_NAME
    write_json(provider_context_path, provider_context)
    write_json(latest_provider_context_path, provider_context)

    if args.candidate_manifest_path:
        candidate_manifest_input_path = Path(args.candidate_manifest_path).expanduser().resolve()
        if not candidate_manifest_input_path.exists():
            failed_requirements.append(
                make_failed_requirement(
                    "a1_candidate_manifest_missing",
                    "The requested action-candidate manifest does not exist.",
                    candidate_manifest_path=str(candidate_manifest_input_path),
                )
            )
            candidate_manifest = {}
        else:
            candidate_manifest = load_json(candidate_manifest_input_path)
    else:
        candidate_manifest_input_path = latest_candidate_manifest_path
        candidate_manifest = _derive_fixture_candidate_manifest(
            session_payload,
            session_manifest_path=session_manifest_path,
            e2c_report=dict(required_reports.get("e2c") or {}),
        )

    normalized_candidate_manifest_path = output_root / DEFAULT_CANDIDATE_MANIFEST_NAME
    write_json(normalized_candidate_manifest_path, candidate_manifest)
    write_json(latest_candidate_manifest_path, candidate_manifest)
    failed_requirements.extend(_validate_candidate_manifest(candidate_manifest, session_payload))

    demo_session_errors: list[Any] = []
    demo_session = load_demo_session(
        manifest_path=session_manifest_path,
        session_manifest_path=session_manifest_path,
        errors=demo_session_errors,
    )
    if str(demo_session.status or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "a1_demo_session_unavailable",
                "A1 requires the demo session to resolve cleanly before candidate execution.",
                demo_session_status=demo_session.status,
                demo_session_errors=[getattr(item, "code", str(item)) for item in demo_session_errors],
            )
        )

    session_packages = _package_map(session_payload)
    manifest_packages = _package_map(candidate_manifest)
    if len(session_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "a1_required_package_count_mismatch",
                "A1 requires exactly two ready session packages.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=sorted(session_packages.keys()),
            )
        )

    per_package_results: list[dict[str, Any]] = []
    per_candidate_results: list[dict[str, Any]] = []
    provider_name = str(candidate_manifest.get("provider_name") or "unknown_provider")
    source_id = str(candidate_manifest.get("source_id") or "unknown_source")
    source_kind = str(candidate_manifest.get("source_kind") or "unknown")

    for package_id, session_package in session_packages.items():
        package_entry = manifest_packages.get(package_id, {})
        candidate = _first_candidate(package_entry)
        package_failures: list[dict[str, Any]] = []
        selected_action_preset_id = str(candidate.get("selected_action_preset_id") or _first_action_preset_id(session_package))
        selected_animation_preset_id = str(candidate.get("selected_animation_preset_id") or "")
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate:
            package_failures.append(
                make_failed_requirement(
                    "a1_package_candidate_missing",
                    "A1 requires a provider candidate for each session package.",
                    package_id=package_id,
                )
            )
        demo_request = build_demo_request(
            demo_session=demo_session,
            selected_package_id=package_id,
            selected_action_preset_id=selected_action_preset_id or None,
            selected_animation_preset_id=selected_animation_preset_id or None,
        )
        animation_request = dict(demo_request.requests.get("animation_preview") or {})
        request_root = output_root / "candidate_runs" / package_id / (candidate_id or "missing_candidate")
        request_root.mkdir(parents=True, exist_ok=True)
        request_json_path = request_root / "animation_preview_request.json"
        result_json_path = request_root / "animation_preview_result.json"

        if str(demo_request.status or "") != "pass" or not animation_request:
            package_failures.append(
                make_failed_requirement(
                    "a1_animation_request_unavailable",
                    "A1 requires the demo request builder to produce an animation preview request.",
                    package_id=package_id,
                    demo_request_status=demo_request.status,
                    demo_request_errors=list(demo_request.errors or []),
                )
            )
            evaluation = {"status": "fail", "counts": {}, "failed_requirements": package_failures, "key_images": {}, "artifacts": {"result_path": str(result_json_path.resolve())}}
            credibility_summary = {
                "subject_visible": False,
                "before_image_present": False,
                "after_image_present": False,
                "animation_pose_verified": False,
                "external_motion_verified": False,
                "warning_flags": ["animation_request_unavailable"],
            }
        else:
            animation_request["params"] = dict(animation_request.get("params") or {})
            animation_request["params"]["output_root"] = str((request_root / "captures").resolve())
            write_json(request_json_path, animation_request)
            host_result: dict[str, Any] = {}
            host_invocation_error = None
            try:
                host_result, host_invocation_error, result_path = run_host_command_result(
                    workspace=workspace,
                    mode=str(animation_request.get("mode") or FIXED_EXECUTION_PROFILE["mode"]),
                    command=str(animation_request.get("command") or "animation-preview"),
                    params=dict(animation_request.get("params") or {}),
                    output_path=result_json_path,
                    host_key=str(animation_request.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
                )
            except Exception as exc:
                host_invocation_error = str(exc)
                result_path = result_json_path
            evaluation, credibility_summary = _evaluate_candidate_result(
                repo_root=repo_root,
                host_result=host_result,
                host_invocation_error=host_invocation_error,
                result_path=result_path,
            )
            package_failures.extend(list(evaluation.get("failed_requirements") or []))

        warning_flags = list(credibility_summary.get("warning_flags") or [])
        package_status = "pass" if not package_failures else "fail"
        per_package_results.append(
            {
                "package_id": package_id,
                "sample_id": str(session_package.get("sample_id") or ""),
                "candidate_id": candidate_id,
                "selected_action_preset_id": selected_action_preset_id,
                "selected_animation_preset_id": selected_animation_preset_id,
                "status": package_status,
                "warning_flags": warning_flags,
                "credibility_summary": credibility_summary,
                "failed_requirements": package_failures,
            }
        )
        per_candidate_results.append(
            {
                "package_id": package_id,
                "sample_id": str(session_package.get("sample_id") or ""),
                "provider_name": provider_name,
                "source_id": source_id,
                "source_kind": source_kind,
                "candidate_id": candidate_id,
                "candidate_payload_kind": str(candidate.get("candidate_payload_kind") or ""),
                "selected_action_preset_id": selected_action_preset_id,
                "selected_animation_preset_id": selected_animation_preset_id,
                "requested_animation_asset_path": str(candidate.get("requested_animation_asset_path") or ""),
                "resolved_animation_asset_path": str(
                    evaluation.get("resolved_animation_asset_path")
                    or candidate.get("resolved_animation_asset_path")
                    or candidate.get("requested_animation_asset_path")
                    or ""
                ),
                "request_json_path": str(request_json_path.resolve()),
                "result_json_path": str(dict(evaluation.get("artifacts") or {}).get("result_path") or str(result_json_path.resolve())),
                "key_images": dict(evaluation.get("key_images") or {}),
                "credibility_summary": credibility_summary,
                "warning_flags": warning_flags,
                "status": package_status,
                "failed_requirements": package_failures,
            }
        )

    counts = {
        "resolved_package_count": len(per_package_results),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "resolved_candidate_count": len(per_candidate_results),
        "passing_candidates": sum(1 for item in per_candidate_results if str(item.get("status") or "") == "pass"),
        "candidate_source_count": len(_candidate_source_metadata(candidate_manifest)),
    }
    failed_requirements.extend(
        make_failed_requirement(
            f"a1_package_failed_{str(item.get('package_id') or '')}",
            "A1 requires every resolved package candidate to pass.",
            package_id=str(item.get("package_id") or ""),
            candidate_id=str(item.get("candidate_id") or ""),
        )
        for item in per_package_results
        if str(item.get("status") or "") != "pass"
    )
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "a1_first_full_pass",
    )
    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "consumed_reports": required_report_paths,
            "external_candidate_sources": _candidate_source_metadata(candidate_manifest),
            "per_package_results": per_package_results,
            "per_candidate_results": per_candidate_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "provider_context_path": str(provider_context_path.resolve()),
                "candidate_manifest_path": str(normalized_candidate_manifest_path.resolve()),
                "provider_state_path": str(latest_provider_state_path.resolve()),
            },
        },
        "aiue_action_candidate_provider_a1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            schema_family="aiue_action_candidate_provider_a1_report",
            notes=[
                "internal_action_candidate_provider_seam",
                "consumes_dv2_and_e2c",
                "supports_session_animation_preset_ref_only",
            ],
        ),
    )
    report_path = output_root / "action_candidate_provider_a1_report.json"
    report_payload["artifacts"]["report_path"] = str(report_path.resolve())
    write_report_pair(report_payload, report_path, latest_report_path)

    provider_state = _provider_state_payload(
        session_manifest_path=session_manifest_path,
        candidate_manifest_path=normalized_candidate_manifest_path,
        provider_context_path=provider_context_path,
        report_payload=report_payload,
    )
    write_json(output_root / DEFAULT_PROVIDER_STATE_NAME, provider_state)
    write_json(latest_provider_state_path, provider_state)
    print(str(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
