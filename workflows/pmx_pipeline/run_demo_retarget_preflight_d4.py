from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, run_host_command_result
from _gate_common import build_discussion_signal, default_latest_report_path, default_output_root, make_failed_requirement, now_utc, repo_root_from_workspace

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json

GATE_ID = "demo_retarget_preflight_d4"
DEMO_HOST_KEY = "demo"
REQUIRED_MODE = "editor_rendered"
DEFAULT_LEVEL_PATH = "/Game/Levels/DefaultLevel"
DEFAULT_ANIMATION_ASSET_PATH = "/Game/CombatMagicAnims/Demo/Mannequins/Anims/Unarmed/Attack/MM_Attack_01"
FIXED_EXECUTION_PROFILE = {
    "host_key": DEMO_HOST_KEY,
    "mode": REQUIRED_MODE,
    "level_path": DEFAULT_LEVEL_PATH,
    "animation_asset_path": DEFAULT_ANIMATION_ASSET_PATH,
    "purpose": "retarget_preflight_only",
    "spawn_location": {"x": 0.0, "y": 0.0, "z": 120.0},
    "spawn_rotation": {"pitch": 0.0, "yaw": 180.0, "roll": 0.0},
    "settle_delay_seconds": 0.2,
}

def parse_args():
    parser = argparse.ArgumentParser(description="Run the AiUE D4 demo retarget preflight gate.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--d1-report-path")
    parser.add_argument("--d3-report-path")
    parser.add_argument("--package-id")
    parser.add_argument("--animation-asset-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()

def default_latest_d1_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, "latest_demo_stage_d1_onboarding_report.json")

def default_latest_d3_report_path(workspace: dict) -> Path:
    return default_named_verification_report_path(workspace, REPO_ROOT, "latest_demo_animation_preview_d3_report.json")

def resolve_optional_report_path(explicit_path: str | None, fallback_path: Path) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"Report path does not exist: {candidate}")
    if fallback_path.exists():
        return fallback_path
    return None

def resolve_d1_report_path(workspace: dict, explicit_path: str | None) -> Path:
    candidate = resolve_optional_report_path(explicit_path, default_latest_d1_report_path(workspace))
    if candidate:
        return candidate
    raise FileNotFoundError("No latest_demo_stage_d1_onboarding_report.json could be resolved for D4.")

def resolve_target_package(d1_report: dict, requested_package_id: str | None) -> dict | None:
    package_results = list((((d1_report.get("scene_sweep") or {}).get("result") or {}).get("package_results") or []))
    candidates = []
    for entry in package_results:
        package_id = str(entry.get("package_id") or "")
        host_asset = str(entry.get("host_blueprint_asset_path") or "")
        if not package_id or not host_asset or entry.get("status") != "pass":
            continue
        candidates.append(
            {
                "package_id": package_id,
                "sample_id": entry.get("sample_id"),
                "host_blueprint_asset_path": host_asset,
            }
        )
    candidates = sorted(candidates, key=lambda item: item["package_id"])
    if requested_package_id:
        for item in candidates:
            if item["package_id"] == requested_package_id:
                return item
        return None
    return candidates[0] if candidates else None

def resolve_target_context(workspace: dict, args) -> tuple[dict | None, dict | None, Path | None]:
    d3_report_path = resolve_optional_report_path(args.d3_report_path, default_latest_d3_report_path(workspace))
    d3_report = load_json(d3_report_path) if d3_report_path and d3_report_path.exists() else None
    if d3_report and d3_report.get("package_id"):
        if not args.package_id or args.package_id == d3_report.get("package_id"):
            return (
                {
                    "package_id": d3_report.get("package_id"),
                    "sample_id": d3_report.get("sample_id"),
                    "host_blueprint_asset_path": d3_report.get("host_blueprint_asset"),
                },
                d3_report,
                d3_report_path,
            )

    d1_report_path = resolve_d1_report_path(workspace, args.d1_report_path)
    d1_report = load_json(d1_report_path)
    return resolve_target_package(d1_report, args.package_id), d1_report, d1_report_path

def load_project_plugin_state(workspace: dict, host_key: str) -> dict:
    hosts = dict(workspace.get("hosts") or {})
    host_entry = dict(hosts.get(host_key) or {})
    project_root_value = host_entry.get("project_root") or workspace["paths"]["unreal_project_root"]
    project_root = Path(project_root_value).expanduser().resolve()
    uproject_candidates = sorted(project_root.glob("*.uproject"))
    if not uproject_candidates:
        return {
            "project_root": str(project_root),
            "uproject_path": None,
            "enabled_plugins": [],
            "plugin_enabled": {},
            "warnings": ["uproject_not_found"],
        }
    uproject_path = uproject_candidates[0]
    raw = json.loads(uproject_path.read_text(encoding="utf-8-sig"))
    plugin_enabled = {
        str(entry.get("Name")): bool(entry.get("Enabled"))
        for entry in (raw.get("Plugins") or [])
        if entry.get("Name")
    }
    return {
        "project_root": str(project_root),
        "uproject_path": str(uproject_path),
        "enabled_plugins": sorted([name for name, enabled in plugin_enabled.items() if enabled]),
        "plugin_enabled": plugin_enabled,
        "warnings": [],
    }

def choose_next_step_id(project_plugin_state: dict, host_result: dict) -> tuple[str, str]:
    plugin_enabled = dict(project_plugin_state.get("plugin_enabled") or {})
    tooling = dict(host_result.get("retarget_tooling") or {})
    readiness = dict(host_result.get("retarget_readiness") or {})
    if not plugin_enabled.get("IKRig") and not tooling.get("can_author_new_retarget_assets"):
        return "enable_ikrig_plugin", "AiUEdemo does not currently enable the IKRig plugin in its .uproject."
    if not tooling.get("can_author_new_retarget_assets"):
        return "restore_ik_retarget_tooling", "The live demo host does not expose IKRigDefinition and IKRetargeter authoring APIs yet."
    if not tooling.get("matching_source_ik_rigs"):
        return "create_source_ikrig", "There is no source IK Rig candidate yet for the imported PMX skeleton."
    if not tooling.get("matching_target_ik_rigs"):
        return "create_target_ikrig", "There is no target mannequin IK Rig candidate yet in the demo project."
    if not tooling.get("matching_retargeters"):
        return "create_ik_retargeter", "There is no IK Retargeter candidate yet for this PMX-to-mannequin path."
    if readiness.get("direct_animation_compatible"):
        return "retry_animation_preview", "Direct compatibility already exists, so the next step is to retry a real animation preview."
    return "author_retarget_mapping", "Tooling is present, so the next step is to author the source and target chains for retargeting."

def main():
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict] = []
    target_package, upstream_report, upstream_report_path = resolve_target_context(workspace, args)
    if upstream_report_path and upstream_report and upstream_report.get("status") != "pass" and upstream_report.get("gate_id") == "demo_stage_d1_onboarding":
        failed_requirements.append(
            make_failed_requirement(
                "d1_prerequisite",
                "D4 requires a passing D1 demo onboarding report when no D3 context is available.",
                d1_report_path=str(upstream_report_path),
                d1_status=upstream_report.get("status"),
            )
        )
    if not target_package:
        failed_requirements.append(
            make_failed_requirement(
                "target_package_resolution",
                "D4 could not resolve a passing runtime-ready package from D3 or D1.",
                requested_package_id=args.package_id or "",
                upstream_report_path=str(upstream_report_path) if upstream_report_path else None,
            )
        )

    inherited_animation_asset_path = ""
    inherited_level_path = ""
    if upstream_report and upstream_report.get("gate_id") == "demo_animation_preview_d3":
        inherited_animation_asset_path = str(
            args.animation_asset_path
            or ((upstream_report.get("fixed_execution_profile") or {}).get("animation_asset_path"))
            or ((upstream_report.get("engine_evidence") or {}).get("animation_asset_path"))
            or ""
        )
        inherited_level_path = str(upstream_report.get("level_path") or "")

    level_path = str(inherited_level_path or DEFAULT_LEVEL_PATH)
    animation_asset_path = str(args.animation_asset_path or inherited_animation_asset_path or DEFAULT_ANIMATION_ASSET_PATH)
    result_path = output_root / "retarget_preflight_result.json"
    host_result = {}
    host_invocation_error = None
    if not failed_requirements and target_package:
        host_result, host_invocation_error, result_path = run_host_command_result(
            workspace=workspace,
            mode=REQUIRED_MODE,
            command="retarget-preflight",
            params={
                "package_id": target_package["package_id"],
                "sample_id": target_package.get("sample_id"),
                "host_blueprint_asset_path": target_package["host_blueprint_asset_path"],
                "level_path": level_path,
                "location": FIXED_EXECUTION_PROFILE["spawn_location"],
                "rotation": FIXED_EXECUTION_PROFILE["spawn_rotation"],
                "settle_delay_seconds": FIXED_EXECUTION_PROFILE["settle_delay_seconds"],
                "animation_asset_path": animation_asset_path,
            },
            output_path=result_path,
            host_key=DEMO_HOST_KEY,
        )

    project_plugin_state = load_project_plugin_state(workspace, DEMO_HOST_KEY)
    compatibility = dict(host_result.get("animation_compatibility") or {})
    source_profile = dict(host_result.get("source_skeleton_profile") or {})
    target_profile = dict(host_result.get("target_skeleton_profile") or {})
    tooling = dict(host_result.get("retarget_tooling") or {})
    readiness = dict(host_result.get("retarget_readiness") or {})

    if not failed_requirements:
        if not compatibility.get("mesh_skeleton_asset_path"):
            failed_requirements.append(
                make_failed_requirement(
                    "source_skeleton_missing",
                    "D4 could not resolve the imported PMX skeleton from the selected host blueprint.",
                    package_id=target_package["package_id"] if target_package else None,
                    host_blueprint_asset=target_package.get("host_blueprint_asset_path") if target_package else None,
                )
            )
        if not compatibility.get("animation_skeleton_asset_path"):
            failed_requirements.append(
                make_failed_requirement(
                    "animation_skeleton_missing",
                    "D4 could not resolve the skeleton used by the requested animation asset.",
                    animation_asset_path=animation_asset_path,
                )
            )
        if not compatibility.get("compatible"):
            plugin_enabled = dict(project_plugin_state.get("plugin_enabled") or {})
            if not plugin_enabled.get("IKRig") and tooling.get("can_author_new_retarget_assets"):
                project_plugin_state.setdefault("warnings", []).append("ikrig_not_listed_in_uproject_but_runtime_tooling_available")
            elif not plugin_enabled.get("IKRig"):
                failed_requirements.append(
                    make_failed_requirement(
                        "ikrig_plugin_disabled",
                        "AiUEdemo does not currently enable the IKRig plugin, so authoring retarget assets is blocked.",
                        uproject_path=project_plugin_state.get("uproject_path"),
                    )
                )
            if not tooling.get("can_author_new_retarget_assets"):
                failed_requirements.append(
                    make_failed_requirement(
                        "ik_retarget_tooling_unavailable",
                        "The live demo host does not expose IKRigDefinition and IKRetargeter authoring APIs yet.",
                        animation_asset_path=animation_asset_path,
                        source_skeleton_asset_path=source_profile.get("skeleton_asset_path"),
                        target_skeleton_asset_path=target_profile.get("skeleton_asset_path"),
                    )
                )
            if not readiness.get("viable"):
                failed_requirements.append(
                    make_failed_requirement(
                        "no_viable_retarget_path",
                        "D4 could not confirm a viable PMX-to-mannequin retarget path yet.",
                        blocking_reasons=list(readiness.get("blocking_reasons") or []),
                        recommended_next_steps=list(readiness.get("recommended_next_steps") or []),
                    )
                )
        elif host_result.get("status") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "retarget_preflight_host",
                    "Retarget preflight did not complete successfully even though direct compatibility was reported.",
                    result_path=str(result_path.resolve()),
                    host_invocation_error=host_invocation_error,
                    host_errors=list(host_result.get("errors") or []),
                )
            )

    if host_invocation_error and not host_result:
        failed_requirements.append(
            make_failed_requirement(
                "retarget_preflight_host",
                "Demo host retarget-preflight did not complete successfully.",
                result_path=str(result_path.resolve()),
                host_invocation_error=host_invocation_error,
            )
        )

    recommended_next_step_id, recommended_next_step_reason = choose_next_step_id(project_plugin_state, host_result)
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(status, failed_requirements, previous_report, previous_report_path, 'd4_first_complete_pass')
    counts = {
        "requested_packages": 1 if target_package else 0,
        "resolved_packages": 1 if target_package else 0,
        "source_bone_count": int(source_profile.get("bone_count") or 0),
        "target_bone_count": int(target_profile.get("bone_count") or 0),
        "matching_source_ik_rigs": len(list(tooling.get("matching_source_ik_rigs") or [])),
        "matching_target_ik_rigs": len(list(tooling.get("matching_target_ik_rigs") or [])),
        "matching_retargeters": len(list(tooling.get("matching_retargeters") or [])),
    }
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": args.workspace_config,
            "host_key": DEMO_HOST_KEY,
            "level_path": level_path,
            "package_id": target_package["package_id"] if target_package else None,
            "sample_id": target_package.get("sample_id") if target_package else None,
            "host_blueprint_asset": target_package.get("host_blueprint_asset_path") if target_package else None,
            "fixed_execution_profile": {
                **FIXED_EXECUTION_PROFILE,
                "level_path": level_path,
                "animation_asset_path": animation_asset_path,
            },
            "counts": counts,
            "failed_requirements": failed_requirements,
            "project_plugin_state": project_plugin_state,
            "engine_evidence": host_result,
            "retarget_plan": {
                "direct_animation_compatible": bool(compatibility.get("compatible")),
                "source_skeleton_asset_path": source_profile.get("skeleton_asset_path"),
                "target_skeleton_asset_path": target_profile.get("skeleton_asset_path"),
                "recommended_next_step_id": recommended_next_step_id,
                "recommended_next_step_reason": recommended_next_step_reason,
                "recommended_actions": list(readiness.get("recommended_next_steps") or []),
            },
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "upstream_report_path": str(upstream_report_path.resolve()) if upstream_report_path else None,
                "latest_report_path": str(latest_report_path.resolve()),
                "retarget_preflight_result_path": str(result_path.resolve()),
            },
        },
        "aiue_demo_retarget_preflight_report",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_demo_retarget_preflight_report",
            notes=["internal_demo_retarget_preflight_gate", "demo_host_only", "retarget_viability_evidence"],
        ),
    )
    report_path = output_root / "d4_demo_retarget_preflight_report.json"
    write_json(report_path, report_payload)
    write_json(latest_report_path, report_payload)
    print(f"D4 demo retarget preflight report written to: {report_path}")
    raise SystemExit(0 if status == "pass" else 1)

if __name__ == "__main__":
    main()



