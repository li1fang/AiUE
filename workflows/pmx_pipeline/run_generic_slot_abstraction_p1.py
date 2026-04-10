from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "generic_slot_abstraction_p1"
DEFAULT_STATIC_MESH_FIXTURES = [
    "/Game/Levels/LevelPrototyping/Meshes/SM_Cube",
    "/Game/Levels/LevelPrototyping/Meshes/SM_Cylinder",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE P1 generic slot abstraction gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--static-mesh-fixture", action="append", default=[])
    return parser.parse_args()


def resolve_report_path(explicit_path: str | None, fallback_path: Path, missing_message: str) -> Path:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    raise FileNotFoundError(missing_message)


def default_latest_d1_report_path(workspace: dict) -> Path:
    return Path(workspace["paths"]["aiue_repo_root"]).expanduser().resolve() / "Saved" / "verification" / "latest_demo_stage_d1_onboarding_report.json"


def normalize_asset_path(asset_path: str | None) -> str:
    text = str(asset_path or "").strip()
    if not text:
        return ""
    if "." not in text:
        return text
    package_path, object_name = text.rsplit(".", 1)
    leaf_name = package_path.rsplit("/", 1)[-1]
    if object_name == leaf_name:
        return package_path
    return text


def ready_demo_packages(d1_report: dict) -> list[dict]:
    results = []
    for entry in ((((d1_report.get("scene_sweep") or {}).get("result") or {}).get("package_results") or [])):
        if entry.get("status") != "pass":
            continue
        if not entry.get("package_id") or not entry.get("host_blueprint_asset_path"):
            continue
        results.append(
            {
                "package_id": str(entry.get("package_id") or ""),
                "sample_id": str(entry.get("sample_id") or ""),
                "host_blueprint_asset_path": str(entry.get("host_blueprint_asset_path") or ""),
            }
        )
    return sorted(results, key=lambda item: item["package_id"])


def build_registry(workspace: dict, output_root: Path, host_key: str) -> tuple[dict, Path]:
    report_path = output_root / "build_registry" / "ue_equipment_assets_report.p1.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    host_payload = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode="editor_rendered",
        command="build-equipment-registry",
        params={
            "conversion_root": workspace["paths"]["conversion_root"],
            "asset_root": "/Game/PMXPipeline",
            "report_path": str(report_path.resolve()),
        },
        output_path=str((output_root / "build_registry" / "build_equipment_registry_result.json").resolve()),
        host_key=host_key,
    )
    result = dict((host_payload.get("payload") or {}).get("result") or {})
    return result, report_path


def inspect_weapon_slot(workspace: dict, output_root: Path, host_key: str, package: dict, level_path: str | None) -> tuple[dict, Path]:
    result_path = output_root / "weapon_slot_checks" / f"{package['package_id']}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    host_payload = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode="editor_rendered",
        command="inspect-slot-runtime",
        params={
            "package_id": package["package_id"],
            "sample_id": package["sample_id"],
            "host_blueprint_asset_path": package["host_blueprint_asset_path"],
            "level_path": level_path,
            "required_slots": ["weapon"],
        },
        output_path=str(result_path.resolve()),
        host_key=host_key,
    )
    return dict((host_payload.get("payload") or {}).get("result") or {}), result_path


def inspect_static_smoke(workspace: dict, output_root: Path, host_key: str, package: dict, level_path: str | None, fixtures: list[str]) -> tuple[dict, Path]:
    result_path = output_root / "static_smoke" / "inspect_slot_runtime_static.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    override_bindings = [
        {
            "slot_name": "p1_fixture",
            "item_package_id": "fixture_cube",
            "item_kind": "static_mesh",
            "attach_socket_name": "WeaponSocket",
            "static_mesh_asset": fixtures[0],
            "consumer_ready": True,
        },
        {
            "slot_name": "p1_fixture",
            "item_package_id": "fixture_cylinder",
            "item_kind": "static_mesh",
            "attach_socket_name": "WeaponSocket",
            "static_mesh_asset": fixtures[1],
            "consumer_ready": True,
        },
    ]
    host_payload = run_host_auto_ue_cli(
        workspace_or_config=workspace,
        mode="editor_rendered",
        command="inspect-slot-runtime",
        params={
            "package_id": package["package_id"],
            "sample_id": package["sample_id"],
            "host_blueprint_asset_path": package["host_blueprint_asset_path"],
            "level_path": level_path,
            "required_slots": ["weapon", "p1_fixture"],
            "slot_binding_overrides": override_bindings,
        },
        output_path=str(result_path.resolve()),
        host_key=host_key,
    )
    return dict((host_payload.get("payload") or {}).get("result") or {}), result_path


def evaluate_weapon_slot_result(result: dict, result_path: Path) -> tuple[dict, list[dict]]:
    failed_requirements = []
    slot_bindings = list(result.get("slot_bindings") or [])
    managed_components_by_slot = dict(result.get("managed_components_by_slot") or {})
    weapon_binding = next((binding for binding in slot_bindings if binding.get("slot_name") == "weapon"), {})
    weapon_component = dict(managed_components_by_slot.get("weapon") or {})
    if result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "weapon_slot_runtime_failed",
                "Generic slot runtime inspection did not pass for a ready weapon bundle.",
                result_path=str(result_path.resolve()),
                errors=list(result.get("errors") or []),
            )
        )
    if weapon_binding.get("item_kind") != "skeletal_mesh":
        failed_requirements.append(
            make_failed_requirement(
                "weapon_slot_not_skeletal",
                "Ready weapon slot did not resolve to skeletal_mesh in the generic slot path.",
                result_path=str(result_path.resolve()),
                weapon_binding=weapon_binding,
            )
        )
    if not weapon_binding.get("asset_path"):
        failed_requirements.append(
            make_failed_requirement(
                "weapon_slot_binding_missing_asset",
                "Ready weapon slot binding is missing an asset path.",
                result_path=str(result_path.resolve()),
            )
        )
    if not weapon_component.get("component_name"):
        failed_requirements.append(
            make_failed_requirement(
                "weapon_slot_component_missing",
                "Ready weapon slot did not create or resolve a managed component.",
                result_path=str(result_path.resolve()),
            )
        )
    return (
        {
            "package_id": result.get("package_id"),
            "sample_id": result.get("sample_id"),
            "status": "pass" if not failed_requirements else "fail",
            "host_blueprint_asset": result.get("host_blueprint_asset"),
            "weapon_binding": weapon_binding,
            "weapon_component": weapon_component,
            "slot_conflicts": list(result.get("slot_conflicts") or []),
            "artifacts": {
                "result_path": str(result_path.resolve()),
            },
        },
        failed_requirements,
    )


def evaluate_static_smoke_result(result: dict, result_path: Path, fixtures: list[str]) -> tuple[dict, list[dict]]:
    failed_requirements = []
    slot_bindings = list(result.get("slot_bindings") or [])
    slot_conflicts = list(result.get("slot_conflicts") or [])
    managed_components_by_slot = dict(result.get("managed_components_by_slot") or {})
    fixture_binding = next((binding for binding in slot_bindings if binding.get("slot_name") == "p1_fixture"), {})
    fixture_component = dict(managed_components_by_slot.get("p1_fixture") or {})
    expected_asset_path = normalize_asset_path(fixtures[1])
    actual_binding_asset_path = normalize_asset_path(fixture_binding.get("asset_path"))
    actual_component_asset_path = normalize_asset_path(fixture_component.get("asset_path"))

    if result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "static_slot_runtime_failed",
                "The static mesh slot smoke test did not pass.",
                result_path=str(result_path.resolve()),
                errors=list(result.get("errors") or []),
            )
        )
    if fixture_binding.get("item_kind") != "static_mesh":
        failed_requirements.append(
            make_failed_requirement(
                "static_slot_wrong_item_kind",
                "The static smoke slot did not resolve to static_mesh.",
                result_path=str(result_path.resolve()),
                fixture_binding=fixture_binding,
            )
        )
    if actual_binding_asset_path != expected_asset_path:
        failed_requirements.append(
            make_failed_requirement(
                "static_slot_override_not_applied",
                "The static smoke slot did not keep the latest override binding.",
                result_path=str(result_path.resolve()),
                expected_asset_path=expected_asset_path,
                actual_asset_path=fixture_binding.get("asset_path"),
            )
        )
    if actual_component_asset_path != expected_asset_path:
        failed_requirements.append(
            make_failed_requirement(
                "static_slot_component_wrong_asset",
                "The managed static slot component did not resolve to the latest override asset.",
                result_path=str(result_path.resolve()),
                expected_asset_path=expected_asset_path,
                actual_asset_path=fixture_component.get("asset_path"),
            )
        )
    if not any(conflict.get("slot_name") == "p1_fixture" and conflict.get("resolution") == "override_latest" for conflict in slot_conflicts):
        failed_requirements.append(
            make_failed_requirement(
                "static_slot_conflict_missing",
                "The latest-override conflict evidence for the static slot smoke test is missing.",
                result_path=str(result_path.resolve()),
                slot_conflicts=slot_conflicts,
            )
        )
    return (
        {
            "status": "pass" if not failed_requirements else "fail",
            "slot_binding": fixture_binding,
            "managed_component": fixture_component,
            "slot_conflicts": slot_conflicts,
            "artifacts": {
                "result_path": str(result_path.resolve()),
            },
        },
        failed_requirements,
    )


def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    d1_report_path = resolve_report_path(
        args.d1_report_path,
        default_latest_d1_report_path(workspace),
        "No latest_demo_stage_d1_onboarding_report.json could be resolved for P1.",
    )
    d1_report = load_json(d1_report_path)
    host_key = str(d1_report.get("host_key") or "demo")
    level_path = str(d1_report.get("level_path") or "/Game/Levels/DefaultLevel")
    packages = ready_demo_packages(d1_report)
    if len(packages) != 2:
        failed_requirements.append(
            make_failed_requirement(
                "ready_package_count",
                "P1 requires exactly two ready demo packages from D1 onboarding.",
                expected=2,
                actual=len(packages),
                d1_report_path=str(d1_report_path.resolve()),
            )
        )

    fixtures = list(args.static_mesh_fixture or [])
    if not fixtures:
        fixtures = list(DEFAULT_STATIC_MESH_FIXTURES)
    if len(fixtures) < 2:
        failed_requirements.append(
            make_failed_requirement(
                "static_fixture_count",
                "P1 requires two static mesh fixtures so the latest override behavior can be verified.",
                fixtures=fixtures,
            )
        )

    build_registry_result = {}
    build_registry_report_path = None
    if not failed_requirements:
        try:
            build_registry_result, build_registry_report_path = build_registry(workspace, output_root, host_key=host_key)
        except Exception as exc:
            failed_requirements.append(
                make_failed_requirement(
                    "build_registry_failed",
                    "P1 could not rebuild the demo host registry on the generic slot runtime.",
                    error=str(exc),
                )
            )

    build_registry_counts = dict(build_registry_result.get("counts") or {})
    if build_registry_result and int(build_registry_counts.get("slot_binding_refs") or 0) <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "slot_binding_refs_missing",
                "The rebuilt registry report did not record any slot binding refs.",
                build_registry_counts=build_registry_counts,
                report_path=str(build_registry_report_path.resolve()) if build_registry_report_path else None,
            )
        )

    weapon_slot_checks = []
    if not failed_requirements:
        for package in packages:
            try:
                result, result_path = inspect_weapon_slot(workspace, output_root, host_key, package, level_path)
                evaluated, failures = evaluate_weapon_slot_result(result, result_path)
                weapon_slot_checks.append(evaluated)
                failed_requirements.extend(failures)
            except Exception as exc:
                failed_requirements.append(
                    make_failed_requirement(
                        "weapon_slot_inspection_failed",
                        "P1 failed to inspect a ready weapon slot through the generic path.",
                        package_id=package.get("package_id"),
                        error=str(exc),
                    )
                )

    static_smoke_result = {}
    if not failed_requirements and packages:
        try:
            raw_static_result, static_result_path = inspect_static_smoke(workspace, output_root, host_key, packages[0], level_path, fixtures[:2])
            static_smoke_result, failures = evaluate_static_smoke_result(raw_static_result, static_result_path, fixtures[:2])
            failed_requirements.extend(failures)
        except Exception as exc:
            failed_requirements.append(
                make_failed_requirement(
                    "static_slot_smoke_failed",
                    "P1 failed while running the static mesh slot smoke test.",
                    error=str(exc),
                )
            )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "p1_first_complete_pass")
    counts = {
        "required_ready_packages": 2,
        "resolved_ready_packages": len(packages),
        "weapon_slot_checks": len(weapon_slot_checks),
        "passing_weapon_slot_checks": sum(1 for item in weapon_slot_checks if item.get("status") == "pass"),
        "static_smoke_checks": 1 if static_smoke_result else 0,
        "passing_static_smoke_checks": 1 if static_smoke_result and static_smoke_result.get("status") == "pass" else 0,
        "slot_binding_refs": int(build_registry_counts.get("slot_binding_refs") or 0),
    }

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": host_key,
            "level_path": level_path,
            "fixed_execution_profile": {
                "host_key": host_key,
                "mode": "editor_rendered",
                "static_mesh_fixtures": fixtures[:2],
                "slot_conflict_policy": "override_latest",
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": [package.get("package_id") for package in packages],
            "build_registry": {
                "status": build_registry_result.get("status"),
                "report_path": str(build_registry_report_path.resolve()) if build_registry_report_path else None,
                "counts": build_registry_counts,
                "warnings": list(build_registry_result.get("warnings") or []),
                "errors": list(build_registry_result.get("errors") or []),
            },
            "weapon_slot_checks": weapon_slot_checks,
            "static_slot_smoke": static_smoke_result,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d1_report_path": str(d1_report_path.resolve()),
            },
        },
        schema_family="aiue_generic_slot_abstraction_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_generic_slot_abstraction_report",
            notes=["internal_p1_gate", "generic_slot_runtime_only"],
        ),
    )
    report_path = output_root / "p1_generic_slot_abstraction_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
