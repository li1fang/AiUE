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
from aiue_core.schema_utils import load_json, load_workspace_config  # noqa: E402
from aiue_t2.demo_control_state import load_demo_control_state  # noqa: E402


GATE_ID = "playable_demo_e2b_credible_showcase"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_E2A_LATEST_NAME = "latest_playable_demo_e2_credibility_report.json"
DEFAULT_M1_LATEST_NAME = "latest_material_texture_proof_m1_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "evidence_mode": "aggregated_showcase_bundle",
    "consumes": [
        "playable_demo_e2_bootstrap",
        "playable_demo_e2_credibility",
        "material_texture_proof_m1",
    ],
}


def _display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2B credible showcase checkpoint.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--e2-credibility-report-path")
    parser.add_argument("--m1-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def _load_latest_required_report(workspace: dict, explicit_path: str | None, latest_name: str) -> tuple[Path, dict[str, Any]]:
    report_path = Path(explicit_path).expanduser().resolve() if explicit_path else verification_named_report_path(workspace, REPO_ROOT, latest_name)
    if not report_path.exists():
        raise FileNotFoundError(report_path)
    return report_path, load_json(report_path)


def _image_exists(path_text: str) -> bool:
    return bool(path_text) and Path(path_text).exists()


def _package_result_from_e2a(e2a_report: dict[str, Any], package_id: str) -> dict[str, Any]:
    return next(
        (
            dict(item)
            for item in list(e2a_report.get("per_package_results") or [])
            if str(item.get("package_id") or "") == package_id
        ),
        {},
    )


def _package_result_from_m1(m1_report: dict[str, Any], package_id: str) -> dict[str, Any]:
    return next(
        (
            dict(item)
            for item in list(m1_report.get("per_package_results") or [])
            if str(item.get("package_id") or "") == package_id
        ),
        {},
    )


def _slot_summary(session_package: dict[str, Any]) -> dict[str, Any]:
    slot_names = sorted(
        {
            str(item.get("slot_name") or "")
            for item in list(session_package.get("slot_bindings") or [])
            if str(item.get("slot_name") or "")
        }
    )
    return {
        "slot_names": slot_names,
        "weapon_present": "weapon" in slot_names or bool(dict(session_package.get("weapon_binding") or {})),
        "clothing_present": "clothing" in slot_names or bool(dict(session_package.get("clothing_binding") or {})),
        "fx_present": "fx" in slot_names or bool(dict(session_package.get("fx_binding") or {})),
        "host_blueprint_asset": str(session_package.get("host_blueprint_asset") or ""),
    }


def _hero_shot_payload(session_package: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evidence = dict(session_package.get("evidence") or {})
    before_image_path = str(evidence.get("hero_before_image_path") or "")
    after_image_path = str(evidence.get("hero_after_image_path") or "")
    failures: list[dict[str, Any]] = []
    if not _image_exists(before_image_path):
        failures.append(
            make_failed_requirement(
                "e2b_hero_before_missing",
                "E2B requires a hero before image for each session package.",
                package_id=session_package.get("package_id"),
                before_image_path=before_image_path,
            )
        )
    if not _image_exists(after_image_path):
        failures.append(
            make_failed_requirement(
                "e2b_hero_after_missing",
                "E2B requires a hero after image for each session package.",
                package_id=session_package.get("package_id"),
                after_image_path=after_image_path,
            )
        )
    return (
        {
            "shot_id": str(session_package.get("hero_shot_id") or ""),
            "before_image_path": before_image_path,
            "after_image_path": after_image_path,
            "full_stack_before": bool(evidence.get("hero_before_full_stack")),
            "full_stack_after": bool(evidence.get("hero_after_full_stack")),
            "motion_metrics": dict(evidence.get("motion_metrics") or {}),
        },
        failures,
    )


def _evaluate_preview_run(
    run_payload: dict[str, Any],
    *,
    package_id: str,
    request_kind: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    key_image_paths = dict(run_payload.get("key_image_paths") or {})
    primary_before = str(key_image_paths.get("primary_before") or "")
    primary_after = str(key_image_paths.get("primary_after") or "")
    credibility_summary = dict(run_payload.get("credibility_summary") or {})
    if str(run_payload.get("result_status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2b_preview_result_not_pass",
                "E2B requires the selected preview run to pass.",
                package_id=package_id,
                request_kind=request_kind,
                result_status=run_payload.get("result_status"),
                result_json_path=run_payload.get("result_json_path"),
            )
        )
    if not _image_exists(primary_before) or not _image_exists(primary_after):
        failures.append(
            make_failed_requirement(
                "e2b_preview_images_missing",
                "E2B requires before and after key images for each selected preview run.",
                package_id=package_id,
                request_kind=request_kind,
                primary_before=primary_before,
                primary_after=primary_after,
            )
        )
    if not bool(credibility_summary.get("subject_visible")):
        failures.append(
            make_failed_requirement(
                "e2b_subject_not_visible",
                "E2B requires the subject to remain visible in the selected preview evidence.",
                package_id=package_id,
                request_kind=request_kind,
                credibility_summary=credibility_summary,
            )
        )
    required_flag = "action_motion_verified" if request_kind == "action_preview" else "animation_pose_verified"
    if not bool(credibility_summary.get(required_flag)):
        failures.append(
            make_failed_requirement(
                "e2b_preview_credibility_missing",
                "E2B requires the selected preview evidence to retain its credibility proof.",
                package_id=package_id,
                request_kind=request_kind,
                required_flag=required_flag,
                credibility_summary=credibility_summary,
            )
        )
    return (
        {
            "request_kind": request_kind,
            "request_json_path": str(run_payload.get("request_json_path") or ""),
            "result_json_path": str(run_payload.get("result_json_path") or ""),
            "result_status": str(run_payload.get("result_status") or ""),
            "generated_at_utc": str(run_payload.get("generated_at_utc") or ""),
            "host_key": str(run_payload.get("host_key") or ""),
            "key_image_paths": key_image_paths,
            "credibility_summary": credibility_summary,
            "status": "pass" if not failures else "fail",
        },
        failures,
    )


def _evaluate_material_reference(m1_package: dict[str, Any], *, package_id: str, m1_report_path: Path | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    if not m1_package:
        failures.append(
            make_failed_requirement(
                "e2b_material_reference_missing",
                "E2B requires an M1 material proof result for each showcased package.",
                package_id=package_id,
                m1_report_path=_display_path(m1_report_path),
            )
        )
        return (
            {
                "status": "fail",
                "m1_report_path": _display_path(m1_report_path),
            },
            failures,
        )
    import_evidence = dict(m1_package.get("import_evidence") or {})
    character_import = dict(import_evidence.get("character") or {})
    weapon_import = dict(import_evidence.get("default_weapon") or {})
    if str(m1_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2b_material_reference_not_pass",
                "E2B requires M1 material proof to pass before a credible showcase can be assembled.",
                package_id=package_id,
                m1_report_path=_display_path(m1_report_path),
            )
        )
    return (
        {
            "status": "pass" if not failures else "fail",
            "m1_report_path": _display_path(m1_report_path),
            "character_texture_counts": {
                "expected": int(character_import.get("expected_texture_count") or 0),
                "imported": int(character_import.get("imported_texture_count") or 0),
            },
            "weapon_texture_counts": {
                "expected": int(weapon_import.get("expected_texture_count") or 0),
                "imported": int(weapon_import.get("imported_texture_count") or 0),
            },
            "host_visual_material_evidence": dict(dict(m1_package.get("host_visual_evidence") or {}).get("material_evidence") or {}),
        },
        failures,
    )


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2b_session_manifest_missing",
                "E2B requires the latest E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    try:
        e2a_report_path, e2a_report = _load_latest_required_report(
            workspace,
            args.e2_credibility_report_path,
            DEFAULT_E2A_LATEST_NAME,
        )
    except FileNotFoundError as exc:
        failed_requirements.append(
            make_failed_requirement(
                "e2b_e2a_report_missing",
                "E2B requires the latest playable demo E2 credibility report.",
                report_path=str(exc),
            )
        )
        e2a_report_path = Path(args.e2_credibility_report_path).expanduser().resolve() if args.e2_credibility_report_path else None
        e2a_report = {}
    try:
        m1_report_path, m1_report = _load_latest_required_report(
            workspace,
            args.m1_report_path,
            DEFAULT_M1_LATEST_NAME,
        )
    except FileNotFoundError as exc:
        failed_requirements.append(
            make_failed_requirement(
                "e2b_m1_report_missing",
                "E2B requires the latest M1 material / texture proof report.",
                report_path=str(exc),
            )
        )
        m1_report_path = Path(args.m1_report_path).expanduser().resolve() if args.m1_report_path else None
        m1_report = {}

    if e2a_report and str(e2a_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2b_e2a_not_pass",
                "E2B requires E2 credibility to pass before building the showcase bundle.",
                e2a_report_path=str(e2a_report_path.resolve()),
                e2a_status=e2a_report.get("status"),
            )
        )
    if m1_report and str(m1_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "e2b_m1_not_pass",
                "E2B requires M1 to pass before building the showcase bundle.",
                m1_report_path=str(m1_report_path.resolve()),
                m1_status=m1_report.get("status"),
            )
        )

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    if len(resolved_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2b_required_package_count",
                "E2B requires exactly two ready bundles in the E2 session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    control_state = load_demo_control_state(session_manifest_path)
    last_runs_by_package = dict(control_state.get("last_runs_by_package") or {})
    per_package_results: list[dict[str, Any]] = []
    for session_package in resolved_packages:
        package_id = str(session_package.get("package_id") or "")
        package_failures: list[dict[str, Any]] = []
        package_runs = dict(last_runs_by_package.get(package_id) or {})

        hero_shot, hero_failures = _hero_shot_payload(session_package)
        action_preview, action_failures = _evaluate_preview_run(
            dict(package_runs.get("action_preview") or {}),
            package_id=package_id,
            request_kind="action_preview",
        )
        animation_preview, animation_failures = _evaluate_preview_run(
            dict(package_runs.get("animation_preview") or {}),
            package_id=package_id,
            request_kind="animation_preview",
        )
        material_reference, material_failures = _evaluate_material_reference(
            _package_result_from_m1(m1_report, package_id),
            package_id=package_id,
            m1_report_path=m1_report_path,
        )
        slot_summary = _slot_summary(session_package)
        if not all(slot_summary.get(key) for key in ("weapon_present", "clothing_present", "fx_present")):
            package_failures.append(
                make_failed_requirement(
                    "e2b_slot_stack_incomplete",
                    "E2B requires the showcased package to expose weapon, clothing, and FX bindings in the session payload.",
                    package_id=package_id,
                    slot_summary=slot_summary,
                )
            )
        e2a_package = _package_result_from_e2a(e2a_report, package_id)
        if e2a_package and str(e2a_package.get("status") or "") != "pass":
            package_failures.append(
                make_failed_requirement(
                    "e2b_e2a_package_not_pass",
                    "E2B requires the matching E2 credibility package result to pass.",
                    package_id=package_id,
                    e2a_status=e2a_package.get("status"),
                )
            )

        package_failures.extend(hero_failures)
        package_failures.extend(action_failures)
        package_failures.extend(animation_failures)
        package_failures.extend(material_failures)
        per_package_results.append(
            {
                "package_id": package_id,
                "sample_id": str(session_package.get("sample_id") or ""),
                "status": "pass" if not package_failures else "fail",
                "hero_shot": hero_shot,
                "action_preview": action_preview,
                "animation_preview": animation_preview,
                "slot_summary": slot_summary,
                "material_proof_reference": material_reference,
                "errors": package_failures,
            }
        )
        failed_requirements.extend(package_failures)

    counts = {
        "resolved_package_count": len(resolved_packages),
        "passing_packages": sum(1 for item in per_package_results if str(item.get("status") or "") == "pass"),
        "hero_shots_present": sum(1 for item in per_package_results if _image_exists(str(dict(item.get("hero_shot") or {}).get("before_image_path") or "")) and _image_exists(str(dict(item.get("hero_shot") or {}).get("after_image_path") or ""))),
        "action_motion_verified": sum(
            1
            for item in per_package_results
            if bool(dict(dict(item.get("action_preview") or {}).get("credibility_summary") or {}).get("action_motion_verified"))
        ),
        "animation_pose_verified": sum(
            1
            for item in per_package_results
            if bool(dict(dict(item.get("animation_preview") or {}).get("credibility_summary") or {}).get("animation_pose_verified"))
        ),
        "packages_with_material_reference": sum(
            1 for item in per_package_results if str(dict(item.get("material_proof_reference") or {}).get("status") or "") == "pass"
        ),
    }
    discussion_signal = build_discussion_signal(
        "pass" if not failed_requirements else "fail",
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_playable_demo_e2b_credible_showcase_pass",
    )
    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": "pass" if not failed_requirements else "fail",
            "success": not failed_requirements,
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_session_manifest": str(session_manifest_path.resolve()) if session_manifest_path.exists() else "",
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "per_package_results": per_package_results,
            "control_state": {
                "status": str(control_state.get("status") or ""),
                "control_state_path": str(control_state.get("control_state_path") or ""),
            },
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "e2a_report_path": _display_path(e2a_report_path),
                "m1_report_path": _display_path(m1_report_path),
                "control_state_path": str(control_state.get("control_state_path") or ""),
            },
        },
        "aiue_playable_demo_e2b_credible_showcase_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_playable_demo_e2b_credible_showcase_report",
            notes=[
                "internal_e2b_showcase_bundle",
                "consumes_m1_material_proof",
                "demo_line_not_active_validation_authority",
            ],
        ),
    )
    report_path = output_root / "playable_demo_e2b_credible_showcase_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if not failed_requirements else 1


if __name__ == "__main__":
    raise SystemExit(main())
