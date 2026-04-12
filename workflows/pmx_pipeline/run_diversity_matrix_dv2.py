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
    verification_named_report_path,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope  # noqa: E402
from aiue_core.schema_utils import load_json, load_workspace_config, write_json  # noqa: E402
from aiue_t1.diversity_matrix import build_diversity_axis  # noqa: E402
from aiue_t2.demo_control_state import build_control_run_summary  # noqa: E402
from aiue_unreal.host_bridge import run_host_auto_ue_cli  # noqa: E402


GATE_ID = "diversity_matrix_dv2"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_DV1_LATEST_NAME = "latest_diversity_matrix_dv1_report.json"
DEFAULT_ALT_CLOTHING_STATIC_MESH = (
    "/Game/MetaHumans/Kellan/MaleHair/Hair/Eyebrows_M_Full_CardsMesh_Group0_LOD1."
    "Eyebrows_M_Full_CardsMesh_Group0_LOD1"
)
DEFAULT_ALT_FX_NIAGARA_SYSTEM = "/Niagara/DefaultAssets/Templates/Systems/RadialBurst.RadialBurst"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "targeted_run_count_per_package": 3,
    "request_kind": "action_preview",
    "request_driver": "host_auto_ue_cli",
    "prerequisite_gate_id": "diversity_matrix_dv1",
    "target_axes": [
        "action_variation",
        "clothing_fixture_diversity",
        "fx_fixture_diversity",
    ],
    "capture_width": 1280,
    "capture_height": 720,
    "capture_delay_seconds": 0.2,
    "subject_min_screen_coverage": 0.015,
    "weapon_min_screen_coverage": 0.001,
    "scene_capture_source": "SCS_FINAL_COLOR_HDR",
    "scene_capture_warmup_count": 4,
    "scene_capture_warmup_delay_seconds": 0.08,
    "tracked_slots": ["clothing", "fx"],
    "min_distance_delta": 40.0,
    "min_yaw_delta": 10.0,
    "slot_coverage_thresholds": {
        "clothing": 0.0001,
        "fx": 0.01,
    },
}
ALT_ACTION_VARIANT = {
    "axis_id": "action_variation",
    "variant_id": "dv2_root_translate_forward",
    "action_kind": "root_translate_forward",
    "action_distance": 85.0,
    "action_yaw_delta": 0.0,
    "action_settle_seconds": 0.2,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE automated diversity matrix DV2 report.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--dv1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--clothing-static-mesh-asset", default=DEFAULT_ALT_CLOTHING_STATIC_MESH)
    parser.add_argument("--fx-niagara-system-asset", default=DEFAULT_ALT_FX_NIAGARA_SYSTEM)
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


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


def expected_component_class(item_kind: str) -> str:
    if item_kind == "static_mesh":
        return "StaticMeshComponent"
    if item_kind == "niagara_system":
        return "NiagaraComponent"
    return "SkeletalMeshComponent"


def required_slot_coverage(slot_name: str) -> float:
    thresholds = dict(FIXED_EXECUTION_PROFILE.get("slot_coverage_thresholds") or {})
    return float(thresholds.get(slot_name) or 0.0)


def default_alt_clothing_variant(static_mesh_asset: str) -> dict[str, Any]:
    return {
        "axis_id": "clothing_fixture_diversity",
        "variant_id": "dv2_kellan_eyebrow_cards_fixture",
        "slot_name": "clothing",
        "item_package_id": "dv2_kellan_eyebrow_cards_fixture",
        "item_kind": "static_mesh",
        "attach_socket_name": "Head",
        "static_mesh_asset": str(static_mesh_asset),
        "consumer_ready": True,
    }


def default_alt_fx_variant(niagara_system_asset: str) -> dict[str, Any]:
    return {
        "axis_id": "fx_fixture_diversity",
        "variant_id": "dv2_radial_burst_fixture",
        "slot_name": "fx",
        "item_package_id": "dv2_radial_burst_fixture",
        "item_kind": "niagara_system",
        "attach_socket_name": "WeaponSocket",
        "niagara_system_asset": str(niagara_system_asset),
        "consumer_ready": True,
        "niagara_desired_age_seconds": 0.08,
        "niagara_seek_delta_seconds": 1.0 / 60.0,
        "niagara_advance_step_count": 4,
        "niagara_advance_step_delta_seconds": 1.0 / 60.0,
    }


def _load_latest_required_report(workspace: dict, explicit_path: str | None, latest_name: str) -> tuple[Path, dict[str, Any]]:
    report_path = Path(explicit_path).expanduser().resolve() if explicit_path else verification_named_report_path(workspace, REPO_ROOT, latest_name)
    if not report_path.exists():
        raise FileNotFoundError(report_path)
    return report_path, load_json(report_path)


def _axis_observed_values(report: dict[str, Any], axis_id: str) -> set[str]:
    for axis in list(report.get("coverage_axes") or []):
        if str(axis.get("axis_id") or "") == axis_id:
            return {str(item) for item in list(axis.get("observed_values") or []) if str(item)}
    return set()


def _first_action_preset(package_payload: dict[str, Any]) -> dict[str, Any]:
    presets = [dict(item) for item in list(package_payload.get("action_presets") or [])]
    return presets[0] if presets else {}


def _first_action_preset_id(package_payload: dict[str, Any]) -> str:
    preset = _first_action_preset(package_payload)
    return str(preset.get("preset_id") or "")


def _first_animation_preset_id(package_payload: dict[str, Any]) -> str:
    for preset in list(package_payload.get("animation_presets") or []):
        preset_id = str(dict(preset).get("preset_id") or "")
        if preset_id:
            return preset_id
    return ""


def _baseline_clothing_binding(package_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(package_payload.get("clothing_binding") or {})


def _baseline_fx_binding(package_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(package_payload.get("fx_binding") or {})


def _variant_slot_binding(variant: dict[str, Any]) -> dict[str, Any]:
    binding = {
        "slot_name": str(variant.get("slot_name") or ""),
        "item_package_id": str(variant.get("item_package_id") or variant.get("variant_id") or ""),
        "item_kind": str(variant.get("item_kind") or "skeletal_mesh"),
        "attach_socket_name": str(variant.get("attach_socket_name") or "WeaponSocket"),
        "consumer_ready": bool(variant.get("consumer_ready", True)),
    }
    if str(binding["item_kind"]) == "static_mesh":
        binding["static_mesh_asset"] = str(variant.get("static_mesh_asset") or "")
    elif str(binding["item_kind"]) == "niagara_system":
        binding["niagara_system_asset"] = str(variant.get("niagara_system_asset") or "")
        binding["niagara_desired_age_seconds"] = float(variant.get("niagara_desired_age_seconds") or 0.08)
        binding["niagara_seek_delta_seconds"] = float(variant.get("niagara_seek_delta_seconds") or (1.0 / 60.0))
        binding["niagara_advance_step_count"] = int(variant.get("niagara_advance_step_count") or 4)
        binding["niagara_advance_step_delta_seconds"] = float(variant.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
    else:
        binding["skeletal_mesh_asset"] = str(variant.get("skeletal_mesh_asset") or "")
    return binding


def _slot_binding_overrides(package_payload: dict[str, Any], variant: dict[str, Any]) -> list[dict[str, Any]]:
    clothing_binding = _baseline_clothing_binding(package_payload)
    fx_binding = _baseline_fx_binding(package_payload)
    if str(variant.get("axis_id") or "") == "clothing_fixture_diversity":
        clothing_binding = _variant_slot_binding(variant)
    if str(variant.get("axis_id") or "") == "fx_fixture_diversity":
        fx_binding = _variant_slot_binding(variant)
    overrides = []
    if clothing_binding:
        overrides.append(clothing_binding)
    if fx_binding:
        overrides.append(fx_binding)
    return overrides


def _request_paths(output_root: Path, package_id: str, axis_id: str, variant_id: str) -> tuple[Path, Path, Path]:
    run_root = output_root / "targeted_runs" / package_id / axis_id / variant_id
    request_json_path = run_root / "action_preview_request.json"
    result_json_path = run_root / "action_preview_result.json"
    capture_root = run_root / "captures"
    capture_root.mkdir(parents=True, exist_ok=True)
    return request_json_path, result_json_path, capture_root


def _action_request_payload(
    *,
    package_payload: dict[str, Any],
    host_key: str,
    mode: str,
    variant: dict[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    hero_shot_id = str(package_payload.get("hero_shot_id") or "")
    hero_shot_plan = dict(package_payload.get("hero_shot_plan") or {})
    baseline_action_preset = _first_action_preset(package_payload)
    baseline_action_preset_id = _first_action_preset_id(package_payload)
    action_kind = str(variant.get("action_kind") or baseline_action_preset.get("action_kind") or "root_translate_and_turn")
    action_distance = float(
        variant.get("action_distance")
        or baseline_action_preset.get("action_distance")
        or baseline_action_preset.get("expected_distance_delta")
        or 85.0
    )
    action_yaw_delta = float(
        variant.get("action_yaw_delta")
        or baseline_action_preset.get("action_yaw_delta")
        or baseline_action_preset.get("expected_yaw_delta")
        or 24.0
    )
    action_settle_seconds = float(variant.get("action_settle_seconds") or baseline_action_preset.get("action_settle_seconds") or 0.2)
    overrides = _slot_binding_overrides(package_payload, variant)
    params = {
        "package_id": str(package_payload.get("package_id") or ""),
        "sample_id": str(package_payload.get("sample_id") or ""),
        "host_blueprint_asset_path": str(package_payload.get("host_blueprint_asset") or ""),
        "level_path": str(package_payload.get("level_path") or ""),
        "location": dict(package_payload.get("spawn_location") or {}),
        "rotation": dict(package_payload.get("spawn_rotation") or {}),
        "output_root": str(output_root.resolve()),
        "shot_order": [hero_shot_id] if hero_shot_id else [],
        "shot_plans": [hero_shot_plan] if hero_shot_plan else [],
        "slot_binding_overrides": overrides,
        "capture_width": int(FIXED_EXECUTION_PROFILE["capture_width"]),
        "capture_height": int(FIXED_EXECUTION_PROFILE["capture_height"]),
        "capture_delay_seconds": float(FIXED_EXECUTION_PROFILE["capture_delay_seconds"]),
        "subject_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["subject_min_screen_coverage"]),
        "weapon_min_screen_coverage": float(FIXED_EXECUTION_PROFILE["weapon_min_screen_coverage"]),
        "scene_capture_source": str(FIXED_EXECUTION_PROFILE["scene_capture_source"]),
        "scene_capture_warmup_count": int(FIXED_EXECUTION_PROFILE["scene_capture_warmup_count"]),
        "scene_capture_warmup_delay_seconds": float(FIXED_EXECUTION_PROFILE["scene_capture_warmup_delay_seconds"]),
        "tracked_slots": list(FIXED_EXECUTION_PROFILE["tracked_slots"]),
        "min_distance_delta": float(FIXED_EXECUTION_PROFILE["min_distance_delta"]),
        "min_yaw_delta": float(FIXED_EXECUTION_PROFILE["min_yaw_delta"]),
        "action_kind": action_kind,
        "action_distance": action_distance,
        "action_yaw_delta": action_yaw_delta,
        "action_settle_seconds": action_settle_seconds,
    }
    fx_binding = next((binding for binding in overrides if str(binding.get("slot_name") or "") == "fx"), {})
    if fx_binding:
        params["prime_niagara_before_capture"] = True
        params["niagara_desired_age_seconds"] = float(fx_binding.get("niagara_desired_age_seconds") or 0.08)
        params["niagara_seek_delta_seconds"] = float(fx_binding.get("niagara_seek_delta_seconds") or (1.0 / 60.0))
        params["niagara_advance_step_count"] = int(fx_binding.get("niagara_advance_step_count") or 4)
        params["niagara_advance_step_delta_seconds"] = float(fx_binding.get("niagara_advance_step_delta_seconds") or (1.0 / 60.0))
        params["niagara_flush_world"] = True
    selected_action_preset_id = str(variant.get("selected_action_preset_id") or "")
    if not selected_action_preset_id:
        axis_id = str(variant.get("axis_id") or "")
        if axis_id == "action_variation":
            selected_action_preset_id = str(variant.get("variant_id") or baseline_action_preset_id)
        else:
            selected_action_preset_id = baseline_action_preset_id
    return {
        "request_kind": "action_preview",
        "selected_package_id": str(package_payload.get("package_id") or ""),
        "selected_action_preset_id": selected_action_preset_id,
        "selected_animation_preset_id": _first_animation_preset_id(package_payload),
        "host_key": str(host_key or FIXED_EXECUTION_PROFILE["host_key"]),
        "mode": str(mode or FIXED_EXECUTION_PROFILE["mode"]),
        "command": "action-preview",
        "params": params,
    }


def _invoke_targeted_run(
    *,
    workspace: dict[str, Any],
    request_payload: dict[str, Any],
    request_json_path: Path,
    result_json_path: Path,
) -> tuple[dict[str, Any], str | None]:
    write_json(request_json_path, request_payload)
    invocation_error = None
    invocation_payload: dict[str, Any] = {}
    try:
        invocation_payload = run_host_auto_ue_cli(
            workspace_or_config=workspace,
            mode=str(request_payload.get("mode") or FIXED_EXECUTION_PROFILE["mode"]),
            command=str(request_payload.get("command") or ""),
            params=dict(request_payload.get("params") or {}),
            output_path=str(result_json_path.resolve()),
            host_key=str(request_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
        )
    except Exception as exc:
        invocation_error = str(exc)
        if result_json_path.exists():
            invocation_payload = {
                "payload": load_json(result_json_path),
                "host_key": str(request_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
            }
        else:
            invocation_payload = {
                "payload": {
                    "status": "error",
                    "result": {},
                },
                "host_key": str(request_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
            }
    return invocation_payload, invocation_error


def _max_tracked_slot_coverage(result_payload: dict[str, Any], slot_name: str) -> float:
    max_ratio = 0.0
    for shot in list(result_payload.get("shots") or []):
        for phase_key in ("before", "after"):
            phase_payload = dict(shot.get(phase_key) or {})
            tracked_payload = dict((phase_payload.get("tracked_slot_coverages") or {}).get(slot_name) or {})
            max_ratio = max(max_ratio, float(tracked_payload.get("coverage_ratio") or 0.0))
    return max_ratio


def _slot_binding_from_result(result_payload: dict[str, Any], slot_name: str) -> dict[str, Any]:
    return next(
        (dict(item) for item in list(result_payload.get("slot_bindings") or []) if str(item.get("slot_name") or "") == slot_name),
        {},
    )


def _slot_attach_state_from_result(result_payload: dict[str, Any], slot_name: str) -> dict[str, Any]:
    return next(
        (dict(item) for item in list(result_payload.get("slot_attach_state") or []) if str(item.get("slot_name") or "") == slot_name),
        {},
    )


def _expected_asset_path(variant: dict[str, Any]) -> str:
    item_kind = str(variant.get("item_kind") or "")
    if item_kind == "static_mesh":
        return normalize_asset_path(variant.get("static_mesh_asset"))
    if item_kind == "niagara_system":
        return normalize_asset_path(variant.get("niagara_system_asset"))
    return normalize_asset_path(variant.get("skeletal_mesh_asset"))


def _evaluate_targeted_slot(
    *,
    package_id: str,
    result_payload: dict[str, Any],
    variant: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    slot_name = str(variant.get("slot_name") or "")
    slot_binding = _slot_binding_from_result(result_payload, slot_name)
    managed_component = dict((result_payload.get("managed_components_by_slot") or {}).get(slot_name) or {})
    attach_state = _slot_attach_state_from_result(result_payload, slot_name)
    expected_kind = str(variant.get("item_kind") or "")
    expected_asset_path = _expected_asset_path(variant)
    actual_binding_asset_path = normalize_asset_path(slot_binding.get("asset_path"))
    actual_component_asset_path = normalize_asset_path(managed_component.get("asset_path"))
    tracked_slot_max_coverage = _max_tracked_slot_coverage(result_payload, slot_name)
    if not slot_binding:
        failures.append(
            make_failed_requirement(
                "dv2_slot_binding_missing",
                "DV2 requires the targeted slot binding to be present in the action preview result.",
                package_id=package_id,
                slot_name=slot_name,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
            )
        )
    if str(slot_binding.get("item_package_id") or "") != str(variant.get("item_package_id") or variant.get("variant_id") or ""):
        failures.append(
            make_failed_requirement(
                "dv2_slot_binding_item_package_mismatch",
                "DV2 requires the targeted slot binding to resolve to the expected item package id.",
                package_id=package_id,
                slot_name=slot_name,
                expected_item_package_id=str(variant.get("item_package_id") or variant.get("variant_id") or ""),
                actual_item_package_id=slot_binding.get("item_package_id"),
            )
        )
    if str(slot_binding.get("item_kind") or "") != expected_kind:
        failures.append(
            make_failed_requirement(
                "dv2_slot_binding_item_kind_mismatch",
                "DV2 requires the targeted slot binding to resolve to the expected item kind.",
                package_id=package_id,
                slot_name=slot_name,
                expected_item_kind=expected_kind,
                actual_item_kind=slot_binding.get("item_kind"),
            )
        )
    if actual_binding_asset_path != expected_asset_path:
        failures.append(
            make_failed_requirement(
                "dv2_slot_binding_asset_mismatch",
                "DV2 requires the targeted slot binding to resolve to the expected asset path.",
                package_id=package_id,
                slot_name=slot_name,
                expected_asset_path=expected_asset_path,
                actual_asset_path=slot_binding.get("asset_path"),
            )
        )
    if str(managed_component.get("class_name") or "") != expected_component_class(expected_kind):
        failures.append(
            make_failed_requirement(
                "dv2_slot_component_class_mismatch",
                "DV2 requires the targeted slot to create the expected managed component class.",
                package_id=package_id,
                slot_name=slot_name,
                expected_component_class=expected_component_class(expected_kind),
                actual_component_class=managed_component.get("class_name"),
            )
        )
    if actual_component_asset_path != expected_asset_path:
        failures.append(
            make_failed_requirement(
                "dv2_slot_component_asset_mismatch",
                "DV2 requires the targeted slot managed component to resolve to the expected asset path.",
                package_id=package_id,
                slot_name=slot_name,
                expected_asset_path=expected_asset_path,
                actual_asset_path=managed_component.get("asset_path"),
            )
        )
    if not bool((managed_component.get("bounds") or {}).get("non_zero")):
        failures.append(
            make_failed_requirement(
                "dv2_slot_component_bounds_invalid",
                "DV2 requires the targeted slot managed component to keep non-zero bounds.",
                package_id=package_id,
                slot_name=slot_name,
                managed_component=managed_component,
            )
        )
    if not attach_state:
        failures.append(
            make_failed_requirement(
                "dv2_slot_attach_state_missing",
                "DV2 requires attach state evidence for each targeted slot override.",
                package_id=package_id,
                slot_name=slot_name,
            )
        )
    elif attach_state.get("resolved_attach_socket_exists") is False:
        failures.append(
            make_failed_requirement(
                "dv2_slot_attach_unresolved",
                "DV2 requires the targeted slot attach state to resolve successfully.",
                package_id=package_id,
                slot_name=slot_name,
                attach_state=attach_state,
            )
        )
    min_coverage = required_slot_coverage(slot_name)
    if tracked_slot_max_coverage < min_coverage:
        failures.append(
            make_failed_requirement(
                "dv2_slot_visibility_insufficient",
                "DV2 requires the targeted slot to remain measurably visible in the action preview proof.",
                package_id=package_id,
                slot_name=slot_name,
                tracked_slot_max_coverage=tracked_slot_max_coverage,
                minimum_required_coverage=min_coverage,
            )
        )
    return (
        {
            "slot_name": slot_name,
            "expected_item_kind": expected_kind,
            "expected_asset_path": expected_asset_path,
            "expected_component_class": expected_component_class(expected_kind),
            "resolved_slot_binding": slot_binding,
            "resolved_managed_component": managed_component,
            "resolved_attach_state": attach_state,
            "tracked_slot_max_coverage": tracked_slot_max_coverage,
            "tracked_slot_min_coverage": min_coverage,
        },
        failures,
    )


def _evaluate_targeted_run(
    *,
    package_id: str,
    variant: dict[str, Any],
    request_json_path: Path,
    result_json_path: Path,
    invocation_payload: dict[str, Any],
    invocation_error: str | None,
    selected_action_preset_id: str,
    selected_animation_preset_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    host_payload = dict(invocation_payload.get("payload") or {})
    result_payload = dict(host_payload.get("result") or {})
    invocation_status = str(result_payload.get("status") or host_payload.get("status") or "")
    run_summary = build_control_run_summary(
        request_kind="action_preview",
        operation="dv2_targeted_invoke",
        selected_package_id=package_id,
        selected_action_preset_id=selected_action_preset_id,
        selected_animation_preset_id=selected_animation_preset_id,
        invocation={
            "request_json_path": str(request_json_path.resolve()),
            "result_json_path": str(result_json_path.resolve()) if result_json_path.exists() else "",
            "host_key": str(invocation_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
            "payload": host_payload,
        },
    )
    credibility_summary = dict(run_summary.get("credibility_summary") or {})
    if invocation_error:
        failures.append(
            make_failed_requirement(
                "dv2_request_invoke_exception",
                "DV2 requires each targeted action-preview request to complete without a host bridge exception.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                error=invocation_error,
            )
        )
    if not request_json_path.exists():
        failures.append(
            make_failed_requirement(
                "dv2_request_json_missing",
                "DV2 requires a request JSON artifact for each targeted run.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                request_json_path=str(request_json_path.resolve()),
            )
        )
    if not result_json_path.exists():
        failures.append(
            make_failed_requirement(
                "dv2_result_json_missing",
                "DV2 requires a result JSON artifact for each targeted run.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                result_json_path=str(result_json_path.resolve()),
            )
        )
    if invocation_status != "pass":
        failures.append(
            make_failed_requirement(
                "dv2_result_not_pass",
                "DV2 requires each targeted action-preview invoke result to pass.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                result_status=invocation_status,
                result_json_path=str(result_json_path.resolve()) if result_json_path.exists() else "",
            )
        )
    if not bool(credibility_summary.get("subject_visible")):
        failures.append(
            make_failed_requirement(
                "dv2_subject_not_visible",
                "DV2 requires the subject to remain visible during each targeted run.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                credibility_summary=credibility_summary,
            )
        )
    if not bool(credibility_summary.get("before_image_present")) or not bool(credibility_summary.get("after_image_present")):
        failures.append(
            make_failed_requirement(
                "dv2_before_after_images_missing",
                "DV2 requires before and after images for each targeted run.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                credibility_summary=credibility_summary,
            )
        )
    if not bool(credibility_summary.get("action_motion_verified")):
        failures.append(
            make_failed_requirement(
                "dv2_action_motion_not_verified",
                "DV2 requires action-preview credibility proof for each targeted run.",
                package_id=package_id,
                axis_id=variant.get("axis_id"),
                variant_id=variant.get("variant_id"),
                credibility_summary=credibility_summary,
            )
        )

    targeted_slot = {}
    if str(variant.get("axis_id") or "") in {"clothing_fixture_diversity", "fx_fixture_diversity"}:
        targeted_slot, slot_failures = _evaluate_targeted_slot(
            package_id=package_id,
            result_payload=result_payload,
            variant=variant,
        )
        failures.extend(slot_failures)

    return (
        {
            "axis_id": str(variant.get("axis_id") or ""),
            "variant_id": str(variant.get("variant_id") or ""),
            "status": "pass" if not failures else "fail",
            "request_kind": "action_preview",
            "selected_action_preset_id": selected_action_preset_id,
            "selected_animation_preset_id": selected_animation_preset_id,
            "request_json_path": str(request_json_path.resolve()),
            "result_json_path": str(result_json_path.resolve()) if result_json_path.exists() else "",
            "result_status": invocation_status,
            "host_key": str(invocation_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"]),
            "generated_at_utc": str(run_summary.get("generated_at_utc") or ""),
            "key_image_paths": dict(run_summary.get("key_image_paths") or {}),
            "credibility_summary": credibility_summary,
            "warning_flags": list(credibility_summary.get("warning_flags") or []),
            "targeted_slot": targeted_slot,
            "failed_requirements": failures,
        },
        failures,
    )


def _invoke_package_variant(
    *,
    workspace: dict[str, Any],
    host_key: str,
    mode: str,
    output_root: Path,
    package_payload: dict[str, Any],
    variant: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    package_id = str(package_payload.get("package_id") or "")
    request_json_path, result_json_path, capture_root = _request_paths(
        output_root,
        package_id,
        str(variant.get("axis_id") or ""),
        str(variant.get("variant_id") or ""),
    )
    request_payload = _action_request_payload(
        package_payload=package_payload,
        host_key=host_key,
        mode=mode,
        variant=variant,
        output_root=capture_root,
    )
    invocation_payload, invocation_error = _invoke_targeted_run(
        workspace=workspace,
        request_payload=request_payload,
        request_json_path=request_json_path,
        result_json_path=result_json_path,
    )
    selected_action_preset_id = str(request_payload.get("selected_action_preset_id") or "")
    selected_animation_preset_id = str(request_payload.get("selected_animation_preset_id") or "")
    return _evaluate_targeted_run(
        package_id=package_id,
        variant=variant,
        request_json_path=request_json_path,
        result_json_path=result_json_path,
        invocation_payload=invocation_payload,
        invocation_error=invocation_error,
        selected_action_preset_id=selected_action_preset_id,
        selected_animation_preset_id=selected_animation_preset_id,
    )


def _axis_entry_by_id(coverage_axes: list[dict[str, Any]], axis_id: str) -> dict[str, Any]:
    return next((dict(item) for item in coverage_axes if str(item.get("axis_id") or "") == axis_id), {})


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    workspace_config_path = Path(args.workspace_config).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    try:
        dv1_report_path, dv1_report = _load_latest_required_report(
            workspace,
            args.dv1_report_path,
            DEFAULT_DV1_LATEST_NAME,
        )
    except FileNotFoundError as exc:
        failed_requirements.append(
            make_failed_requirement(
                "dv2_dv1_report_missing",
                "DV2 requires the latest DV1 diversity matrix report before targeted expansion.",
                report_path=str(exc),
            )
        )
        dv1_report_path = None
        dv1_report = {}

    if dv1_report and str(dv1_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "dv2_dv1_not_pass",
                "DV2 requires the DV1 diversity matrix prerequisite to pass.",
                dv1_report_path=str(dv1_report_path.resolve()) if dv1_report_path else "",
                dv1_status=dv1_report.get("status"),
            )
        )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "dv2_session_manifest_missing",
                "DV2 requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    if len(resolved_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "dv2_required_package_count_mismatch",
                "DV2 requires exactly two ready bundles in the session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    host_key = str(session_payload.get("host_key") or FIXED_EXECUTION_PROFILE["host_key"])
    mode = str(session_payload.get("mode") or FIXED_EXECUTION_PROFILE["mode"])
    alt_variants = [
        dict(ALT_ACTION_VARIANT),
        default_alt_clothing_variant(args.clothing_static_mesh_asset),
        default_alt_fx_variant(args.fx_niagara_system_asset),
    ]

    per_package_results: list[dict[str, Any]] = []
    targeted_variant_pass_counts = {str(variant.get("axis_id") or ""): 0 for variant in alt_variants}
    for package_payload in resolved_packages:
        package_id = str(package_payload.get("package_id") or "")
        package_failures: list[dict[str, Any]] = []
        baseline_action_preset = _first_action_preset(package_payload)
        anchor_animation_preset_id = _first_animation_preset_id(package_payload)
        if not baseline_action_preset:
            package_failures.append(
                make_failed_requirement(
                    "dv2_action_preset_missing",
                    "DV2 requires at least one baseline action preset for each package.",
                    package_id=package_id,
                )
            )
        if not anchor_animation_preset_id:
            package_failures.append(
                make_failed_requirement(
                    "dv2_animation_preset_missing",
                    "DV2 requires at least one anchor animation preset for each package.",
                    package_id=package_id,
                )
            )

        targeted_runs: list[dict[str, Any]] = []
        if not package_failures:
            for variant in alt_variants:
                variant_payload = dict(variant)
                if str(variant_payload.get("axis_id") or "") != "action_variation":
                    variant_payload.setdefault("action_kind", str(baseline_action_preset.get("action_kind") or "root_translate_and_turn"))
                    variant_payload.setdefault(
                        "action_distance",
                        float(
                            baseline_action_preset.get("action_distance")
                            or baseline_action_preset.get("expected_distance_delta")
                            or 85.0
                        ),
                    )
                    variant_payload.setdefault(
                        "action_yaw_delta",
                        float(
                            baseline_action_preset.get("action_yaw_delta")
                            or baseline_action_preset.get("expected_yaw_delta")
                            or 24.0
                        ),
                    )
                    variant_payload.setdefault(
                        "action_settle_seconds",
                        float(baseline_action_preset.get("action_settle_seconds") or 0.2),
                    )
                run_payload, run_failures = _invoke_package_variant(
                    workspace=workspace,
                    host_key=host_key,
                    mode=mode,
                    output_root=output_root,
                    package_payload=package_payload,
                    variant=variant_payload,
                )
                targeted_runs.append(run_payload)
                if str(run_payload.get("status") or "") == "pass":
                    targeted_variant_pass_counts[str(variant_payload.get("axis_id") or "")] += 1
                package_failures.extend(run_failures)

        per_package_results.append(
            {
                "package_id": package_id,
                "sample_id": str(package_payload.get("sample_id") or ""),
                "host_blueprint_asset": str(package_payload.get("host_blueprint_asset") or ""),
                "baseline_action_preset_id": str(baseline_action_preset.get("preset_id") or ""),
                "anchor_animation_preset_id": anchor_animation_preset_id,
                "baseline_slot_variants": {
                    "weapon_item_package_id": str(dict(package_payload.get("weapon_binding") or {}).get("item_package_id") or ""),
                    "clothing_item_package_id": str(dict(package_payload.get("clothing_binding") or {}).get("item_package_id") or ""),
                    "fx_item_package_id": str(dict(package_payload.get("fx_binding") or {}).get("item_package_id") or ""),
                },
                "targeted_runs": targeted_runs,
                "status": "pass" if not package_failures else "fail",
                "errors": package_failures,
            }
        )
        failed_requirements.extend(package_failures)

    observed_by_axis = {
        "character_variant_diversity": _axis_observed_values(dv1_report, "character_variant_diversity"),
        "weapon_variant_diversity": _axis_observed_values(dv1_report, "weapon_variant_diversity"),
        "clothing_fixture_diversity": _axis_observed_values(dv1_report, "clothing_fixture_diversity"),
        "fx_fixture_diversity": _axis_observed_values(dv1_report, "fx_fixture_diversity"),
        "action_variation": _axis_observed_values(dv1_report, "action_variation"),
        "animation_variation": _axis_observed_values(dv1_report, "animation_variation"),
    }
    required_package_count = len(resolved_packages)
    variant_results = []
    for variant in alt_variants:
        axis_id = str(variant.get("axis_id") or "")
        variant_id = str(variant.get("item_package_id") or variant.get("variant_id") or "")
        passing_packages = int(targeted_variant_pass_counts.get(axis_id) or 0)
        fully_verified = bool(required_package_count and passing_packages == required_package_count)
        if fully_verified:
            observed_by_axis.setdefault(axis_id, set()).add(variant_id)
        variant_results.append(
            {
                "axis_id": axis_id,
                "variant_id": str(variant.get("variant_id") or variant_id),
                "observed_value": variant_id,
                "required_package_count": required_package_count,
                "passing_package_count": passing_packages,
                "status": "covered" if fully_verified else ("partial" if passing_packages > 0 else "missing"),
            }
        )

    coverage_axes = [
        build_diversity_axis("character_variant_diversity", sorted(observed_by_axis["character_variant_diversity"]), noun_phrase="character bundles", gate_label="DV2"),
        build_diversity_axis("weapon_variant_diversity", sorted(observed_by_axis["weapon_variant_diversity"]), noun_phrase="weapon bundles", gate_label="DV2"),
        build_diversity_axis("clothing_fixture_diversity", sorted(observed_by_axis["clothing_fixture_diversity"]), noun_phrase="clothing fixtures", gate_label="DV2"),
        build_diversity_axis("fx_fixture_diversity", sorted(observed_by_axis["fx_fixture_diversity"]), noun_phrase="FX fixtures", gate_label="DV2"),
        build_diversity_axis("action_variation", sorted(observed_by_axis["action_variation"]), noun_phrase="verified action presets", gate_label="DV2"),
        build_diversity_axis("animation_variation", sorted(observed_by_axis["animation_variation"]), noun_phrase="verified animation presets", gate_label="DV2"),
    ]
    for axis in coverage_axes:
        if str(axis.get("status") or "") != "covered":
            failed_requirements.append(
                make_failed_requirement(
                    "dv2_axis_not_covered",
                    "DV2 requires every diversity axis to be covered after targeted expansion.",
                    axis_id=str(axis.get("axis_id") or ""),
                    axis_status=str(axis.get("status") or ""),
                    observed_values=list(axis.get("observed_values") or []),
                )
            )

    distinct_counts = {
        "character_variant_diversity": int(_axis_entry_by_id(coverage_axes, "character_variant_diversity").get("distinct_count") or 0),
        "weapon_variant_diversity": int(_axis_entry_by_id(coverage_axes, "weapon_variant_diversity").get("distinct_count") or 0),
        "clothing_fixture_diversity": int(_axis_entry_by_id(coverage_axes, "clothing_fixture_diversity").get("distinct_count") or 0),
        "fx_fixture_diversity": int(_axis_entry_by_id(coverage_axes, "fx_fixture_diversity").get("distinct_count") or 0),
        "action_variation": int(_axis_entry_by_id(coverage_axes, "action_variation").get("distinct_count") or 0),
        "animation_variation": int(_axis_entry_by_id(coverage_axes, "animation_variation").get("distinct_count") or 0),
    }
    targeted_runs = [
        dict(entry)
        for package in per_package_results
        for entry in list(package.get("targeted_runs") or [])
    ]
    counts = {
        "resolved_package_count": len(resolved_packages),
        "targeted_run_count": len(targeted_runs),
        "passing_targeted_runs": sum(1 for entry in targeted_runs if str(entry.get("status") or "") == "pass"),
        "targeted_run_count_per_package": int(FIXED_EXECUTION_PROFILE["targeted_run_count_per_package"]),
        "covered_axis_count": sum(1 for axis in coverage_axes if str(axis.get("status") or "") == "covered"),
        "partial_axis_count": sum(1 for axis in coverage_axes if str(axis.get("status") or "") == "partial"),
        "missing_axis_count": sum(1 for axis in coverage_axes if str(axis.get("status") or "") == "missing"),
    }
    status = "pass" if not failed_requirements and counts["resolved_package_count"] == int(FIXED_EXECUTION_PROFILE["required_package_count"]) else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_diversity_matrix_dv2_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()) if session_manifest_path.exists() else "",
            "fixed_execution_profile": {
                **dict(FIXED_EXECUTION_PROFILE),
                "alt_action_variant": dict(ALT_ACTION_VARIANT),
                "alt_clothing_variant": default_alt_clothing_variant(args.clothing_static_mesh_asset),
                "alt_fx_variant": default_alt_fx_variant(args.fx_niagara_system_asset),
            },
            "counts": counts,
            "baseline_gate_id": str(dv1_report.get("gate_id") or ""),
            "baseline_distinct_counts": dict(dv1_report.get("distinct_counts") or {}),
            "targeted_variant_results": variant_results,
            "distinct_counts": distinct_counts,
            "coverage_axes": coverage_axes,
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "dv1_report_path": str(dv1_report_path.resolve()) if dv1_report_path else "",
            },
        },
        "aiue_diversity_matrix_dv2_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_diversity_matrix_dv2_report",
            notes=[
                "automated_diversity_truth_source",
                "targeted_axis_expansion_on_top_of_dv1",
                "updates_test_governance_coverage_axes",
            ],
        ),
    )
    report_path = output_root / "diversity_matrix_dv2_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
