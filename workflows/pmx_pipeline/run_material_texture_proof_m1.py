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
from run_editor_gate_g1 import REQUIRED_PACKAGE_COUNT, resolve_equipment_report_path, select_target_packages  # noqa: E402
from run_visual_proof_v1 import FIXED_EXECUTION_PROFILE as V1_PROFILE, REQUIRED_SHOTS, evaluate_visual_proof_result  # noqa: E402

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_workspace_config, write_json  # noqa: E402
from aiue_t1.material_proof import (  # noqa: E402
    build_material_report_index,
    resolve_conversion_search_roots,
    resolve_package_material_evidence,
)
from aiue_unreal.host_bridge import run_host_auto_ue_cli  # noqa: E402


GATE_ID = "material_texture_proof_m1"
FIXED_EXECUTION_PROFILE = {
    "host_key": "kernel",
    "mode": "editor_rendered",
    "required_package_count": REQUIRED_PACKAGE_COUNT,
    "required_shot_ids": list(REQUIRED_SHOTS),
    "cell_strategy": "isolated_vertical_cell",
    "cell_origin": dict(V1_PROFILE["cell_origin"]),
    "capture_width": int(V1_PROFILE["capture_width"]),
    "capture_height": int(V1_PROFILE["capture_height"]),
    "capture_delay_seconds": float(V1_PROFILE["capture_delay_seconds"]),
    "subject_min_screen_coverage": float(V1_PROFILE["subject_min_screen_coverage"]),
    "weapon_min_screen_coverage": float(V1_PROFILE["weapon_min_screen_coverage"]),
    "evidence_mode": "import_plus_host_visual",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE M1 material / texture proof gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--equipment-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def _counted_material_slot_match(record: dict[str, Any]) -> bool:
    expected = list(record.get("expected_material_slot_names") or [])
    actual = list(record.get("actual_material_slot_names") or [])
    if not expected:
        return False
    return expected == actual


def evaluate_import_evidence(import_evidence: dict[str, Any], *, package_id: str, label: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    validation = dict(import_evidence.get("validation") or {})
    import_summary = dict(import_evidence.get("import") or {})
    failed_requirements: list[dict[str, Any]] = []
    if not validation:
        failed_requirements.append(
            make_failed_requirement(
                "m1_validation_report_missing",
                "M1 requires a resolved local validation report for each verified package.",
                package_id=package_id,
                package_role=label,
            )
        )
    if not import_summary:
        failed_requirements.append(
            make_failed_requirement(
                "m1_import_report_missing",
                "M1 requires a resolved local import report for each verified package.",
                package_id=package_id,
                package_role=label,
            )
        )
    if validation and str(validation.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "m1_validation_status_not_pass",
                "M1 requires the local validation report to pass.",
                package_id=package_id,
                package_role=label,
                validation_status=validation.get("status"),
                validation_report_path=validation.get("source_path"),
            )
        )
    expected_texture_count = int(validation.get("expected_texture_count") or 0) if validation else 0
    imported_texture_count = int(validation.get("imported_texture_count") or 0) if validation else 0
    if validation and expected_texture_count <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "m1_expected_texture_count_missing",
                "M1 requires validation evidence to report a non-zero expected texture count.",
                package_id=package_id,
                package_role=label,
                expected_texture_count=expected_texture_count,
            )
        )
    if validation and expected_texture_count != imported_texture_count:
        failed_requirements.append(
            make_failed_requirement(
                "m1_texture_count_mismatch",
                "M1 requires imported_texture_count to match expected_texture_count.",
                package_id=package_id,
                package_role=label,
                expected_texture_count=expected_texture_count,
                imported_texture_count=imported_texture_count,
            )
        )
    if validation and not _counted_material_slot_match(validation):
        failed_requirements.append(
            make_failed_requirement(
                "m1_material_slot_names_mismatch",
                "M1 requires validation evidence to confirm material slot names are preserved.",
                package_id=package_id,
                package_role=label,
                expected_material_slot_names=list(validation.get("expected_material_slot_names") or []),
                actual_material_slot_names=list(validation.get("actual_material_slot_names") or []),
            )
        )
    imported_texture_assets = [str(item) for item in list(import_summary.get("imported_texture_assets") or []) if str(item)]
    if import_summary and not imported_texture_assets:
        failed_requirements.append(
            make_failed_requirement(
                "m1_imported_textures_missing",
                "M1 requires the import report to retain imported texture asset references.",
                package_id=package_id,
                package_role=label,
                import_report_path=import_summary.get("source_path"),
            )
        )
    return (
        {
            "package_id": str(validation.get("package_id") or import_summary.get("package_id") or ""),
            "sample_id": str(validation.get("sample_id") or import_summary.get("sample_id") or ""),
            "status": "pass" if not failed_requirements else "fail",
            "validation_report_path": str(validation.get("source_path") or ""),
            "import_report_path": str(import_summary.get("source_path") or validation.get("import_report_path") or ""),
            "validation_status": str(validation.get("status") or ""),
            "import_status": str(import_summary.get("status") or ""),
            "expected_texture_count": expected_texture_count,
            "imported_texture_count": imported_texture_count,
            "expected_material_slot_names": list(validation.get("expected_material_slot_names") or []),
            "actual_material_slot_names": list(validation.get("actual_material_slot_names") or []),
            "material_slot_names_match": _counted_material_slot_match(validation) if validation else False,
            "imported_texture_assets": imported_texture_assets,
            "warnings": list(validation.get("warnings") or []) + list(import_summary.get("warnings") or []),
        },
        failed_requirements,
    )


def evaluate_host_material_evidence(visual_summary: dict[str, Any], *, package_id: str) -> list[dict[str, Any]]:
    failed_requirements: list[dict[str, Any]] = []
    material_evidence = dict(visual_summary.get("material_evidence") or {})
    main_mesh = dict(material_evidence.get("main_mesh") or {})
    weapon_mesh = dict(material_evidence.get("weapon_mesh") or {})
    if int(main_mesh.get("material_slot_count") or 0) <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "m1_main_mesh_material_slots_missing",
                "M1 requires the spawned character mesh to expose material slots in host visual evidence.",
                package_id=package_id,
                material_evidence=main_mesh,
            )
        )
    if not [path for path in list(main_mesh.get("material_asset_paths") or []) if str(path)]:
        failed_requirements.append(
            make_failed_requirement(
                "m1_main_mesh_material_assets_missing",
                "M1 requires the spawned character mesh to expose non-empty material asset paths.",
                package_id=package_id,
                material_evidence=main_mesh,
            )
        )
    if int(weapon_mesh.get("material_slot_count") or 0) <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "m1_weapon_material_slots_missing",
                "M1 requires the spawned default weapon mesh to expose material slots in host visual evidence.",
                package_id=package_id,
                material_evidence=weapon_mesh,
            )
        )
    if not [path for path in list(weapon_mesh.get("material_asset_paths") or []) if str(path)]:
        failed_requirements.append(
            make_failed_requirement(
                "m1_weapon_material_assets_missing",
                "M1 requires the spawned default weapon mesh to expose non-empty material asset paths.",
                package_id=package_id,
                material_evidence=weapon_mesh,
            )
        )
    return failed_requirements


def build_visual_request(package: dict[str, Any], output_root: Path) -> dict[str, Any]:
    return {
        "package_id": package["package_id"],
        "sample_id": package["sample_id"],
        "host_blueprint_asset_path": package["host_blueprint_asset"],
        "runtime_ready_only": True,
        "output_root": str(output_root.resolve()),
        "cell_origin": dict(FIXED_EXECUTION_PROFILE["cell_origin"]),
        "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
        "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
        "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
        "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
        "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
        "requested_shot_ids": list(FIXED_EXECUTION_PROFILE["required_shot_ids"]),
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    equipment_report_path = resolve_equipment_report_path(workspace, args.equipment_report_path)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = None
    previous_report_path = latest_report_path if latest_report_path.exists() else None
    if latest_report_path.exists():
        from aiue_core.schema_utils import load_json  # local import to keep file top tidy

        previous_report = load_json(latest_report_path)
    from aiue_core.schema_utils import load_json  # noqa: PLC0415

    equipment_report = load_json(equipment_report_path)
    selected_packages = select_target_packages(equipment_report)
    failed_requirements: list[dict[str, Any]] = []
    if len(selected_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "m1_required_package_count",
                "M1 requires exactly two runtime-ready packages with ready weapon pairs.",
                expected=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                actual=len(selected_packages),
                resolved_package_ids=[str(item.get("package_id") or "") for item in selected_packages],
            )
        )

    search_roots = resolve_conversion_search_roots(workspace, equipment_report, equipment_report_path)
    material_report_index = build_material_report_index(search_roots)
    per_package_results: list[dict[str, Any]] = []
    for package in selected_packages:
        package_id = str(package.get("package_id") or "")
        sample_id = str(package.get("sample_id") or "")
        package_failures: list[dict[str, Any]] = []

        character_evidence_payload = resolve_package_material_evidence(
            material_report_index,
            package_id=package_id,
            sample_id=sample_id,
        )
        weapon_evidence_payload = resolve_package_material_evidence(
            material_report_index,
            package_id=str(package.get("default_weapon_package_id") or ""),
            sample_id=sample_id,
        )
        character_import_evidence, character_failures = evaluate_import_evidence(
            character_evidence_payload,
            package_id=package_id,
            label="character",
        )
        weapon_import_evidence, weapon_failures = evaluate_import_evidence(
            weapon_evidence_payload,
            package_id=package_id,
            label="default_weapon",
        )
        package_failures.extend(character_failures)
        package_failures.extend(weapon_failures)

        host_visual_result = {}
        host_visual_summary = {"status": "fail", "shots": [], "material_evidence": {}}
        visual_output_path = output_root / "host_visual" / f"{package_id}_inspect_host_visual.json"
        try:
            host_visual_run = run_host_auto_ue_cli(
                workspace,
                mode=str(FIXED_EXECUTION_PROFILE["mode"]),
                command="inspect-host-visual",
                params=build_visual_request(package, output_root / "captures" / package_id),
                output_path=str(visual_output_path),
                host_key="kernel",
            )
            host_visual_result = dict((host_visual_run.get("payload") or {}).get("result") or {})
            host_visual_summary, visual_failures = evaluate_visual_proof_result(host_visual_result, output_root)
            host_visual_summary["material_evidence"] = dict(host_visual_result.get("material_evidence") or {})
            package_failures.extend(visual_failures)
            package_failures.extend(evaluate_host_material_evidence(host_visual_summary, package_id=package_id))
        except Exception as exc:
            package_failures.append(
                make_failed_requirement(
                    "m1_host_visual_execution_failed",
                    "M1 requires inspect-host-visual to execute successfully on the kernel host.",
                    package_id=package_id,
                    error=str(exc),
                    output_path=str(visual_output_path.resolve()),
                )
            )

        per_package_results.append(
            {
                "package_id": package_id,
                "sample_id": sample_id,
                "host_blueprint_asset": str(package.get("host_blueprint_asset") or ""),
                "default_weapon_package_id": str(package.get("default_weapon_package_id") or ""),
                "status": "pass" if not package_failures else "fail",
                "import_evidence": {
                    "character": character_import_evidence,
                    "default_weapon": weapon_import_evidence,
                },
                "host_visual_evidence": host_visual_summary,
                "failed_requirements": package_failures,
                "artifacts": {
                    "host_visual_result_path": str(visual_output_path.resolve()),
                },
            }
        )
        failed_requirements.extend(package_failures)

    counts = {
        "required_package_count": int(FIXED_EXECUTION_PROFILE["required_package_count"]),
        "resolved_package_count": len(selected_packages),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "character_texture_sets_passed": sum(
            1
            for item in per_package_results
            if str(dict((item.get("import_evidence") or {}).get("character") or {}).get("status") or "") == "pass"
        ),
        "weapon_texture_sets_passed": sum(
            1
            for item in per_package_results
            if str(dict((item.get("import_evidence") or {}).get("default_weapon") or {}).get("status") or "") == "pass"
        ),
        "host_visual_packages_passed": sum(
            1
            for item in per_package_results
            if str(dict(item.get("host_visual_evidence") or {}).get("status") or "") == "pass"
        ),
    }
    discussion_signal = build_discussion_signal(
        "pass" if not failed_requirements else "fail",
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_material_texture_proof_m1_pass",
    )
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": "pass" if not failed_requirements else "fail",
            "success": not failed_requirements,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "equipment_report_path": str(equipment_report_path.resolve()),
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
        "aiue_material_texture_proof_m1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_material_texture_proof_m1_report",
            notes=[
                "internal_m1_material_texture_proof",
                "dual_evidence_import_plus_host_visual",
                "kernel_host_validation_authority",
            ],
        ),
    )
    report_path = output_root / "material_texture_proof_m1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if not failed_requirements else 1


if __name__ == "__main__":
    raise SystemExit(main())
