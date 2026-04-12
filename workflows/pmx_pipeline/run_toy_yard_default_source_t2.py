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
from aiue_t1.toy_yard_manifest_artifact_check import build_manifest_artifact_check_report  # noqa: E402
from aiue_unreal.action_runner import run_action  # noqa: E402
from toy_yard_view import (  # noqa: E402
    build_toy_yard_manifest_index,
    resolve_toy_yard_registry_path,
    resolve_toy_yard_summary_path,
    resolve_toy_yard_view_root,
)


GATE_ID = "toy_yard_default_source_t2"
FIXED_EXECUTION_PROFILE = {
    "source_mode": "toy_yard_default_source",
    "mode": "cmd_nullrhi",
    "lanes": ["solo", "bundle"],
    "default_source_required": True,
    "raw_package_discovery_allowed": False,
    "toy_yard_sqlite_required": False,
    "roundtrip_required": False,
    "communication_signal_enabled": True,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE T2 toy-yard default-source confirmation gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--summary-path")
    parser.add_argument("--registry-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def resolve_summary_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Summary path does not exist: {candidate}")
    candidate = resolve_toy_yard_summary_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard suite summary could be resolved from workspace paths.toy_yard_pmx_view_root.")


def resolve_registry_path(workspace: dict, explicit_path: str | None) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Registry path does not exist: {candidate}")
    candidate = resolve_toy_yard_registry_path(workspace)
    if candidate:
        return candidate
    raise FileNotFoundError("No toy-yard equipment registry could be resolved from workspace paths.toy_yard_pmx_view_root.")


def _candidate_success_entries(summary_payload: dict[str, Any], manifest_index: dict[str, Path]) -> list[dict[str, Any]]:
    results = []
    for entry in list(summary_payload.get("successes") or []):
        package_id = str(entry.get("package_id") or "").strip()
        if not package_id or package_id not in manifest_index:
            continue
        if not bool(entry.get("consumer_ready")):
            continue
        results.append(dict(entry))
    return results


def select_solo_candidate(summary_payload: dict[str, Any], manifest_index: dict[str, Path]) -> dict[str, Any] | None:
    candidates = [
        entry
        for entry in _candidate_success_entries(summary_payload, manifest_index)
        if str(entry.get("content_bucket") or "") == "Characters"
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: str(item.get("package_id") or ""))
    selected = dict(candidates[0])
    package_id = str(selected.get("package_id") or "")
    selected["manifest_path"] = str(manifest_index[package_id])
    return selected


def select_bundle_candidate(registry_payload: dict[str, Any], manifest_index: dict[str, Path]) -> dict[str, Any] | None:
    candidates = []
    for entry in list(registry_payload.get("ready_pairs") or []):
        character_package_id = str(entry.get("character_package_id") or "").strip()
        weapon_package_id = str(entry.get("weapon_package_id") or "").strip()
        if not character_package_id or not weapon_package_id:
            continue
        if character_package_id not in manifest_index or weapon_package_id not in manifest_index:
            continue
        candidate = dict(entry)
        candidate["character_manifest_path"] = str(manifest_index[character_package_id])
        candidate["weapon_manifest_path"] = str(manifest_index[weapon_package_id])
        candidates.append(candidate)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (str(item.get("sample_id") or ""), str(item.get("character_package_id") or ""), str(item.get("weapon_package_id") or "")))
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


def evaluate_solo_lane(workspace: dict, output_root: Path, solo_candidate: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lane_root = output_root / "solo"
    lane_root.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(str(solo_candidate["manifest_path"])).expanduser().resolve()
    import_payload, import_action_path = run_workflow_action(
        workspace,
        "import-package",
        {
            "manifest": str(manifest_path),
        },
        lane_root / "import_package.action.json",
    )
    import_success, import_warnings, import_result = evaluate_action_payload(import_payload)
    import_report_path = str(import_result.get("import_report_path") or (manifest_path.parent / "ue_import_report.local.json"))
    validate_payload, validate_action_path = run_workflow_action(
        workspace,
        "validate-package",
        {
            "manifest": str(manifest_path),
            "import_report": import_report_path,
        },
        lane_root / "validate_package.action.json",
    )
    validate_success, validate_warnings, validate_result = evaluate_action_payload(validate_payload)

    failed_requirements: list[dict[str, Any]] = []
    if not import_success:
        failed_requirements.append(
            make_failed_requirement(
                "t2_solo_import_failed",
                "T2A requires the solo lane import-package action to pass from toy-yard export only.",
                action_path=import_action_path,
                errors=list(import_payload.get("errors") or []),
            )
        )
    if not validate_success:
        failed_requirements.append(
            make_failed_requirement(
                "t2_solo_validate_failed",
                "T2A requires the solo lane validate-package action to pass from toy-yard export only.",
                action_path=validate_action_path,
                errors=list(validate_payload.get("errors") or []),
            )
        )

    return (
        {
            "lane_id": "solo",
            "status": "pass" if not failed_requirements else "fail",
            "selected_package_id": str(solo_candidate.get("package_id") or ""),
            "selected_manifest_path": str(manifest_path),
            "source_mode": "toy_yard_export",
            "import_action": {
                "status": str(import_payload.get("status") or ""),
                "output_path": str(import_action_path),
                "warnings": import_warnings,
                "import_report_path": str(import_result.get("import_report_path") or ""),
                "validation_report_path": str(import_result.get("validation_report_path") or ""),
            },
            "validate_action": {
                "status": str(validate_payload.get("status") or ""),
                "output_path": str(validate_action_path),
                "warnings": validate_warnings,
                "validation_score": validate_result.get("validation_score"),
                "validation_status": validate_result.get("validation_status"),
            },
        },
        failed_requirements,
    )


def evaluate_bundle_lane(workspace: dict, output_root: Path, summary_path: Path, bundle_candidate: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lane_root = output_root / "bundle"
    lane_root.mkdir(parents=True, exist_ok=True)
    character_manifest_path = Path(str(bundle_candidate["character_manifest_path"])).expanduser().resolve()
    weapon_manifest_path = Path(str(bundle_candidate["weapon_manifest_path"])).expanduser().resolve()

    character_import_payload, character_import_action_path = run_workflow_action(
        workspace,
        "import-package",
        {
            "manifest": str(character_manifest_path),
        },
        lane_root / "import_package_character.action.json",
    )
    weapon_import_payload, weapon_import_action_path = run_workflow_action(
        workspace,
        "import-package",
        {
            "manifest": str(weapon_manifest_path),
        },
        lane_root / "import_package_weapon.action.json",
    )
    character_import_success, character_import_warnings, character_import_result = evaluate_action_payload(character_import_payload)
    weapon_import_success, weapon_import_warnings, weapon_import_result = evaluate_action_payload(weapon_import_payload)

    refresh_payload, refresh_action_path = run_workflow_action(
        workspace,
        "refresh-assets",
        {
            "summary": str(summary_path.resolve()),
            "registry_output": str((lane_root / "ue_equipment_registry.t2.json").resolve()),
            "assets_output": str((lane_root / "ue_equipment_assets_report.t2.json").resolve()),
        },
        lane_root / "refresh_assets.action.json",
    )
    refresh_success, refresh_warnings, refresh_result = evaluate_action_payload(refresh_payload)
    assets_report_path = lane_root / "ue_equipment_assets_report.t2.json"
    assets_report = load_json(assets_report_path) if assets_report_path.exists() else {}
    counts = dict(assets_report.get("counts") or {})

    failed_requirements: list[dict[str, Any]] = []
    if not character_import_success:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_character_import_failed",
                "T2A requires the bundle character import-package action to pass from toy-yard export only.",
                action_path=character_import_action_path,
                errors=list(character_import_payload.get("errors") or []),
            )
        )
    if not weapon_import_success:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_weapon_import_failed",
                "T2A requires the bundle weapon import-package action to pass from toy-yard export only.",
                action_path=weapon_import_action_path,
                errors=list(weapon_import_payload.get("errors") or []),
            )
        )
    if not refresh_success:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_refresh_failed",
                "T2A requires the bundle refresh-assets action to pass from toy-yard export summary only.",
                action_path=refresh_action_path,
                errors=list(refresh_payload.get("errors") or []),
            )
        )
    if refresh_warnings:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_refresh_warnings_present",
                "T2A requires the bundle refresh-assets action to complete without warnings.",
                action_path=refresh_action_path,
                warnings=refresh_warnings,
            )
        )
    if int(counts.get("runtime_ready_host_blueprints") or 0) < 1:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_runtime_ready_host_missing",
                "T2A requires refresh-assets to produce at least one runtime-ready host blueprint.",
                assets_report_path=str(assets_report_path.resolve()),
                counts=counts,
            )
        )
    if int(counts.get("runtime_preview_fail") or 0) > 0:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_runtime_preview_failed",
                "T2A requires refresh-assets runtime preview checks to complete without failures.",
                assets_report_path=str(assets_report_path.resolve()),
                counts=counts,
            )
        )

    return (
        {
            "lane_id": "bundle",
            "status": "pass" if not failed_requirements else "fail",
            "selected_sample_id": str(bundle_candidate.get("sample_id") or ""),
            "selected_character_package_id": str(bundle_candidate.get("character_package_id") or ""),
            "selected_weapon_package_id": str(bundle_candidate.get("weapon_package_id") or ""),
            "selected_character_manifest_path": str(character_manifest_path),
            "selected_weapon_manifest_path": str(weapon_manifest_path),
            "source_mode": "toy_yard_export",
            "character_import_action": {
                "status": str(character_import_payload.get("status") or ""),
                "output_path": str(character_import_action_path),
                "warnings": character_import_warnings,
                "import_report_path": str(character_import_result.get("import_report_path") or ""),
            },
            "weapon_import_action": {
                "status": str(weapon_import_payload.get("status") or ""),
                "output_path": str(weapon_import_action_path),
                "warnings": weapon_import_warnings,
                "import_report_path": str(weapon_import_result.get("import_report_path") or ""),
            },
            "refresh_action": {
                "status": str(refresh_payload.get("status") or ""),
                "output_path": str(refresh_action_path),
                "warnings": refresh_warnings,
                "registry_output_path": str((lane_root / "ue_equipment_registry.t2.json").resolve()),
                "assets_output_path": str(assets_report_path.resolve()),
            },
            "runtime_counts": counts,
        },
        failed_requirements,
    )


def build_communication_signal(
    *,
    manifest_check_payload: dict[str, Any],
    failed_requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    failed_ids = {str(item.get("id") or "") for item in failed_requirements}
    if str(manifest_check_payload.get("status") or "") != "pass":
        return {
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": "export_packet_artifact_contract_issue",
            "recommended_node": "contract_adjustment_or_export_packet_rebuild",
        }
    if failed_ids & {
        "t2_summary_path_missing",
        "t2_registry_path_missing",
        "t2_view_root_missing",
        "t2_solo_candidate_missing",
        "t2_bundle_candidate_missing",
        "t2_bundle_runtime_mesh_missing",
    }:
        return {
            "should_contact_toy_yard": True,
            "owner": "toy-yard",
            "reason": "default_source_resolution_or_registry_contract_issue",
            "recommended_node": "toy_yard_t2_contract_followup",
        }
    if failed_ids:
        return {
            "should_contact_toy_yard": False,
            "owner": "aiue",
            "reason": "aiue_runtime_or_consumption_issue",
            "recommended_node": "aiue_runtime_followup",
        }
    return {
        "should_contact_toy_yard": False,
        "owner": "none",
        "reason": "no_external_followup_needed",
        "recommended_node": None,
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []

    toy_yard_view_root = resolve_toy_yard_view_root(workspace)
    if toy_yard_view_root is None:
        failed_requirements.append(
            make_failed_requirement(
                "t2_view_root_missing",
                "T2A requires paths.toy_yard_pmx_view_root to resolve to a valid toy-yard export root.",
            )
        )
    try:
        summary_path = resolve_summary_path(workspace, args.summary_path)
    except FileNotFoundError as exc:
        summary_path = None
        failed_requirements.append(
            make_failed_requirement(
                "t2_summary_path_missing",
                "T2A requires a resolvable toy-yard suite summary path.",
                error=str(exc),
            )
        )
    try:
        registry_path = resolve_registry_path(workspace, args.registry_path)
    except FileNotFoundError as exc:
        registry_path = None
        failed_requirements.append(
            make_failed_requirement(
                "t2_registry_path_missing",
                "T2A requires a resolvable toy-yard equipment registry path.",
                error=str(exc),
            )
        )

    summary_payload = load_json(summary_path) if summary_path and summary_path.exists() else {}
    registry_payload = load_json(registry_path) if registry_path and registry_path.exists() else {}
    if summary_path and summary_path.exists():
        conversion_root, manifest_index = build_toy_yard_manifest_index(summary_path)
    else:
        conversion_root, manifest_index = None, {}

    manifest_check_payload = build_manifest_artifact_check_report(
        manifest_paths=list(manifest_index.values()),
        export_root=toy_yard_view_root,
        source_workspace_config=Path(args.workspace_config).expanduser().resolve(),
    )
    manifest_check_path = output_root / "packet" / "manifest_artifact_check.json"
    manifest_check_path.parent.mkdir(parents=True, exist_ok=True)
    from aiue_core.schema_utils import write_json  # noqa: PLC0415

    write_json(manifest_check_path, manifest_check_payload)

    solo_candidate = select_solo_candidate(summary_payload, manifest_index) if manifest_index else None
    if not solo_candidate:
        failed_requirements.append(
            make_failed_requirement(
                "t2_solo_candidate_missing",
                "T2A requires a consumer-ready character package resolvable from toy-yard suite summary and manifest index.",
                summary_path=str(summary_path.resolve()) if summary_path else None,
            )
        )
    bundle_candidate = select_bundle_candidate(registry_payload, manifest_index) if manifest_index else None
    if not bundle_candidate:
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_candidate_missing",
                "T2A requires at least one ready pair resolvable from toy-yard registry and manifest index.",
                registry_path=str(registry_path.resolve()) if registry_path else None,
            )
        )
    elif not str(bundle_candidate.get("character_skeletal_mesh") or "").strip() or not str(bundle_candidate.get("weapon_skeletal_mesh") or "").strip():
        failed_requirements.append(
            make_failed_requirement(
                "t2_bundle_runtime_mesh_missing",
                "T2A requires the selected toy-yard ready pair to carry non-empty runtime mesh evidence in registry.",
                bundle_candidate=bundle_candidate,
            )
        )

    per_lane_results: list[dict[str, Any]] = []
    if solo_candidate:
        lane_result, lane_failures = evaluate_solo_lane(workspace, output_root, solo_candidate)
        per_lane_results.append(lane_result)
        failed_requirements.extend(lane_failures)
    if bundle_candidate and summary_path:
        lane_result, lane_failures = evaluate_bundle_lane(workspace, output_root, summary_path, bundle_candidate)
        per_lane_results.append(lane_result)
        failed_requirements.extend(lane_failures)

    counts = {
        "manifest_count": len(manifest_index),
        "solo_lanes_passed": sum(1 for item in per_lane_results if item.get("lane_id") == "solo" and item.get("status") == "pass"),
        "bundle_lanes_passed": sum(1 for item in per_lane_results if item.get("lane_id") == "bundle" and item.get("status") == "pass"),
        "lanes_run": len(per_lane_results),
        "failed_requirements": len(failed_requirements),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "t2_first_full_pass",
    )
    communication_signal = build_communication_signal(
        manifest_check_payload=manifest_check_payload,
        failed_requirements=failed_requirements,
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "generated_at_utc": now_utc(),
            "status": status,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "toy_yard_view_root": str(toy_yard_view_root.resolve()) if toy_yard_view_root else "",
            "resolved_summary_path": str(summary_path.resolve()) if summary_path else "",
            "resolved_registry_path": str(registry_path.resolve()) if registry_path else "",
            "resolved_conversion_root": str(conversion_root.resolve()) if conversion_root else "",
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "lanes": ["solo", "bundle"],
            "selected_inputs": {
                "solo_package_id": str((solo_candidate or {}).get("package_id") or ""),
                "bundle_sample_id": str((bundle_candidate or {}).get("sample_id") or ""),
                "bundle_character_package_id": str((bundle_candidate or {}).get("character_package_id") or ""),
                "bundle_weapon_package_id": str((bundle_candidate or {}).get("weapon_package_id") or ""),
            },
            "counts": counts,
            "per_lane_results": per_lane_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "communication_signal": communication_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "manifest_artifact_check_path": str(manifest_check_path.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
            },
        },
        "aiue_default_source_gate_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_default_source_gate_report",
            notes=["internal_gate_runner", "toy_yard_default_source_confirmation"],
        ),
    )

    report_path = output_root / "toy_yard_default_source_t2_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(f"T2 toy-yard default-source report written to: {report_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
