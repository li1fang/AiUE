from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


CATEGORY_ORDER = ["active_line", "platform_line", "body_platform_line", "governance_line", "historical_other"]
CATEGORY_LABELS = {
    "active_line": "Active Line",
    "platform_line": "Platform Line",
    "body_platform_line": "Body Platform Line",
    "governance_line": "Governance Line",
    "historical_other": "Historical / Other",
}


@dataclass
class ErrorRecord:
    code: str
    message: str
    path: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "path": self.path}


@dataclass
class ReportRecord:
    gate_id: str
    name: str
    category: str
    status: str
    generated_at_utc: str
    report_artifact_path: str
    report_source_path: str
    report_payload: dict[str, Any] = field(default_factory=dict)

    def to_dump_dict(self) -> dict[str, str]:
        return {
            "gate_id": self.gate_id,
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "generated_at_utc": self.generated_at_utc,
            "report_artifact_path": self.report_artifact_path,
            "report_source_path": self.report_source_path,
        }


@dataclass
class PreviewImageRecord:
    key: str
    title: str
    section: str
    image_path: str
    source_path: str

    def to_dump_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "title": self.title,
            "section": self.section,
            "image_path": self.image_path,
            "source_path": self.source_path,
        }


@dataclass
class DemoPresetRecord:
    preset_id: str
    preset_kind: str
    family: str = ""
    source_gate_id: str = ""
    status: str = ""
    requested_asset_path: str = ""
    resolved_asset_path: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "preset_id": self.preset_id,
            "preset_kind": self.preset_kind,
            "family": self.family,
            "source_gate_id": self.source_gate_id,
            "status": self.status,
            "requested_asset_path": self.requested_asset_path,
            "resolved_asset_path": self.resolved_asset_path,
        }


@dataclass
class DemoPackageRecord:
    package_id: str
    sample_id: str
    host_blueprint_asset: str
    hero_shot_id: str
    slot_names: list[str]
    hero_before_image_path: str
    hero_after_image_path: str
    action_presets: list[DemoPresetRecord] = field(default_factory=list)
    animation_presets: list[DemoPresetRecord] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "sample_id": self.sample_id,
            "host_blueprint_asset": self.host_blueprint_asset,
            "hero_shot_id": self.hero_shot_id,
            "slot_names": list(self.slot_names),
            "hero_before_image_path": self.hero_before_image_path,
            "hero_after_image_path": self.hero_after_image_path,
            "action_presets": [record.to_dump_dict() for record in self.action_presets],
            "animation_presets": [record.to_dump_dict() for record in self.animation_presets],
        }


@dataclass
class DemoSessionRecord:
    status: str
    session_manifest_path: str
    session_id: str
    session_type: str
    host_key: str
    mode: str
    level_path: str
    default_package_id: str | None
    packages: list[DemoPackageRecord] = field(default_factory=list)
    switch_order: list[str] = field(default_factory=list)
    source_reports: dict[str, str] = field(default_factory=dict)

    def package_by_id(self, package_id: str | None) -> DemoPackageRecord | None:
        if not package_id:
            return None
        return next((record for record in self.packages if record.package_id == package_id), None)

    def to_dump_dict(
        self,
        *,
        selected_package_id: str | None = None,
        selected_action_preset_id: str | None = None,
        selected_animation_preset_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "status": self.status,
            "session_manifest_path": self.session_manifest_path,
            "session_id": self.session_id,
            "session_type": self.session_type,
            "host_key": self.host_key,
            "mode": self.mode,
            "level_path": self.level_path,
            "default_package_id": self.default_package_id,
            "package_count": len(self.packages),
            "package_ids": [record.package_id for record in self.packages],
            "selected_package_id": selected_package_id,
            "selected_action_preset_id": selected_action_preset_id,
            "selected_animation_preset_id": selected_animation_preset_id,
        }


@dataclass
class DemoRequestRecord:
    status: str
    selected_package_id: str | None
    selected_action_preset_id: str | None
    selected_animation_preset_id: str | None
    requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "selected_package_id": self.selected_package_id,
            "selected_action_preset_id": self.selected_action_preset_id,
            "selected_animation_preset_id": self.selected_animation_preset_id,
            "request_kinds": sorted(self.requests.keys()),
            "requests": dict(self.requests),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass
class GovernanceBalanceRecord:
    status: str
    recommended_next_round_kind: str | None = None
    discussion_reason: str | None = None
    stability_pressure: str = "unknown"
    governance_pressure: str = "unknown"
    progress_pressure: str = "unknown"
    hotspot_paths: list[str] = field(default_factory=list)
    report_gate_id: str = ""
    report_source_path: str = ""

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "recommended_next_round_kind": self.recommended_next_round_kind,
            "discussion_signal": {"reason": self.discussion_reason},
            "stability_pressure": self.stability_pressure,
            "governance_pressure": self.governance_pressure,
            "progress_pressure": self.progress_pressure,
            "hotspot_paths": list(self.hotspot_paths),
            "report_gate_id": self.report_gate_id,
            "report_source_path": self.report_source_path,
        }


@dataclass
class TestGovernanceRecord:
    status: str
    checkpoint_ready: bool = False
    automation_checkpoint_ready: bool = False
    signoff_checkpoint_ready: bool = False
    required_lane_ids: list[str] = field(default_factory=list)
    executed_lane_ids: list[str] = field(default_factory=list)
    failed_lane_ids: list[str] = field(default_factory=list)
    high_priority_blind_spot_ids: list[str] = field(default_factory=list)
    high_priority_automation_blind_spot_ids: list[str] = field(default_factory=list)
    high_priority_signoff_blind_spot_ids: list[str] = field(default_factory=list)
    report_gate_id: str = ""
    report_source_path: str = ""

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checkpoint_ready": bool(self.checkpoint_ready),
            "automation_checkpoint_ready": bool(self.automation_checkpoint_ready),
            "signoff_checkpoint_ready": bool(self.signoff_checkpoint_ready),
            "required_lane_ids": list(self.required_lane_ids),
            "executed_lane_ids": list(self.executed_lane_ids),
            "failed_lane_ids": list(self.failed_lane_ids),
            "high_priority_blind_spot_ids": list(self.high_priority_blind_spot_ids),
            "high_priority_automation_blind_spot_ids": list(self.high_priority_automation_blind_spot_ids),
            "high_priority_signoff_blind_spot_ids": list(self.high_priority_signoff_blind_spot_ids),
            "report_gate_id": self.report_gate_id,
            "report_source_path": self.report_source_path,
        }


@dataclass
class FeatureLedgerRecord:
    status: str
    item_count: int = 0
    experimental_item_count: int = 0
    unknown_priority_count: int = 0
    pending_triage_count: int = 0
    ledger_path: str = ""
    validation_errors: list[str] = field(default_factory=list)
    unknown_priority_item_ids: list[str] = field(default_factory=list)
    pending_triage_item_ids: list[str] = field(default_factory=list)

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "item_count": int(self.item_count),
            "experimental_item_count": int(self.experimental_item_count),
            "unknown_priority_count": int(self.unknown_priority_count),
            "pending_triage_count": int(self.pending_triage_count),
            "ledger_path": self.ledger_path,
            "validation_errors": list(self.validation_errors),
            "unknown_priority_item_ids": list(self.unknown_priority_item_ids),
            "pending_triage_item_ids": list(self.pending_triage_item_ids),
        }


@dataclass
class Pv1SignoffRecord:
    status: str
    requested_signoff_status: str = ""
    operator: str = ""
    notes: str = ""
    success: bool = False
    checked_package_ids: list[str] = field(default_factory=list)
    checked_package_count: int = 0
    source_session_manifest: str = ""
    source_e2b_report: str = ""
    report_gate_id: str = ""
    report_source_path: str = ""

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "requested_signoff_status": self.requested_signoff_status,
            "operator": self.operator,
            "notes": self.notes,
            "success": bool(self.success),
            "checked_package_ids": list(self.checked_package_ids),
            "checked_package_count": int(self.checked_package_count),
            "source_session_manifest": self.source_session_manifest,
            "source_e2b_report": self.source_e2b_report,
            "report_gate_id": self.report_gate_id,
            "report_source_path": self.report_source_path,
        }


@dataclass
class QaFullRecord:
    status: str
    hard_failure_count: int = 0
    soft_finding_count: int = 0
    expected_watchlist_count: int = 0
    blocked_lane_count: int = 0
    root_failure_count: int = 0
    cascade_failure_count: int = 0
    environment_failure_count: int = 0
    flake_count: int = 0
    output_drift_count: int = 0
    watchlist_only: bool = False
    root_failure_lane_ids: list[str] = field(default_factory=list)
    cascade_failure_lane_ids: list[str] = field(default_factory=list)
    environment_failure_lane_ids: list[str] = field(default_factory=list)
    discussion_reason: str = ""
    report_gate_id: str = ""
    report_source_path: str = ""

    def to_dump_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "hard_failure_count": int(self.hard_failure_count),
            "soft_finding_count": int(self.soft_finding_count),
            "expected_watchlist_count": int(self.expected_watchlist_count),
            "blocked_lane_count": int(self.blocked_lane_count),
            "root_failure_count": int(self.root_failure_count),
            "cascade_failure_count": int(self.cascade_failure_count),
            "environment_failure_count": int(self.environment_failure_count),
            "flake_count": int(self.flake_count),
            "output_drift_count": int(self.output_drift_count),
            "watchlist_only": bool(self.watchlist_only),
            "root_failure_lane_ids": list(self.root_failure_lane_ids),
            "cascade_failure_lane_ids": list(self.cascade_failure_lane_ids),
            "environment_failure_lane_ids": list(self.environment_failure_lane_ids),
            "discussion_signal": {"reason": self.discussion_reason},
            "report_gate_id": self.report_gate_id,
            "report_source_path": self.report_source_path,
        }


@dataclass
class AppState:
    status: str
    manifest_path: str
    pack_root: str
    generated_at_utc: str
    summary_counts: dict[str, int]
    report_categories: dict[str, list[ReportRecord]]
    reports_by_gate_id: dict[str, ReportRecord]
    preview_images: list[PreviewImageRecord]
    r3_metrics: list[dict[str, Any]]
    quality_summaries: dict[str, Any]
    slot_debugger: dict[str, Any]
    governance_balance: GovernanceBalanceRecord
    test_governance: TestGovernanceRecord
    feature_ledger: FeatureLedgerRecord
    pv1_signoff: Pv1SignoffRecord
    qa_full: QaFullRecord
    demo_session: DemoSessionRecord
    demo_request: DemoRequestRecord
    errors: list[ErrorRecord]
    default_report_gate_id: str | None
    default_image_key: str | None
    default_package_id: str | None
    default_action_preset_id: str | None
    default_animation_preset_id: str | None

    def to_dump_payload(self, view_state: "ViewState | None" = None) -> dict[str, Any]:
        from aiue_t2.state import build_demo_request, build_q5c_contrast_focus

        selected_report = view_state.selected_report_gate_id if view_state else self.default_report_gate_id
        selected_image = view_state.selected_image_key if view_state else self.default_image_key
        selected_package = view_state.selected_package_id if view_state else self.default_package_id
        selected_action_preset = view_state.selected_action_preset_id if view_state else self.default_action_preset_id
        selected_animation_preset = view_state.selected_animation_preset_id if view_state else self.default_animation_preset_id
        selected_review_compare_index = view_state.selected_review_compare_index if view_state else 0
        resolved_demo_request = build_demo_request(
            demo_session=self.demo_session,
            selected_package_id=selected_package,
            selected_action_preset_id=selected_action_preset,
            selected_animation_preset_id=selected_animation_preset,
        )
        slot_packages = list(self.slot_debugger.get("packages") or [])
        return {
            "status": self.status,
            "manifest_path": self.manifest_path,
            "pack_root": self.pack_root,
            "generated_at_utc": self.generated_at_utc,
            "summary_counts": dict(self.summary_counts),
            "report_categories": {
                category: [record.gate_id or record.name for record in list(records or [])]
                for category, records in self.report_categories.items()
            },
            "selected_default_report": selected_report,
            "selected_default_image": selected_image,
            "selected_default_package": selected_package,
            "selected_default_action_preset": selected_action_preset,
            "selected_default_animation_preset": selected_animation_preset,
            "selected_default_review_compare_index": int(selected_review_compare_index),
            "slot_debugger": {
                "package_count": int(self.slot_debugger.get("package_count") or 0),
                "package_ids": [str(item.get("package_id") or "") for item in slot_packages],
            },
            "governance_balance": self.governance_balance.to_dump_dict(),
            "test_governance": self.test_governance.to_dump_dict(),
            "feature_ledger": self.feature_ledger.to_dump_dict(),
            "pv1_signoff": self.pv1_signoff.to_dump_dict(),
            "qa_full": self.qa_full.to_dump_dict(),
            "q5c_contrast_focus": build_q5c_contrast_focus(
                self.quality_summaries,
                selected_package_id=selected_package,
            ),
            "demo_session": self.demo_session.to_dump_dict(
                selected_package_id=selected_package,
                selected_action_preset_id=selected_action_preset,
                selected_animation_preset_id=selected_animation_preset,
            ),
            "demo_request": resolved_demo_request.to_dump_dict(),
            "preview_images": [record.to_dump_dict() for record in self.preview_images],
            "quality_summaries": dict(self.quality_summaries),
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass
class ViewState:
    selected_report_gate_id: str | None = None
    selected_image_key: str | None = None
    selected_package_id: str | None = None
    selected_action_preset_id: str | None = None
    selected_animation_preset_id: str | None = None
    selected_review_compare_index: int = 0


def build_default_view_state(app_state: AppState) -> ViewState:
    return ViewState(
        selected_report_gate_id=app_state.default_report_gate_id,
        selected_image_key=app_state.default_image_key,
        selected_package_id=app_state.default_package_id,
        selected_action_preset_id=app_state.default_action_preset_id,
        selected_animation_preset_id=app_state.default_animation_preset_id,
        selected_review_compare_index=0,
    )


def report_payload_to_text(report_record: ReportRecord | None) -> str:
    if report_record is None:
        return "{}"
    return json.dumps(report_record.report_payload or {}, ensure_ascii=False, indent=2)


def view_state_to_dict(view_state: ViewState) -> dict[str, Any]:
    return asdict(view_state)
