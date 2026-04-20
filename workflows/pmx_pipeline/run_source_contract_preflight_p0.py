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
from run_editor_gate_g1 import REQUIRED_PACKAGE_COUNT, resolve_equipment_report_path, resolve_summary_path, select_target_packages  # noqa: E402

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402
from aiue_t1.material_proof import (  # noqa: E402
    build_material_report_index,
    resolve_conversion_search_roots,
    resolve_package_material_evidence,
)


GATE_ID = "source_contract_preflight_p0"
FIXED_EXECUTION_PROFILE = {
    "required_package_count": REQUIRED_PACKAGE_COUNT,
    "scope": "import_validation_registry_contract_only",
    "checks": [
        "import_report_presence",
        "validation_report_presence",
        "manifest_presence",
        "material_slot_name_alignment",
        "texture_count_alignment",
        "mesh_destination_presence",
        "source_to_ue_artifact_completeness",
        "package_registry_consistency",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE P0 source contract preflight gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--summary-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def _existing_path(path_text: str | None) -> str:
    candidate = Path(str(path_text or "")).expanduser()
    return str(candidate.resolve()) if str(path_text or "").strip() and candidate.exists() else ""


def _non_empty_list(values: list[Any] | None) -> list[str]:
    return [str(item) for item in list(values or []) if str(item)]


def evaluate_source_evidence(
    import_evidence: dict[str, Any],
    *,
    expected_package_id: str,
    expected_sample_id: str,
    package_id: str,
    role: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validation = dict(import_evidence.get("validation") or {})
    import_summary = dict(import_evidence.get("import") or {})
    failed_requirements: list[dict[str, Any]] = []

    if not validation:
        failed_requirements.append(
            make_failed_requirement(
                "p0_validation_report_missing",
                "P0 requires a resolved validation report for every source package.",
                package_id=package_id,
                package_role=role,
                expected_package_id=expected_package_id,
            )
        )
    if not import_summary:
        failed_requirements.append(
            make_failed_requirement(
                "p0_import_report_missing",
                "P0 requires a resolved import report for every source package.",
                package_id=package_id,
                package_role=role,
                expected_package_id=expected_package_id,
            )
        )

    validation_status = str(validation.get("status") or "")
    import_status = str(import_summary.get("status") or "")
    if validation and validation_status != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "p0_validation_status_not_pass",
                "P0 requires the validation report to pass.",
                package_id=package_id,
                package_role=role,
                validation_status=validation_status,
                validation_report_path=str(validation.get("source_path") or ""),
            )
        )
    if import_summary and import_status and import_status not in {"pass", "success", "unknown"}:
        failed_requirements.append(
            make_failed_requirement(
                "p0_import_status_not_pass",
                "P0 requires the import report to complete successfully.",
                package_id=package_id,
                package_role=role,
                import_status=import_status,
                import_report_path=str(import_summary.get("source_path") or ""),
            )
        )

    if validation and str(validation.get("package_id") or "") != expected_package_id:
        failed_requirements.append(
            make_failed_requirement(
                "p0_validation_package_id_mismatch",
                "P0 requires validation package identity to match the selected package.",
                package_id=package_id,
                package_role=role,
                expected_package_id=expected_package_id,
                actual_package_id=str(validation.get("package_id") or ""),
            )
        )
    if import_summary and str(import_summary.get("package_id") or "") != expected_package_id:
        failed_requirements.append(
            make_failed_requirement(
                "p0_import_package_id_mismatch",
                "P0 requires import package identity to match the selected package.",
                package_id=package_id,
                package_role=role,
                expected_package_id=expected_package_id,
                actual_package_id=str(import_summary.get("package_id") or ""),
            )
        )

    if validation and expected_sample_id and str(validation.get("sample_id") or "") not in {"", expected_sample_id}:
        failed_requirements.append(
            make_failed_requirement(
                "p0_validation_sample_id_mismatch",
                "P0 requires validation sample identity to match the selected package sample.",
                package_id=package_id,
                package_role=role,
                expected_sample_id=expected_sample_id,
                actual_sample_id=str(validation.get("sample_id") or ""),
            )
        )
    if import_summary and expected_sample_id and str(import_summary.get("sample_id") or "") not in {"", expected_sample_id}:
        failed_requirements.append(
            make_failed_requirement(
                "p0_import_sample_id_mismatch",
                "P0 requires import sample identity to match the selected package sample.",
                package_id=package_id,
                package_role=role,
                expected_sample_id=expected_sample_id,
                actual_sample_id=str(import_summary.get("sample_id") or ""),
            )
        )

    expected_texture_count = int(validation.get("expected_texture_count") or 0) if validation else 0
    imported_texture_count = int(validation.get("imported_texture_count") or 0) if validation else 0
    if validation and expected_texture_count <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "p0_expected_texture_count_missing",
                "P0 requires a non-zero expected texture count in validation evidence.",
                package_id=package_id,
                package_role=role,
                expected_texture_count=expected_texture_count,
            )
        )
    if validation and expected_texture_count != imported_texture_count:
        failed_requirements.append(
            make_failed_requirement(
                "p0_texture_count_mismatch",
                "P0 requires imported_texture_count to match expected_texture_count.",
                package_id=package_id,
                package_role=role,
                expected_texture_count=expected_texture_count,
                imported_texture_count=imported_texture_count,
            )
        )

    expected_material_slot_names = _non_empty_list(validation.get("expected_material_slot_names"))
    actual_material_slot_names = _non_empty_list(validation.get("actual_material_slot_names"))
    if not expected_material_slot_names:
        failed_requirements.append(
            make_failed_requirement(
                "p0_expected_material_slots_missing",
                "P0 requires expected material slot names in validation evidence.",
                package_id=package_id,
                package_role=role,
            )
        )
    if expected_material_slot_names != actual_material_slot_names:
        failed_requirements.append(
            make_failed_requirement(
                "p0_material_slot_names_mismatch",
                "P0 requires actual material slot names to match expected slot names.",
                package_id=package_id,
                package_role=role,
                expected_material_slot_names=expected_material_slot_names,
                actual_material_slot_names=actual_material_slot_names,
            )
        )

    manifest_path = _existing_path(import_summary.get("manifest_path"))
    if import_summary and not manifest_path:
        failed_requirements.append(
            make_failed_requirement(
                "p0_manifest_missing",
                "P0 requires the import report to retain a readable manifest path.",
                package_id=package_id,
                package_role=role,
                manifest_path=str(import_summary.get("manifest_path") or ""),
            )
        )

    mesh_destination = str(import_summary.get("mesh_destination") or "")
    if import_summary and not mesh_destination:
        failed_requirements.append(
            make_failed_requirement(
                "p0_mesh_destination_missing",
                "P0 requires the import report to retain a mesh destination path.",
                package_id=package_id,
                package_role=role,
            )
        )

    imported_texture_assets = _non_empty_list(import_summary.get("imported_texture_assets"))
    if import_summary and not imported_texture_assets:
        failed_requirements.append(
            make_failed_requirement(
                "p0_imported_texture_assets_missing",
                "P0 requires the import report to retain imported texture asset references.",
                package_id=package_id,
                package_role=role,
            )
        )

    validation_report_path = _existing_path(validation.get("source_path"))
    import_report_path = _existing_path(import_summary.get("source_path"))
    if validation and not validation_report_path:
        failed_requirements.append(
            make_failed_requirement(
                "p0_validation_artifact_missing",
                "P0 requires the validation report artifact to exist on disk.",
                package_id=package_id,
                package_role=role,
            )
        )
    if import_summary and not import_report_path:
        failed_requirements.append(
            make_failed_requirement(
                "p0_import_artifact_missing",
                "P0 requires the import report artifact to exist on disk.",
                package_id=package_id,
                package_role=role,
            )
        )

    return (
        {
            "expected_package_id": expected_package_id,
            "expected_sample_id": expected_sample_id,
            "status": "pass" if not failed_requirements else "fail",
            "validation_status": validation_status,
            "import_status": import_status,
            "validation_report_path": validation_report_path,
            "import_report_path": import_report_path,
            "manifest_path": manifest_path,
            "mesh_destination": mesh_destination,
            "texture_destination": str(import_summary.get("texture_destination") or ""),
            "expected_texture_count": expected_texture_count,
            "imported_texture_count": imported_texture_count,
            "expected_material_slot_names": expected_material_slot_names,
            "actual_material_slot_names": actual_material_slot_names,
            "imported_texture_assets": imported_texture_assets,
        },
        failed_requirements,
    )


def summary_package_presence(summary_payload: dict[str, Any], package_id: str) -> bool:
    saw_known_collection = False
    for collection_key in (
        "ready_character_entries",
        "ready_weapon_entries",
        "character_entries",
        "weapon_entries",
        "entries",
        "packages",
    ):
        entries = list(summary_payload.get(collection_key) or [])
        if entries:
            saw_known_collection = True
        for entry in entries:
            if str((dict(entry or {})).get("package_id") or "") == package_id:
                return True
    return not saw_known_collection


def evaluate_package_contract(
    package: dict[str, Any],
    *,
    summary_payload: dict[str, Any],
    material_report_index: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    package_id = str(package.get("package_id") or "")
    sample_id = str(package.get("sample_id") or "")
    default_weapon_package_id = str(package.get("default_weapon_package_id") or "")
    failed_requirements: list[dict[str, Any]] = []

    character_evidence, character_failures = evaluate_source_evidence(
        resolve_package_material_evidence(
            material_report_index,
            package_id=package_id,
            sample_id=sample_id,
        ),
        expected_package_id=package_id,
        expected_sample_id=sample_id,
        package_id=package_id,
        role="character",
    )
    weapon_evidence, weapon_failures = evaluate_source_evidence(
        resolve_package_material_evidence(
            material_report_index,
            package_id=default_weapon_package_id,
            sample_id=sample_id,
        ),
        expected_package_id=default_weapon_package_id,
        expected_sample_id=sample_id,
        package_id=package_id,
        role="default_weapon",
    )
    failed_requirements.extend(character_failures)
    failed_requirements.extend(weapon_failures)

    if not summary_package_presence(summary_payload, package_id):
        failed_requirements.append(
            make_failed_requirement(
                "p0_character_missing_from_summary",
                "P0 requires the selected character package to appear in the resolved summary contract.",
                package_id=package_id,
                summary_path=str(summary_payload.get("_source_path") or ""),
            )
        )
    if not summary_package_presence(summary_payload, default_weapon_package_id):
        failed_requirements.append(
            make_failed_requirement(
                "p0_weapon_missing_from_summary",
                "P0 requires the selected default weapon package to appear in the resolved summary contract.",
                package_id=package_id,
                default_weapon_package_id=default_weapon_package_id,
                summary_path=str(summary_payload.get("_source_path") or ""),
            )
        )

    return (
        {
            "package_id": package_id,
            "sample_id": sample_id,
            "default_weapon_package_id": default_weapon_package_id,
            "host_blueprint_asset": str(package.get("host_blueprint_asset") or ""),
            "status": "pass" if not failed_requirements else "fail",
            "source_contract": {
                "character": character_evidence,
                "default_weapon": weapon_evidence,
            },
            "failed_requirements": failed_requirements,
        },
        failed_requirements,
    )


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)

    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    equipment_report = load_json(equipment_report_path)
    summary_path = resolve_summary_path(workspace, equipment_report_path, equipment_report, args.summary_path)
    summary_payload = dict(load_json(summary_path) or {})
    summary_payload["_source_path"] = str(summary_path.resolve())
    selected_packages = select_target_packages(equipment_report)
    failed_requirements: list[dict[str, Any]] = []
    if len(selected_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "p0_required_package_count",
                "P0 requires exactly two runtime-ready packages with ready weapon pairs.",
                expected=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                actual=len(selected_packages),
                resolved_package_ids=[str(item.get("package_id") or "") for item in selected_packages],
            )
        )

    search_roots = resolve_conversion_search_roots(workspace, equipment_report, equipment_report_path)
    material_report_index = build_material_report_index(search_roots)
    per_package_results: list[dict[str, Any]] = []
    for package in selected_packages:
        package_result, package_failures = evaluate_package_contract(
            package,
            summary_payload=summary_payload,
            material_report_index=material_report_index,
        )
        per_package_results.append(package_result)
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(selected_packages),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "character_contracts_passed": sum(
            1
            for item in per_package_results
            if str(dict(((item.get("source_contract") or {}).get("character") or {})).get("status") or "") == "pass"
        ),
        "weapon_contracts_passed": sum(
            1
            for item in per_package_results
            if str(dict(((item.get("source_contract") or {}).get("default_weapon") or {})).get("status") or "") == "pass"
        ),
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_source_contract_preflight_p0_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "equipment_report_path": str(equipment_report_path.resolve()),
            "summary_path": str(summary_path.resolve()),
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "resolved_package_ids": [str(item.get("package_id") or "") for item in selected_packages],
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "latest_report_path": str(latest_report_path.resolve()),
                "search_roots": list(material_report_index.get("search_roots") or []),
                "scan_errors": list(material_report_index.get("scan_errors") or []),
            },
        },
        schema_family="aiue_source_contract_preflight_p0_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_source_contract_preflight_p0_report",
            notes=[
                "internal_source_contract_preflight",
                "import_validation_registry_contract_only",
                "no_deep_geometry_checks",
            ],
        ),
    )
    report_path = output_root / "source_contract_preflight_p0_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
