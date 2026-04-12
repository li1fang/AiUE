from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from _bootstrap import ensure_aiue_paths

REPO_ROOT = ensure_aiue_paths()

from _demo_common import default_named_verification_report_path, resolve_report_path
from _gate_common import (
    build_discussion_signal,
    default_latest_report_path,
    default_output_root,
    make_failed_requirement,
    now_utc,
    repo_root_from_workspace,
    write_report_pair,
)

from aiue_core.report_writer import make_compatibility_block, with_report_envelope
from aiue_core.schema_utils import load_json, load_workspace_config, write_json


GATE_ID = "playable_demo_e2c_credible_showcase_polish"
DEFAULT_SESSION_MANIFEST_NAME = "playable_demo_e2_session.json"
DEFAULT_POLISH_STATE_NAME = "playable_demo_e2_polish_state.json"
DEFAULT_E2B_LATEST_NAME = "latest_playable_demo_e2b_credible_showcase_report.json"
DEFAULT_DV2_LATEST_NAME = "latest_diversity_matrix_dv2_report.json"
DEFAULT_CURATED_REVIEW_LATEST_NAME = "latest_playable_demo_e2_curated_review_report.json"
DEFAULT_REVIEW_NAVIGATION_LATEST_NAME = "latest_playable_demo_e2_review_navigation_report.json"
DEFAULT_REVIEW_REPLAY_LATEST_NAME = "latest_playable_demo_e2_review_replay_report.json"
DEFAULT_REVIEW_HISTORY_LATEST_NAME = "latest_playable_demo_e2_review_history_report.json"
DEFAULT_REVIEW_COMPARE_LATEST_NAME = "latest_playable_demo_e2_review_compare_report.json"
DEFAULT_REVIEW_COMPARE_BROWSE_LATEST_NAME = "latest_playable_demo_e2_review_compare_browse_report.json"

FIXED_EXECUTION_PROFILE = {
    "host_key": "demo",
    "mode": "editor_rendered",
    "required_package_count": 2,
    "evidence_mode": "aggregated_polish_bundle",
    "consumes": [
        "playable_demo_e2b_credible_showcase",
        "diversity_matrix_dv2",
        "playable_demo_e2_curated_review",
        "playable_demo_e2_review_navigation",
        "playable_demo_e2_review_replay",
        "playable_demo_e2_review_history",
        "playable_demo_e2_review_compare",
        "playable_demo_e2_review_compare_browse",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the AiUE E2C credible showcase polish checkpoint.")
    parser.add_argument("--workspace-config", required=True)
    parser.add_argument("--session-manifest-path")
    parser.add_argument("--e2b-report-path")
    parser.add_argument("--dv2-report-path")
    parser.add_argument("--curated-review-report-path")
    parser.add_argument("--review-navigation-report-path")
    parser.add_argument("--review-replay-report-path")
    parser.add_argument("--review-history-report-path")
    parser.add_argument("--review-compare-report-path")
    parser.add_argument("--review-compare-browse-report-path")
    parser.add_argument("--output-root")
    parser.add_argument("--latest-report-path")
    parser.add_argument("--latest-polish-state-path")
    return parser.parse_args()


def default_session_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Saved" / "demo" / "e2" / "latest" / DEFAULT_SESSION_MANIFEST_NAME


def default_latest_polish_state_path(repo_root: Path) -> Path:
    latest_root = repo_root / "Saved" / "demo" / "e2" / "latest"
    latest_root.mkdir(parents=True, exist_ok=True)
    return latest_root / DEFAULT_POLISH_STATE_NAME


def _load_required_report(
    workspace: dict[str, Any],
    *,
    explicit_path: str | None,
    latest_name: str,
    missing_message: str,
) -> tuple[Path | None, dict[str, Any], list[dict[str, Any]]]:
    failures: list[dict[str, Any]] = []
    try:
        report_path = resolve_report_path(
            explicit_path,
            default_named_verification_report_path(workspace, REPO_ROOT, latest_name),
            missing_message,
        )
    except FileNotFoundError as exc:
        failures.append(
            make_failed_requirement(
                "e2c_required_report_missing",
                missing_message,
                report_name=latest_name,
                report_path=str(exc),
            )
        )
        return None, {}, failures
    return report_path, load_json(report_path), failures


def _image_exists(path_text: str) -> bool:
    return bool(path_text) and Path(path_text).expanduser().exists()


def _find_package_result(report_payload: dict[str, Any], package_id: str) -> dict[str, Any]:
    for item in list(report_payload.get("per_package_results") or []):
        if str(item.get("package_id") or "") == package_id:
            return dict(item)
    return {}


def _display_path(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve())
    except Exception:
        return str(path)


def _review_status(review_payload: dict[str, Any]) -> str:
    return str(review_payload.get("status") or "missing")


def _browse_pair_count(browse_payload: dict[str, Any]) -> int:
    results = [dict(item) for item in list(browse_payload.get("browse_focus_results") or [])]
    return len(results)


def _all_browse_pass(browse_payload: dict[str, Any]) -> bool:
    results = [dict(item) for item in list(browse_payload.get("browse_focus_results") or [])]
    return bool(results) and all(str(item.get("status") or "") == "pass" for item in results)


def _history_focus(history_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(dict(history_payload.get("history_focus_result") or {}).get("history_focus") or {})


def _compare_focus(compare_payload: dict[str, Any]) -> dict[str, Any]:
    return dict(compare_payload.get("compare_focus") or {})


def _find_targeted_run(dv2_package: dict[str, Any], axis_id: str) -> dict[str, Any]:
    for item in list(dv2_package.get("targeted_runs") or []):
        if str(item.get("axis_id") or "") == axis_id:
            return dict(item)
    return {}


def _texture_counts_ready(count_payload: dict[str, Any]) -> bool:
    expected = count_payload.get("expected")
    imported = count_payload.get("imported")
    if expected is None or imported is None:
        return False
    try:
        expected_value = int(expected)
        imported_value = int(imported)
    except (TypeError, ValueError):
        return False
    return expected_value >= 0 and imported_value >= expected_value


def _component_material_evidence_ready(component_payload: dict[str, Any]) -> bool:
    if not component_payload:
        return False
    try:
        material_slot_count = int(component_payload.get("material_slot_count") or 0)
    except (TypeError, ValueError):
        material_slot_count = 0
    material_asset_paths = [str(path) for path in list(component_payload.get("material_asset_paths") or []) if str(path)]
    non_empty_material_asset_paths = [
        str(path) for path in list(component_payload.get("non_empty_material_asset_paths") or []) if str(path)
    ]
    texture_summary = dict(component_payload.get("texture_reference_summary") or {})
    texture_asset_paths = [str(path) for path in list(texture_summary.get("texture_asset_paths") or []) if str(path)]
    return bool(material_slot_count > 0 or material_asset_paths or non_empty_material_asset_paths or texture_asset_paths)


def _host_visual_material_evidence_ready(host_payload: dict[str, Any]) -> bool:
    if not host_payload:
        return False
    main_mesh_ready = _component_material_evidence_ready(dict(host_payload.get("main_mesh") or {}))
    weapon_mesh_ready = _component_material_evidence_ready(dict(host_payload.get("weapon_mesh") or {}))
    managed_slots = {
        str(slot_name): dict(slot_payload or {})
        for slot_name, slot_payload in dict(host_payload.get("managed_slots") or {}).items()
    }
    managed_slot_ready = any(_component_material_evidence_ready(slot_payload) for slot_payload in managed_slots.values())
    return main_mesh_ready and (weapon_mesh_ready or managed_slot_ready)


def _material_reference_ready(material_reference: dict[str, Any]) -> bool:
    if not material_reference:
        return False
    if "material_evidence_present" in material_reference:
        return bool(material_reference.get("material_evidence_present"))
    if str(material_reference.get("status") or "") != "pass":
        return False
    if _host_visual_material_evidence_ready(dict(material_reference.get("host_visual_material_evidence") or {})):
        return True
    if _texture_counts_ready(dict(material_reference.get("character_texture_counts") or {})):
        return True
    if _texture_counts_ready(dict(material_reference.get("weapon_texture_counts") or {})):
        return True
    return bool(material_reference.get("m1_report_path"))


def _selected_pair_payload(browse_payload: dict[str, Any]) -> dict[str, Any]:
    results = [dict(item) for item in list(browse_payload.get("browse_focus_results") or [])]
    if not results:
        return {}
    selected = next((item for item in results if int(item.get("selected_pair_index") or -1) == 0), {})
    if selected:
        return dict(selected.get("selected_compare_pair") or {})
    return dict(results[0].get("selected_compare_pair") or {})


def _package_polish_result(
    *,
    session_package: dict[str, Any],
    e2b_package: dict[str, Any],
    dv2_package: dict[str, Any],
    curated_package: dict[str, Any],
    navigation_package: dict[str, Any],
    replay_package: dict[str, Any],
    history_package: dict[str, Any],
    compare_package: dict[str, Any],
    browse_package: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    package_id = str(session_package.get("package_id") or "")
    failures: list[dict[str, Any]] = []

    hero_shot = dict(e2b_package.get("hero_shot") or {})
    material_reference = dict(e2b_package.get("material_proof_reference") or {})
    action_preview = dict(e2b_package.get("action_preview") or {})
    animation_preview = dict(e2b_package.get("animation_preview") or {})
    review_focus = dict(navigation_package.get("review_focus") or {})
    history_focus = _history_focus(history_package)
    compare_focus = _compare_focus(compare_package)
    compare_pair = _selected_pair_payload(browse_package)
    action_replay = dict(replay_package.get("action_replay") or {})
    animation_replay = dict(replay_package.get("animation_replay") or {})
    clothing_variant = _find_targeted_run(dv2_package, "clothing_fixture_diversity")
    fx_variant = _find_targeted_run(dv2_package, "fx_fixture_diversity")
    action_variant = _find_targeted_run(dv2_package, "action_variation")
    material_ready = _material_reference_ready(material_reference)

    if str(e2b_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_e2b_package_missing_or_not_pass",
                "E2C requires E2B showcase evidence for every session package.",
                package_id=package_id,
                e2b_status=e2b_package.get("status"),
            )
        )
    if str(curated_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_curated_review_not_pass",
                "E2C requires curated review to pass for every package.",
                package_id=package_id,
                curated_review_status=curated_package.get("status"),
            )
        )
    if str(navigation_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_navigation_not_pass",
                "E2C requires review navigation to pass for every package.",
                package_id=package_id,
                review_navigation_status=navigation_package.get("status"),
            )
        )
    if str(replay_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_replay_not_pass",
                "E2C requires review replay to pass for every package.",
                package_id=package_id,
                review_replay_status=replay_package.get("status"),
            )
        )
    if str(history_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_history_not_pass",
                "E2C requires review history to pass for every package.",
                package_id=package_id,
                review_history_status=history_package.get("status"),
            )
        )
    if str(compare_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_compare_not_pass",
                "E2C requires review compare to pass for every package.",
                package_id=package_id,
                review_compare_status=compare_package.get("status"),
            )
        )
    if str(browse_package.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_compare_browse_not_pass",
                "E2C requires compare browse to pass for every package.",
                package_id=package_id,
                review_compare_browse_status=browse_package.get("status"),
            )
        )

    key_images = {
        "hero_before": str(hero_shot.get("before_image_path") or ""),
        "hero_after": str(hero_shot.get("after_image_path") or ""),
        "action_after": str(review_focus.get("action_primary_after_image_path") or ""),
        "animation_after": str(review_focus.get("animation_primary_after_image_path") or ""),
        "compare_action_after": str(dict(compare_pair.get("action_event") or {}).get("key_image_paths", {}).get("primary_after") or ""),
        "compare_animation_after": str(dict(compare_pair.get("animation_event") or {}).get("key_image_paths", {}).get("primary_after") or ""),
    }
    for image_role, image_path in key_images.items():
        if not _image_exists(image_path):
            failures.append(
                make_failed_requirement(
                    "e2c_key_image_missing",
                    "E2C requires the showcase key images to remain available on disk.",
                    package_id=package_id,
                    image_role=image_role,
                    image_path=image_path,
                )
            )

    if not material_ready:
        failures.append(
            make_failed_requirement(
                "e2c_material_reference_missing",
                "E2C requires material proof evidence for every package.",
                package_id=package_id,
                material_reference=material_reference,
            )
        )

    if not clothing_variant or str(clothing_variant.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_dv2_clothing_variant_missing",
                "E2C requires DV2 clothing diversity evidence for every package.",
                package_id=package_id,
                clothing_variant_status=clothing_variant.get("status"),
            )
        )
    if not fx_variant or str(fx_variant.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_dv2_fx_variant_missing",
                "E2C requires DV2 FX diversity evidence for every package.",
                package_id=package_id,
                fx_variant_status=fx_variant.get("status"),
            )
        )
    if not action_variant or str(action_variant.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_dv2_action_variant_missing",
                "E2C requires DV2 alternate action evidence for every package.",
                package_id=package_id,
                action_variant_status=action_variant.get("status"),
            )
        )

    if not compare_focus or not bool(compare_focus.get("compare_ready")):
        failures.append(
            make_failed_requirement(
                "e2c_compare_focus_not_ready",
                "E2C requires a compare-ready review focus for every package.",
                package_id=package_id,
                compare_focus=compare_focus,
            )
        )
    if _browse_pair_count(browse_package) < 2 or not _all_browse_pass(browse_package):
        failures.append(
            make_failed_requirement(
                "e2c_compare_browse_incomplete",
                "E2C requires two browseable compare pairs per package.",
                package_id=package_id,
                browse_pair_count=_browse_pair_count(browse_package),
            )
        )
    if int(history_focus.get("event_count") or 0) < 2:
        failures.append(
            make_failed_requirement(
                "e2c_review_history_too_short",
                "E2C requires review history to retain at least two replay events per package.",
                package_id=package_id,
                event_count=int(history_focus.get("event_count") or 0),
            )
        )
    if str(action_replay.get("status") or "") != "pass" or str(animation_replay.get("status") or "") != "pass":
        failures.append(
            make_failed_requirement(
                "e2c_replay_focus_incomplete",
                "E2C requires action and animation replay verification for every package.",
                package_id=package_id,
                action_replay_status=action_replay.get("status"),
                animation_replay_status=animation_replay.get("status"),
            )
        )

    review_chain = {
        "curated_review_status": _review_status(curated_package),
        "navigation_status": _review_status(navigation_package),
        "replay_status": _review_status(replay_package),
        "history_status": _review_status(history_package),
        "compare_status": _review_status(compare_package),
        "compare_browse_status": _review_status(browse_package),
    }
    polish_summary = {
        "hero_ready": all(_image_exists(key_images[key]) for key in ("hero_before", "hero_after")),
        "material_ready": material_ready,
        "replay_ready": str(action_replay.get("status") or "") == "pass" and str(animation_replay.get("status") or "") == "pass",
        "compare_ready": bool(compare_focus.get("compare_ready")) and _all_browse_pass(browse_package),
        "history_ready": int(history_focus.get("event_count") or 0) >= 2,
        "diversity_ready": all(str(item.get("status") or "") == "pass" for item in (action_variant, clothing_variant, fx_variant)),
    }
    result = {
        "package_id": package_id,
        "sample_id": str(session_package.get("sample_id") or ""),
        "status": "pass" if not failures else "fail",
        "hero_shot": hero_shot,
        "material_reference": material_reference,
        "review_chain": review_chain,
        "action_preview": action_preview,
        "animation_preview": animation_preview,
        "review_focus": review_focus,
        "replay": {
            "action_replay": action_replay,
            "animation_replay": animation_replay,
        },
        "history_focus": history_focus,
        "compare_focus": compare_focus,
        "compare_pair": compare_pair,
        "browse_pair_count": _browse_pair_count(browse_package),
        "diversity_reference": {
            "baseline_action_preset_id": str(dv2_package.get("baseline_action_preset_id") or ""),
            "action_variant": action_variant,
            "clothing_variant": clothing_variant,
            "fx_variant": fx_variant,
        },
        "key_images": key_images,
        "polish_summary": polish_summary,
        "warning_flags": list(review_focus.get("warning_flags") or []),
        "errors": [],
        "failed_requirements": failures,
    }
    return result, failures


def _build_polish_state(
    *,
    session_payload: dict[str, Any],
    report_payload: dict[str, Any],
    output_report_path: Path,
) -> dict[str, Any]:
    package_results = [dict(item) for item in list(report_payload.get("per_package_results") or [])]
    return {
        "gate_id": GATE_ID,
        "status": str(report_payload.get("status") or "unknown"),
        "generated_at_utc": str(report_payload.get("generated_at_utc") or ""),
        "session_id": str(session_payload.get("session_id") or ""),
        "session_manifest_path": str(report_payload.get("source_session_manifest") or ""),
        "source_report_path": str(output_report_path.resolve()),
        "summary": {
            **dict(report_payload.get("counts") or {}),
            "selected_default_package_id": str(session_payload.get("default_package_id") or ""),
        },
        "package_polish": package_results,
        "source_reports": dict(report_payload.get("consumed_reports") or {}),
        "artifacts": dict(report_payload.get("artifacts") or {}),
    }


def main() -> int:
    args = parse_args()
    workspace = load_workspace_config(args.workspace_config)
    repo_root = repo_root_from_workspace(workspace, REPO_ROOT)
    output_root = Path(args.output_root).expanduser().resolve() if args.output_root else default_output_root(workspace, REPO_ROOT, GATE_ID)
    latest_report_path = Path(args.latest_report_path).expanduser().resolve() if args.latest_report_path else default_latest_report_path(workspace, REPO_ROOT, GATE_ID)
    latest_polish_state_path = (
        Path(args.latest_polish_state_path).expanduser().resolve() if args.latest_polish_state_path else default_latest_polish_state_path(repo_root)
    )
    session_manifest_path = Path(args.session_manifest_path).expanduser().resolve() if args.session_manifest_path else default_session_manifest_path(repo_root)
    output_root.mkdir(parents=True, exist_ok=True)
    previous_report = load_json(latest_report_path) if latest_report_path.exists() else None
    previous_report_path = latest_report_path if latest_report_path.exists() else None

    failed_requirements: list[dict[str, Any]] = []
    if not session_manifest_path.exists():
        failed_requirements.append(
            make_failed_requirement(
                "e2c_session_manifest_missing",
                "E2C credible showcase polish requires the latest playable demo E2 session manifest.",
                session_manifest_path=str(session_manifest_path.resolve()),
            )
        )
        session_payload = {}
    else:
        session_payload = load_json(session_manifest_path)

    report_specs = [
        ("e2b", args.e2b_report_path, DEFAULT_E2B_LATEST_NAME, "E2C requires the latest E2B credible showcase report."),
        ("dv2", args.dv2_report_path, DEFAULT_DV2_LATEST_NAME, "E2C requires the latest DV2 diversity matrix report."),
        ("curated_review", args.curated_review_report_path, DEFAULT_CURATED_REVIEW_LATEST_NAME, "E2C requires the latest curated review report."),
        ("review_navigation", args.review_navigation_report_path, DEFAULT_REVIEW_NAVIGATION_LATEST_NAME, "E2C requires the latest review navigation report."),
        ("review_replay", args.review_replay_report_path, DEFAULT_REVIEW_REPLAY_LATEST_NAME, "E2C requires the latest review replay report."),
        ("review_history", args.review_history_report_path, DEFAULT_REVIEW_HISTORY_LATEST_NAME, "E2C requires the latest review history report."),
        ("review_compare", args.review_compare_report_path, DEFAULT_REVIEW_COMPARE_LATEST_NAME, "E2C requires the latest review compare report."),
        ("review_compare_browse", args.review_compare_browse_report_path, DEFAULT_REVIEW_COMPARE_BROWSE_LATEST_NAME, "E2C requires the latest compare-browse report."),
    ]
    loaded_reports: dict[str, dict[str, Any]] = {}
    loaded_report_paths: dict[str, Path | None] = {}
    for key, explicit_path, latest_name, missing_message in report_specs:
        report_path, report_payload, report_failures = _load_required_report(
            workspace,
            explicit_path=explicit_path,
            latest_name=latest_name,
            missing_message=missing_message,
        )
        failed_requirements.extend(report_failures)
        loaded_reports[key] = report_payload
        loaded_report_paths[key] = report_path
        if report_payload and str(report_payload.get("status") or "") != "pass":
            failed_requirements.append(
                make_failed_requirement(
                    "e2c_required_report_not_pass",
                    "E2C requires every upstream showcase-polish report to be green.",
                    report_name=latest_name,
                    report_path=_display_path(report_path),
                    upstream_status=report_payload.get("status"),
                )
            )

    resolved_packages = [dict(item) for item in list(session_payload.get("packages") or [])]
    if len(resolved_packages) != int(FIXED_EXECUTION_PROFILE["required_package_count"]):
        failed_requirements.append(
            make_failed_requirement(
                "e2c_required_package_count_mismatch",
                "E2C requires exactly two ready bundles in the playable demo session manifest.",
                required_package_count=int(FIXED_EXECUTION_PROFILE["required_package_count"]),
                resolved_package_ids=[str(item.get("package_id") or "") for item in resolved_packages],
            )
        )

    per_package_results: list[dict[str, Any]] = []
    for session_package in resolved_packages:
        package_id = str(session_package.get("package_id") or "")
        package_result, package_failures = _package_polish_result(
            session_package=session_package,
            e2b_package=_find_package_result(loaded_reports["e2b"], package_id),
            dv2_package=_find_package_result(loaded_reports["dv2"], package_id),
            curated_package=_find_package_result(loaded_reports["curated_review"], package_id),
            navigation_package=_find_package_result(loaded_reports["review_navigation"], package_id),
            replay_package=_find_package_result(loaded_reports["review_replay"], package_id),
            history_package=_find_package_result(loaded_reports["review_history"], package_id),
            compare_package=_find_package_result(loaded_reports["review_compare"], package_id),
            browse_package=_find_package_result(loaded_reports["review_compare_browse"], package_id),
        )
        per_package_results.append(package_result)
        failed_requirements.extend(package_failures)

    passing_packages = sum(1 for item in per_package_results if str(item.get("status") or "") == "pass")
    compare_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("compare_ready")))
    replay_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("replay_ready")))
    diversity_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("diversity_ready")))
    material_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("material_ready")))
    history_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("history_ready")))
    hero_ready_packages = sum(1 for item in per_package_results if bool(dict(item.get("polish_summary") or {}).get("hero_ready")))

    counts = {
        "resolved_package_count": len(resolved_packages),
        "passing_packages": passing_packages,
        "compare_ready_packages": compare_ready_packages,
        "replay_ready_packages": replay_ready_packages,
        "history_ready_packages": history_ready_packages,
        "diversity_ready_packages": diversity_ready_packages,
        "packages_with_material_reference": material_ready_packages,
        "packages_with_hero_shots": hero_ready_packages,
    }
    status = "pass" if not failed_requirements else "fail"
    discussion_signal = build_discussion_signal(
        status,
        failed_requirements,
        previous_report,
        previous_report_path,
        "first_complete_playable_demo_e2c_credible_showcase_polish_pass",
    )

    report_payload = with_report_envelope(
        {
            "gate_id": GATE_ID,
            "status": status,
            "generated_at_utc": now_utc(),
            "workspace_config": str(Path(args.workspace_config).expanduser().resolve()),
            "source_session_manifest": str(session_manifest_path.resolve()) if session_manifest_path.exists() else str(session_manifest_path),
            "fixed_execution_profile": FIXED_EXECUTION_PROFILE,
            "counts": counts,
            "consumed_reports": {key: _display_path(path) for key, path in loaded_report_paths.items()},
            "per_package_results": per_package_results,
            "failed_requirements": failed_requirements,
            "discussion_signal": discussion_signal,
            "artifacts": {
                "run_root": str(output_root.resolve()),
                "polish_state_path": str(latest_polish_state_path.resolve()),
            },
        },
        "aiue_playable_demo_e2c_credible_showcase_polish_report",
        tool_name="AiUE",
        workflow_pack="pmx_pipeline",
        compatibility=make_compatibility_block(
            schema_family="aiue_playable_demo_e2c_credible_showcase_polish_report",
            notes=[
                "internal_e2c_showcase_polish_bundle",
                "consumes_e2b_dv2_and_native_review_slices",
                "demo_line_remains_presentation_first_not_validation_authority",
            ],
        ),
    )

    report_path = output_root / "playable_demo_e2c_credible_showcase_polish_report.json"
    write_report_pair(report_payload, report_path, latest_report_path)

    polish_state = _build_polish_state(
        session_payload=session_payload,
        report_payload=report_payload,
        output_report_path=report_path,
    )
    write_json(output_root / DEFAULT_POLISH_STATE_NAME, polish_state)
    write_json(latest_polish_state_path, polish_state)
    print(str(report_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
