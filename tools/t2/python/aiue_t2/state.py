from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from aiue_t2.state_demo import build_demo_request, default_demo_preset_id, load_demo_session
from aiue_t2.state_models import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    AppState,
    DemoPackageRecord,
    DemoPresetRecord,
    DemoRequestRecord,
    DemoSessionRecord,
    ErrorRecord,
    GovernanceBalanceRecord,
    Pv1SignoffRecord,
    PreviewImageRecord,
    ReportRecord,
    TestGovernanceRecord,
    ViewState,
    build_default_view_state,
    report_payload_to_text,
    view_state_to_dict,
)
from aiue_t2.state_quality import (
    build_q5c_contrast_focus,
    extract_governance_balance,
    extract_pv1_signoff,
    extract_r3_metrics,
    extract_test_governance,
    load_preview_images,
    load_quality_summaries,
    load_report_categories,
)


def resolve_manifest_path(*, repo_root: Path, manifest_path: str | Path | None = None, latest: bool = False) -> Path:
    if manifest_path:
        return Path(manifest_path).expanduser().resolve()
    if latest or not manifest_path:
        return (repo_root / "Saved" / "tooling" / "t1" / "latest" / "manifest.json").resolve()
    raise ValueError("Unable to resolve a manifest path.")


def wait_for_manifest_path(
    manifest_path: str | Path,
    *,
    timeout_seconds: float = 3.0,
    poll_interval_seconds: float = 0.1,
) -> Path:
    resolved_path = Path(manifest_path).expanduser().resolve()
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    while True:
        if resolved_path.exists():
            return resolved_path
        if time.monotonic() >= deadline:
            return resolved_path
        time.sleep(max(0.01, float(poll_interval_seconds)))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _error_app_state(*, manifest_path: Path, code: str, message: str) -> AppState:
    error = ErrorRecord(code=code, message=message, path=str(manifest_path))
    return AppState(
        status="error",
        manifest_path=str(manifest_path),
        pack_root=str(manifest_path.parent),
        generated_at_utc="",
        summary_counts={
            "reports": 0,
            "active_line_reports": 0,
            "platform_line_reports": 0,
            "governance_line_reports": 0,
            "historical_other_reports": 0,
            "passing_reports": 0,
        },
        report_categories={key: [] for key in CATEGORY_ORDER},
        reports_by_gate_id={},
        preview_images=[],
        r3_metrics=[],
        quality_summaries={
            "diversity_matrix": {"status": "missing", "coverage_axes": []},
            "m1_material_proof": {"status": "missing", "packages": []},
            "q5c_lite": {"status": "missing", "packages": [], "diagnostic_class_counts": {}},
            "q5c_contrast": {"status": "missing", "packages": []},
        },
        slot_debugger={"package_count": 0, "packages": []},
        governance_balance=GovernanceBalanceRecord(status="missing"),
        test_governance=TestGovernanceRecord(status="missing"),
        pv1_signoff=Pv1SignoffRecord(status="missing"),
        demo_session=DemoSessionRecord(
            status="missing",
            session_manifest_path="",
            session_id="",
            session_type="",
            host_key="",
            mode="",
            level_path="",
            default_package_id=None,
        ),
        demo_request=DemoRequestRecord(
            status="missing",
            selected_package_id=None,
            selected_action_preset_id=None,
            selected_animation_preset_id=None,
        ),
        errors=[error],
        default_report_gate_id=None,
        default_image_key=None,
        default_package_id=None,
        default_action_preset_id=None,
        default_animation_preset_id=None,
    )


def _coerce_summary_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = dict(payload.get("counts") or {})
    return {
        "reports": int(counts.get("reports") or 0),
        "active_line_reports": int(counts.get("active_line_reports") or 0),
        "platform_line_reports": int(counts.get("platform_line_reports") or 0),
        "governance_line_reports": int(counts.get("governance_line_reports") or 0),
        "historical_other_reports": int(counts.get("historical_other_reports") or 0),
        "passing_reports": int(counts.get("passing_reports") or 0),
    }


def _default_report_gate_id(report_categories: dict[str, list[ReportRecord]]) -> str | None:
    for category in CATEGORY_ORDER:
        records = list(report_categories.get(category) or [])
        if records:
            return records[0].gate_id or records[0].name
    return None


def load_workbench_state(
    manifest_path: str | Path,
    *,
    session_manifest_path: str | Path | None = None,
) -> AppState:
    resolved_manifest_path = Path(manifest_path).expanduser().resolve()
    if not resolved_manifest_path.exists():
        return _error_app_state(
            manifest_path=resolved_manifest_path,
            code="manifest_missing",
            message="The requested T1 manifest does not exist.",
        )
    try:
        manifest = _load_json(resolved_manifest_path)
    except json.JSONDecodeError as exc:
        return _error_app_state(
            manifest_path=resolved_manifest_path,
            code="manifest_invalid_json",
            message=f"Failed to parse manifest JSON: {exc}",
        )

    pack_root = resolved_manifest_path.parent
    errors: list[ErrorRecord] = []
    report_categories, reports_by_gate_id = load_report_categories(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    preview_images = load_preview_images(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    quality_summaries = load_quality_summaries(
        manifest=manifest,
        pack_root=pack_root,
        reports_by_gate_id=reports_by_gate_id,
        preview_images=preview_images,
    )
    slot_debugger = dict(manifest.get("slot_debugger") or {})
    demo_session = load_demo_session(
        manifest_path=resolved_manifest_path,
        session_manifest_path=session_manifest_path,
        errors=errors,
    )
    summary_counts = _coerce_summary_counts(dict(manifest.get("report_index") or {}))
    default_report_gate_id = _default_report_gate_id(report_categories)
    slot_packages = list(slot_debugger.get("packages") or [])
    governance_balance = extract_governance_balance(reports_by_gate_id)
    test_governance = extract_test_governance(reports_by_gate_id)
    pv1_signoff = extract_pv1_signoff(reports_by_gate_id)
    default_package_id = (
        demo_session.default_package_id
        or (str(slot_packages[0].get("package_id") or "") if slot_packages else None)
    )
    q5c_contrast_focus = build_q5c_contrast_focus(
        quality_summaries,
        selected_package_id=default_package_id,
    )
    default_image_key = q5c_contrast_focus.get("recommended_preview_image_key") or (
        preview_images[0].key if preview_images else None
    )
    default_action_preset_id = default_demo_preset_id(
        demo_session,
        package_id=default_package_id,
        preset_kind="action",
    )
    default_animation_preset_id = default_demo_preset_id(
        demo_session,
        package_id=default_package_id,
        preset_kind="animation",
    )
    demo_request = build_demo_request(
        demo_session=demo_session,
        selected_package_id=default_package_id,
        selected_action_preset_id=default_action_preset_id,
        selected_animation_preset_id=default_animation_preset_id,
    )
    return AppState(
        status="pass" if not errors else "error",
        manifest_path=str(resolved_manifest_path),
        pack_root=str(pack_root),
        generated_at_utc=str(manifest.get("generated_at_utc") or ""),
        summary_counts=summary_counts,
        report_categories=report_categories,
        reports_by_gate_id=reports_by_gate_id,
        preview_images=preview_images,
        r3_metrics=extract_r3_metrics(reports_by_gate_id),
        quality_summaries=quality_summaries,
        slot_debugger=slot_debugger,
        governance_balance=governance_balance,
        test_governance=test_governance,
        pv1_signoff=pv1_signoff,
        demo_session=demo_session,
        demo_request=demo_request,
        errors=errors,
        default_report_gate_id=default_report_gate_id,
        default_image_key=default_image_key,
        default_package_id=default_package_id,
        default_action_preset_id=default_action_preset_id,
        default_animation_preset_id=default_animation_preset_id,
    )
