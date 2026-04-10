from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, write_report_pair

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config
from aiue_unreal.host_bridge import run_host_auto_ue_cli

GATE_ID = "clothing_vertical_slice_p2"
DEFAULT_CLOTHING_FIXTURE_ASSET = "/Game/Characters/Echo/Meshes/SKM_Echo_Hair.SKM_Echo_Hair"
DEFAULT_CLOTHING_SLOT_NAME = "clothing"
DEFAULT_CLOTHING_ATTACH_SOCKET = "Head"
DEFAULT_TRACKED_CLOTHING_MIN_COVERAGE = 0.001


def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE P2 clothing vertical slice gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--clothing-asset-path", default=DEFAULT_CLOTHING_FIXTURE_ASSET)
    parser.add_argument("--clothing-slot-name", default=DEFAULT_CLOTHING_SLOT_NAME)
    parser.add_argument("--attach-socket-name", default=DEFAULT_CLOTHING_ATTACH_SOCKET)
    parser.add_argument("--tracked-clothing-min-coverage", type=float, default=DEFAULT_TRACKED_CLOTHING_MIN_COVERAGE)
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


def clothing_binding(slot_name: str, attach_socket_name: str, clothing_asset_path: str) -> dict:
    return {
        "slot_name": str(slot_name or DEFAULT_CLOTHING_SLOT_NAME),
        "item_package_id": "p2_echo_hair_fixture",
        "item_kind": "skeletal_mesh",
        "attach_socket_name": str(attach_socket_name or DEFAULT_CLOTHING_ATTACH_SOCKET),
        "skeletal_mesh_asset": str(clothing_asset_path or DEFAULT_CLOTHING_FIXTURE_ASSET),
        "consumer_ready": True,
    }


def inspect_runtime(
    workspace: dict,
    output_root: Path,
    host_key: str,
    package: dict,
    level_path: str,
    binding: dict,
) -> tuple[dict, Path]:
    result_path = output_root / "runtime_checks" / f"{package['package_id']}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        host_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode="editor_rendered",
            command="inspect-slot-runtime",
            params={
                "package_id": package["package_id"],
                "sample_id": package["sample_id"],
                "host_blueprint_asset_path": package["host_blueprint_asset_path"],
                "level_path": level_path,
                "required_slots": ["weapon", binding["slot_name"]],
                "slot_binding_overrides": [binding],
            },
            output_path=str(result_path.resolve()),
            host_key=host_key,
        )
        return dict((host_payload.get("payload") or {}).get("result") or {}), result_path
    except Exception:
        if result_path.exists():
            return dict((load_json(result_path).get("result") or {})), result_path
        raise


def inspect_visual(
    workspace: dict,
    output_root: Path,
    host_key: str,
    package: dict,
    level_path: str,
    binding: dict,
) -> tuple[dict, Path]:
    result_path = output_root / "visual_checks" / f"{package['package_id']}.json"
    capture_root = output_root / "visual_checks" / package["package_id"] / "captures"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    capture_root.mkdir(parents=True, exist_ok=True)
    try:
        host_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode="editor_rendered",
            command="inspect-host-visual",
            params={
                "package_id": package["package_id"],
                "sample_id": package["sample_id"],
                "host_blueprint_asset_path": package["host_blueprint_asset_path"],
                "level_path": level_path,
                "output_root": str(capture_root.resolve()),
                "slot_binding_overrides": [binding],
                "tracked_slots": [binding["slot_name"]],
            },
            output_path=str(result_path.resolve()),
            host_key=host_key,
        )
        return dict((host_payload.get("payload") or {}).get("result") or {}), result_path
    except Exception:
        if result_path.exists():
            return dict((load_json(result_path).get("result") or {})), result_path
        raise


def evaluate_runtime_result(result: dict, result_path: Path, binding: dict) -> tuple[dict, list[dict]]:
    failed_requirements = []
    slot_name = binding["slot_name"]
    expected_asset_path = normalize_asset_path(binding["skeletal_mesh_asset"])
    slot_bindings = list(result.get("slot_bindings") or [])
    managed_components_by_slot = dict(result.get("managed_components_by_slot") or {})
    slot_attach_state = list(result.get("slot_attach_state") or [])
    clothing_binding_result = next((entry for entry in slot_bindings if entry.get("slot_name") == slot_name), {})
    clothing_component = dict(managed_components_by_slot.get(slot_name) or {})
    clothing_attach_state = next((entry for entry in slot_attach_state if entry.get("slot_name") == slot_name), {})
    attach_resolution_mode = str(clothing_attach_state.get("attach_resolution_mode") or "")
    owner_origin_attach_ok = attach_resolution_mode in {"owner_origin", "owner_origin_fallback"} and bool((clothing_component.get("bounds") or {}).get("non_zero"))
    runtime_errors = list(result.get("errors") or [])
    soft_runtime_pass = owner_origin_attach_ok and sorted(set(runtime_errors)) == [f"slot_attach_unresolved:{slot_name}"]

    if result.get("status") != "pass" and not soft_runtime_pass:
        failed_requirements.append(
            make_failed_requirement(
                "p2_runtime_failed",
                "The clothing slot runtime inspection did not pass.",
                result_path=str(result_path.resolve()),
                errors=runtime_errors,
            )
        )
    if clothing_binding_result.get("item_kind") != "skeletal_mesh":
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_wrong_item_kind",
                "The clothing slot did not resolve to skeletal_mesh.",
                result_path=str(result_path.resolve()),
                binding=clothing_binding_result,
            )
        )
    if normalize_asset_path(clothing_binding_result.get("asset_path")) != expected_asset_path:
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_binding_asset_mismatch",
                "The clothing slot binding did not resolve to the expected wearable asset.",
                result_path=str(result_path.resolve()),
                expected_asset_path=expected_asset_path,
                actual_asset_path=clothing_binding_result.get("asset_path"),
            )
        )
    if clothing_component.get("class_name") != "SkeletalMeshComponent":
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_component_missing",
                "The clothing slot did not create a skeletal mesh component.",
                result_path=str(result_path.resolve()),
                managed_component=clothing_component,
            )
        )
    if not bool((clothing_component.get("bounds") or {}).get("non_zero")):
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_bounds_invalid",
                "The clothing slot component bounds are not valid.",
                result_path=str(result_path.resolve()),
                managed_component=clothing_component,
            )
        )
    if clothing_attach_state and clothing_attach_state.get("resolved_attach_socket_exists") is False and not owner_origin_attach_ok:
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_attach_unresolved",
                "The clothing slot could not resolve an attach target on the PMX host.",
                result_path=str(result_path.resolve()),
                attach_state=clothing_attach_state,
            )
        )

    return (
        {
            "package_id": result.get("package_id"),
            "sample_id": result.get("sample_id"),
            "status": "pass" if not failed_requirements else "fail",
            "host_blueprint_asset": result.get("host_blueprint_asset"),
            "clothing_binding": clothing_binding_result,
            "clothing_component": clothing_component,
            "clothing_attach_state": clothing_attach_state,
            "owner_origin_attach_ok": owner_origin_attach_ok,
            "slot_conflicts": list(result.get("slot_conflicts") or []),
            "artifacts": {
                "result_path": str(result_path.resolve()),
            },
        },
        failed_requirements,
    )


def evaluate_visual_result(result: dict, result_path: Path, binding: dict, tracked_min_coverage: float) -> tuple[dict, list[dict]]:
    failed_requirements = []
    slot_name = binding["slot_name"]
    expected_asset_path = normalize_asset_path(binding["skeletal_mesh_asset"])
    managed_components_by_slot = dict(result.get("managed_components_by_slot") or {})
    slot_attach_state = list(result.get("slot_attach_state") or [])
    clothing_component = dict(managed_components_by_slot.get(slot_name) or {})
    clothing_attach_state = next((entry for entry in slot_attach_state if entry.get("slot_name") == slot_name), {})
    attach_resolution_mode = str(clothing_attach_state.get("attach_resolution_mode") or "")
    owner_origin_attach_ok = attach_resolution_mode in {"owner_origin", "owner_origin_fallback"} and bool((clothing_component.get("bounds") or {}).get("non_zero"))
    shots = list(result.get("shots") or [])
    passing_visual_shots = sum(1 for shot in shots if shot.get("status") == "pass")
    passing_clothing_shots = sum(
        1
        for shot in shots
        if Path(str(shot.get("image_path") or "")).exists()
        and float((((shot.get("tracked_slot_coverages") or {}).get(slot_name) or {}).get("coverage_ratio") or 0.0)) >= tracked_min_coverage
    )

    if result.get("status") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "p2_visual_failed",
                "The clothing composition visual proof did not pass.",
                result_path=str(result_path.resolve()),
                errors=list(result.get("errors") or []),
            )
        )
    if normalize_asset_path(clothing_component.get("asset_path")) != expected_asset_path:
        failed_requirements.append(
            make_failed_requirement(
                "p2_visual_clothing_asset_mismatch",
                "The visual proof did not keep the expected clothing asset on the managed slot component.",
                result_path=str(result_path.resolve()),
                expected_asset_path=expected_asset_path,
                actual_asset_path=clothing_component.get("asset_path"),
            )
        )
    if not bool((clothing_component.get("bounds") or {}).get("non_zero")):
        failed_requirements.append(
            make_failed_requirement(
                "p2_visual_clothing_bounds_invalid",
                "The visual proof did not keep a valid clothing component bounds payload.",
                result_path=str(result_path.resolve()),
                managed_component=clothing_component,
            )
        )
    if clothing_attach_state and clothing_attach_state.get("resolved_attach_socket_exists") is False and not owner_origin_attach_ok:
        failed_requirements.append(
            make_failed_requirement(
                "p2_visual_clothing_attach_unresolved",
                "The visual proof shows an unresolved clothing attach state.",
                result_path=str(result_path.resolve()),
                attach_state=clothing_attach_state,
            )
        )
    if passing_visual_shots <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "p2_visual_no_passing_shots",
                "The clothing composition proof did not produce any passing visual shots.",
                result_path=str(result_path.resolve()),
            )
        )
    if passing_clothing_shots <= 0:
        failed_requirements.append(
            make_failed_requirement(
                "p2_clothing_not_visible_in_shots",
                "The clothing slot did not register enough on-screen coverage in any tracked visual shot.",
                result_path=str(result_path.resolve()),
                tracked_slot=slot_name,
                tracked_min_coverage=tracked_min_coverage,
            )
        )

    return (
        {
            "package_id": result.get("package_id"),
            "sample_id": result.get("sample_id"),
            "status": "pass" if not failed_requirements else "fail",
            "host_blueprint_asset": result.get("host_blueprint_asset"),
            "clothing_component": clothing_component,
            "clothing_attach_state": clothing_attach_state,
            "owner_origin_attach_ok": owner_origin_attach_ok,
            "passing_visual_shots": passing_visual_shots,
            "passing_clothing_shots": passing_clothing_shots,
            "shots": shots,
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
        "No latest_demo_stage_d1_onboarding_report.json could be resolved for P2.",
    )
    d1_report = load_json(d1_report_path)
    host_key = str(d1_report.get("host_key") or "demo")
    level_path = str(d1_report.get("level_path") or "/Game/Levels/DefaultLevel")
    packages = ready_demo_packages(d1_report)
    if len(packages) != 2:
        failed_requirements.append(
            make_failed_requirement(
                "ready_package_count",
                "P2 requires exactly two ready demo packages from D1 onboarding.",
                expected=2,
                actual=len(packages),
                d1_report_path=str(d1_report_path.resolve()),
            )
        )

    binding = clothing_binding(args.clothing_slot_name, args.attach_socket_name, args.clothing_asset_path)
    runtime_checks = []
    visual_checks = []
    if not failed_requirements:
        for package in packages:
            try:
                runtime_raw, runtime_path = inspect_runtime(workspace, output_root, host_key, package, level_path, binding)
                runtime_evaluated, runtime_failures = evaluate_runtime_result(runtime_raw, runtime_path, binding)
                runtime_checks.append(runtime_evaluated)
                failed_requirements.extend(runtime_failures)

                visual_raw, visual_path = inspect_visual(workspace, output_root, host_key, package, level_path, binding)
                visual_evaluated, visual_failures = evaluate_visual_result(visual_raw, visual_path, binding, args.tracked_clothing_min_coverage)
                visual_checks.append(visual_evaluated)
                failed_requirements.extend(visual_failures)
            except Exception as exc:
                failed_requirements.append(
                    make_failed_requirement(
                        "p2_package_execution_failed",
                        "P2 failed while validating a ready bundle with the clothing slot fixture.",
                        package_id=package.get("package_id"),
                        error=str(exc),
                    )
                )

    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, "p2_first_complete_pass")
    counts = {
        "required_ready_packages": 2,
        "resolved_ready_packages": len(packages),
        "runtime_checks": len(runtime_checks),
        "passing_runtime_checks": sum(1 for item in runtime_checks if item.get("status") == "pass"),
        "visual_checks": len(visual_checks),
        "passing_visual_checks": sum(1 for item in visual_checks if item.get("status") == "pass"),
        "passing_clothing_visual_shots": sum(int(item.get("passing_clothing_shots") or 0) for item in visual_checks),
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
                "clothing_slot_name": binding["slot_name"],
                "attach_socket_name": binding["attach_socket_name"],
                "clothing_asset_path": binding["skeletal_mesh_asset"],
                "tracked_clothing_min_coverage": float(args.tracked_clothing_min_coverage),
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "resolved_package_ids": [package.get("package_id") for package in packages],
            "runtime_checks": runtime_checks,
            "visual_checks": visual_checks,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "d1_report_path": str(d1_report_path.resolve()),
            },
        },
        schema_family="aiue_clothing_vertical_slice_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_clothing_vertical_slice_report",
            notes=["internal_p2_gate", "generic_slot_runtime_clothing_slice"],
        ),
    )
    report_path = output_root / "p2_clothing_vertical_slice_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
