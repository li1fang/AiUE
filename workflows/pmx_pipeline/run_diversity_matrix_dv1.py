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
from aiue_t1.diversity_matrix import build_diversity_axis  # noqa: E402
from aiue_t2.demo_control_state import build_control_run_summary  # noqa: E402
from aiue_t2.demo_request_runner import (  # noqa: E402
    default_request_json_path,
    default_result_json_path,
    invoke_demo_request,
    load_demo_request_selection,
)


GATE_ID = "diversity_matrix_dv1"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_E2A_LATEST_NAME = "latest_playable_demo_e2_credibility_report.json"
DEFAULT_M1_LATEST_NAME = "latest_material_texture_proof_m1_report.json"
FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "action_selection": "all_available",
    "animation_selection": "all_available",
    "request_driver": "demo_request_runner",
    "prerequisites": [
        "playable_demo_e2_credibility",
        "material_texture_proof_m1",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE automated diversity matrix DV1 report.")
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


def _selected_preset_values(package_payload: dict[str, Any], preset_key: str) -> list[str]:
    return [
        str(item.get("preset_id") or "")
        for item in list(package_payload.get(preset_key) or [])
        if str(item.get("preset_id") or "")
    ]


def _primary_slot_package_id(package_payload: dict[str, Any], field_name: str) -> str:
    return str(dict(package_payload.get(field_name) or {}).get("item_package_id") or "")


def _evaluate_run_summary(
    *,
    package_id: str,
    request_kind: str,
    expected_action_preset_id: str,
    expected_animation_preset_id: str,
    invocation: dict[str, Any],
    run_summary: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    result_status = str(run_summary.get("result_status") or "")
    request_json_path = str(run_summary.get("request_json_path") or "")
    result_json_path = str(run_summary.get("result_json_path") or "")
    credibility_summary = dict(run_summary.get("credibility_summary") or {})
    selected_action_preset_id = str(run_summary.get("selected_action_preset_id") or "")
    selected_animation_preset_id = str(run_summary.get("selected_animation_preset_id") or "")

    if str(invocation.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "dv1_request_invoke_failed",
                "DV1 requires each matrix request invoke to report pass.",
                package_id=package_id,
                request_kind=request_kind,
                invocation_status=invocation.get("status"),
                invocation=invocation,
            )
        )
    if selected_action_preset_id != expected_action_preset_id:
        failures.append(
            make_failed_requirement(
                "dv1_action_preset_mismatch",
                "DV1 requires the recorded action preset to match the requested preset.",
                package_id=package_id,
                request_kind=request_kind,
                expected_action_preset_id=expected_action_preset_id,
                actual_action_preset_id=selected_action_preset_id,
            )
        )
    if selected_animation_preset_id != expected_animation_preset_id:
        failures.append(
            make_failed_requirement(
                "dv1_animation_preset_mismatch",
                "DV1 requires the recorded animation preset to match the requested preset.",
                package_id=package_id,
                request_kind=request_kind,
                expected_animation_preset_id=expected_animation_preset_id,
                actual_animation_preset_id=selected_animation_preset_id,
            )
        )
    if not request_json_path or not Path(request_json_path).exists():
        failures.append(
            make_failed_requirement(
                "dv1_request_json_missing",
                "DV1 requires each matrix run to leave behind a request JSON artifact.",
                package_id=package_id,
                request_kind=request_kind,
                request_json_path=request_json_path,
            )
        )
    if not result_json_path or not Path(result_json_path).exists():
        failures.append(
            make_failed_requirement(
                "dv1_result_json_missing",
                "DV1 requires each matrix run to leave behind a result JSON artifact.",
                package_id=package_id,
                request_kind=request_kind,
                result_json_path=result_json_path,
            )
        )
    if result_status != "pass":
        failures.append(
            make_failed_requirement(
                "dv1_result_not_pass",
                "DV1 requires each matrix run result to pass.",
                package_id=package_id,
                request_kind=request_kind,
                result_status=result_status,
                result_json_path=result_json_path,
            )
        )
    if not bool(credibility_summary.get("subject_visible")):
        failures.append(
            make_failed_requirement(
                "dv1_subject_not_visible",
                "DV1 requires the subject to remain visible during each matrix run.",
                package_id=package_id,
                request_kind=request_kind,
                credibility_summary=credibility_summary,
            )
        )
    required_flag = "action_motion_verified" if request_kind == "action_preview" else "animation_pose_verified"
    if not bool(credibility_summary.get(required_flag)):
        failures.append(
            make_failed_requirement(
                "dv1_credibility_not_verified",
                "DV1 requires each matrix run to satisfy the request-specific credibility proof.",
                package_id=package_id,
                request_kind=request_kind,
                required_flag=required_flag,
                credibility_summary=credibility_summary,
            )
        )
    return (
        {
            "status": "pass" if not failures else "fail",
            "request_kind": request_kind,
            "selected_action_preset_id": selected_action_preset_id,
            "selected_animation_preset_id": selected_animation_preset_id,
            "request_json_path": request_json_path,
            "result_json_path": result_json_path,
            "result_status": result_status,
            "host_key": str(run_summary.get("host_key") or ""),
            "generated_at_utc": str(run_summary.get("generated_at_utc") or ""),
            "key_image_paths": dict(run_summary.get("key_image_paths") or {}),
            "credibility_summary": credibility_summary,
            "warning_flags": list(credibility_summary.get("warning_flags") or []),
        },
        failures,
    )


def _invoke_matrix_entry(
    *,
    repo_root: Path,
    workspace_config_path: Path,
    session_manifest_path: Path,
    package_id: str,
    action_preset_id: str,
    animation_preset_id: str,
    request_kind: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    selection = load_demo_request_selection(
        repo_root=repo_root,
        session_manifest_path=session_manifest_path,
        package_id=package_id,
        action_preset_id=action_preset_id,
        animation_preset_id=animation_preset_id,
        request_kind=request_kind,
    )
    request_json_path = default_request_json_path(selection)
    result_json_path = default_result_json_path(selection, dry_run=False)
    try:
        invocation = invoke_demo_request(
            selection,
            workspace_config=workspace_config_path,
            dry_run=False,
        )
    except Exception as exc:
        return (
            {
                "status": "fail",
                "request_kind": request_kind,
                "selected_action_preset_id": action_preset_id,
                "selected_animation_preset_id": animation_preset_id,
                "request_json_path": str(request_json_path.resolve()) if request_json_path.exists() else "",
                "result_json_path": str(result_json_path.resolve()) if result_json_path.exists() else "",
                "result_status": "error",
                "host_key": str(selection.request_payload.get("host_key") or ""),
                "generated_at_utc": now_utc(),
                "key_image_paths": {},
                "credibility_summary": {},
                "warning_flags": ["invoke_exception"],
            },
            [
                make_failed_requirement(
                    "dv1_request_invoke_exception",
                    "DV1 requires each matrix invoke to complete without a host bridge exception.",
                    package_id=package_id,
                    request_kind=request_kind,
                    selected_action_preset_id=action_preset_id,
                    selected_animation_preset_id=animation_preset_id,
                    request_json_path=str(request_json_path.resolve()) if request_json_path.exists() else "",
                    result_json_path=str(result_json_path.resolve()) if result_json_path.exists() else "",
                    error=str(exc),
                )
            ],
        )
    run_summary = build_control_run_summary(
        request_kind=selection.request_kind,
        operation="dv1_matrix_invoke",
        selected_package_id=selection.selected_package_id,
        selected_action_preset_id=selection.selected_action_preset_id,
        selected_animation_preset_id=selection.selected_animation_preset_id,
        invocation=invocation,
    )
    return _evaluate_run_summary(
        package_id=package_id,
        request_kind=request_kind,
        expected_action_preset_id=action_preset_id,
        expected_animation_preset_id=animation_preset_id,
        invocation=invocation,
        run_summary=run_summary,
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
        e2a_report_path, e2a_report = _load_latest_required_report(
            workspace,
            args.e2_credibility_report_path,
            DEFAULT_E2A_LATEST_NAME,
        )
    except FileNotFoundError as exc:
        failed_requirements.append(
            make_failed_requirement(
                "dv1_e2a_report_missing",
                "DV1 requires the latest E2 credibility report before expanding diversity coverage.",
                report_path=str(exc),
            )
        )
        e2a_report_path = None
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
                "dv1_m1_report_missing",
                "DV1 requires the latest M1 material proof report before expanding diversity coverage.",
                report_path=str(exc),
            )
        )
        m1_report_path = None
        m1_report = {}

    if e2a_report and str(e2a_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "dv1_e2a_not_pass",
                "DV1 requires the E2 credibility prerequisite to pass.",
                e2a_report_path=str((e2a_report_path or Path("")).resolve()) if e2a_report_path else "",
                e2a_status=e2a_report.get("status"),
            )
        )
    if m1_report and str(m1_report.get("status") or "") != "pass":
        failed_requirements.append(
            make_failed_requirement(
                "dv1_m1_not_pass",
                "DV1 requires the M1 material proof prerequisite to pass.",
                m1_report_path=str((m1_report_path or Path("")).resolve()) if m1_report_path else "",
                m1_status=m1_report.get("status"),
            )
        )

    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "dv1_session_manifest_missing",
                "DV1 requires the latest playable demo E2 session manifest.",
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
                "dv1_required_package_count_mismatch",
                "DV1 requires exactly two ready bundles in the session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    per_package_results: list[dict[str, Any]] = []
    distinct_character_ids: set[str] = set()
    distinct_weapon_ids: set[str] = set()
    distinct_clothing_ids: set[str] = set()
    distinct_fx_ids: set[str] = set()
    verified_action_presets: set[str] = set()
    verified_animation_presets: set[str] = set()

    for package_payload in resolved_packages:
        package_id = str(package_payload.get("package_id") or "")
        sample_id = str(package_payload.get("sample_id") or "")
        host_blueprint_asset = str(package_payload.get("host_blueprint_asset") or "")
        weapon_item_package_id = _primary_slot_package_id(package_payload, "weapon_binding")
        clothing_item_package_id = _primary_slot_package_id(package_payload, "clothing_binding")
        fx_item_package_id = _primary_slot_package_id(package_payload, "fx_binding")
        action_preset_ids = _selected_preset_values(package_payload, "action_presets")
        animation_preset_ids = _selected_preset_values(package_payload, "animation_presets")

        package_failures: list[dict[str, Any]] = []
        action_matrix_runs: list[dict[str, Any]] = []
        animation_matrix_runs: list[dict[str, Any]] = []

        if package_id:
            distinct_character_ids.add(package_id)
        if weapon_item_package_id:
            distinct_weapon_ids.add(weapon_item_package_id)
        if clothing_item_package_id:
            distinct_clothing_ids.add(clothing_item_package_id)
        if fx_item_package_id:
            distinct_fx_ids.add(fx_item_package_id)

        if not action_preset_ids:
            package_failures.append(
                make_failed_requirement(
                    "dv1_action_presets_missing",
                    "DV1 requires at least one action preset for each package.",
                    package_id=package_id,
                )
            )
        if not animation_preset_ids:
            package_failures.append(
                make_failed_requirement(
                    "dv1_animation_presets_missing",
                    "DV1 requires at least one animation preset for each package.",
                    package_id=package_id,
                )
            )

        if not package_failures:
            anchor_action_preset_id = action_preset_ids[0]
            anchor_animation_preset_id = animation_preset_ids[0]

            for action_preset_id in action_preset_ids:
                run_result, run_failures = _invoke_matrix_entry(
                    repo_root=repo_root,
                    workspace_config_path=workspace_config_path,
                    session_manifest_path=session_manifest_path,
                    package_id=package_id,
                    action_preset_id=action_preset_id,
                    animation_preset_id=anchor_animation_preset_id,
                    request_kind="action_preview",
                )
                action_matrix_runs.append(run_result)
                if str(run_result.get("status") or "") == "pass":
                    verified_action_presets.add(action_preset_id)
                package_failures.extend(run_failures)

            for animation_preset_id in animation_preset_ids:
                run_result, run_failures = _invoke_matrix_entry(
                    repo_root=repo_root,
                    workspace_config_path=workspace_config_path,
                    session_manifest_path=session_manifest_path,
                    package_id=package_id,
                    action_preset_id=anchor_action_preset_id,
                    animation_preset_id=animation_preset_id,
                    request_kind="animation_preview",
                )
                animation_matrix_runs.append(run_result)
                if str(run_result.get("status") or "") == "pass":
                    verified_animation_presets.add(animation_preset_id)
                package_failures.extend(run_failures)

        per_package_results.append(
            {
                "package_id": package_id,
                "sample_id": sample_id,
                "host_blueprint_asset": host_blueprint_asset,
                "slot_variants": {
                    "weapon_item_package_id": weapon_item_package_id,
                    "clothing_item_package_id": clothing_item_package_id,
                    "fx_item_package_id": fx_item_package_id,
                },
                "available_action_preset_ids": action_preset_ids,
                "available_animation_preset_ids": animation_preset_ids,
                "action_matrix_runs": action_matrix_runs,
                "animation_matrix_runs": animation_matrix_runs,
                "status": "pass" if not package_failures else "fail",
                "errors": package_failures,
            }
        )
        failed_requirements.extend(package_failures)

    coverage_axes = [
        build_diversity_axis("character_variant_diversity", sorted(distinct_character_ids), noun_phrase="character bundles"),
        build_diversity_axis("weapon_variant_diversity", sorted(distinct_weapon_ids), noun_phrase="weapon bundles"),
        build_diversity_axis("clothing_fixture_diversity", sorted(distinct_clothing_ids), noun_phrase="clothing fixtures"),
        build_diversity_axis("fx_fixture_diversity", sorted(distinct_fx_ids), noun_phrase="FX fixtures"),
        build_diversity_axis("action_variation", sorted(verified_action_presets), noun_phrase="verified action presets"),
        build_diversity_axis("animation_variation", sorted(verified_animation_presets), noun_phrase="verified animation presets"),
    ]
    distinct_counts = {
        "character_variant_diversity": int(_axis_entry_by_id(coverage_axes, "character_variant_diversity").get("distinct_count") or 0),
        "weapon_variant_diversity": int(_axis_entry_by_id(coverage_axes, "weapon_variant_diversity").get("distinct_count") or 0),
        "clothing_fixture_diversity": int(_axis_entry_by_id(coverage_axes, "clothing_fixture_diversity").get("distinct_count") or 0),
        "fx_fixture_diversity": int(_axis_entry_by_id(coverage_axes, "fx_fixture_diversity").get("distinct_count") or 0),
        "action_variation": int(_axis_entry_by_id(coverage_axes, "action_variation").get("distinct_count") or 0),
        "animation_variation": int(_axis_entry_by_id(coverage_axes, "animation_variation").get("distinct_count") or 0),
    }
    action_entries = [
        dict(entry)
        for package in per_package_results
        for entry in list(package.get("action_matrix_runs") or [])
    ]
    animation_entries = [
        dict(entry)
        for package in per_package_results
        for entry in list(package.get("animation_matrix_runs") or [])
    ]
    counts = {
        "resolved_package_count": len(resolved_packages),
        "matrix_entry_count": len(action_entries) + len(animation_entries),
        "passing_matrix_entries": sum(
            1 for entry in action_entries + animation_entries if str(entry.get("status") or "") == "pass"
        ),
        "action_entry_count": len(action_entries),
        "animation_entry_count": len(animation_entries),
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
        "first_complete_diversity_matrix_dv1_pass",
    )

    report_payload = with_report_envelope(
        {
            "generated_at_utc": now_utc(),
            "gate_id": GATE_ID,
            "status": status,
            "success": status == "pass",
            "workspace_config": str(workspace_config_path),
            "source_session_manifest": str(session_manifest_path.resolve()) if session_manifest_path.exists() else "",
            "fixed_execution_profile": dict(FIXED_EXECUTION_PROFILE),
            "counts": counts,
            "distinct_counts": distinct_counts,
            "coverage_axes": coverage_axes,
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "e2a_report_path": str(e2a_report_path.resolve()) if e2a_report_path else "",
                "m1_report_path": str(m1_report_path.resolve()) if m1_report_path else "",
            },
        },
        "aiue_diversity_matrix_dv1_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            "aiue_diversity_matrix_dv1_report",
            notes=[
                "automated_diversity_truth_source",
                "updates_test_governance_coverage_axes",
                "partial_axes_do_not_fail_matrix_capture",
            ],
        ),
    )
    report_path = output_root / "diversity_matrix_dv1_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)
    print(report_path)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
