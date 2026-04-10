from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


CATEGORY_ORDER = ["active_line", "platform_line", "historical_other"]
CATEGORY_LABELS = {
    "active_line": "Active Line",
    "platform_line": "Platform Line",
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
    slot_debugger: dict[str, Any]
    errors: list[ErrorRecord]
    default_report_gate_id: str | None
    default_image_key: str | None
    default_package_id: str | None

    def to_dump_payload(self, view_state: "ViewState | None" = None) -> dict[str, Any]:
        selected_report = view_state.selected_report_gate_id if view_state else self.default_report_gate_id
        selected_image = view_state.selected_image_key if view_state else self.default_image_key
        selected_package = view_state.selected_package_id if view_state else self.default_package_id
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
            "slot_debugger": {
                "package_count": int(self.slot_debugger.get("package_count") or 0),
                "package_ids": [str(item.get("package_id") or "") for item in slot_packages],
            },
            "preview_images": [record.to_dump_dict() for record in self.preview_images],
            "errors": [error.to_dict() for error in self.errors],
        }


@dataclass
class ViewState:
    selected_report_gate_id: str | None = None
    selected_image_key: str | None = None
    selected_package_id: str | None = None


def build_default_view_state(app_state: AppState) -> ViewState:
    return ViewState(
        selected_report_gate_id=app_state.default_report_gate_id,
        selected_image_key=app_state.default_image_key,
        selected_package_id=app_state.default_package_id,
    )


def resolve_manifest_path(*, repo_root: Path, manifest_path: str | Path | None = None, latest: bool = False) -> Path:
    if manifest_path:
        return Path(manifest_path).expanduser().resolve()
    if latest or not manifest_path:
        return (repo_root / "Saved" / "tooling" / "t1" / "latest" / "manifest.json").resolve()
    raise ValueError("Unable to resolve a manifest path.")


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
            "historical_other_reports": 0,
            "passing_reports": 0,
        },
        report_categories={key: [] for key in CATEGORY_ORDER},
        reports_by_gate_id={},
        preview_images=[],
        r3_metrics=[],
        slot_debugger={"package_count": 0, "packages": []},
        errors=[error],
        default_report_gate_id=None,
        default_image_key=None,
        default_package_id=None,
    )


def _artifact_path(pack_root: Path, relative_path: str) -> Path:
    return (pack_root / Path(relative_path)).resolve()


def _coerce_summary_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = dict(payload.get("counts") or {})
    return {
        "reports": int(counts.get("reports") or 0),
        "active_line_reports": int(counts.get("active_line_reports") or 0),
        "platform_line_reports": int(counts.get("platform_line_reports") or 0),
        "historical_other_reports": int(counts.get("historical_other_reports") or 0),
        "passing_reports": int(counts.get("passing_reports") or 0),
    }


def _load_report_categories(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> tuple[dict[str, list[ReportRecord]], dict[str, ReportRecord]]:
    report_artifacts = list((manifest.get("artifacts") or {}).get("reports") or [])
    artifact_paths_by_gate_id = {
        str(item.get("gate_id") or ""): _artifact_path(pack_root, str(item.get("relative_path") or ""))
        for item in report_artifacts
        if str(item.get("gate_id") or "") and str(item.get("relative_path") or "")
    }
    categories_payload = dict((manifest.get("report_index") or {}).get("categories") or {})
    report_categories: dict[str, list[ReportRecord]] = {key: [] for key in CATEGORY_ORDER}
    reports_by_gate_id: dict[str, ReportRecord] = {}

    for category in CATEGORY_ORDER:
        for entry in list(categories_payload.get(category) or []):
            gate_id = str(entry.get("gate_id") or "")
            artifact_path = artifact_paths_by_gate_id.get(gate_id)
            report_payload: dict[str, Any] = {}
            if artifact_path is None or not artifact_path.exists():
                missing_path = artifact_path or Path(str(entry.get("report_path") or ""))
                errors.append(
                    ErrorRecord(
                        code="artifact_missing",
                        message=f"Missing report artifact for gate '{gate_id or entry.get('name') or 'unknown'}'.",
                        path=str(missing_path),
                    )
                )
            else:
                try:
                    report_payload = _load_json(artifact_path)
                except json.JSONDecodeError as exc:
                    errors.append(
                        ErrorRecord(
                            code="artifact_missing",
                            message=f"Unreadable report artifact JSON for gate '{gate_id or entry.get('name') or 'unknown'}': {exc}",
                            path=str(artifact_path),
                        )
                    )
            record = ReportRecord(
                gate_id=gate_id,
                name=str(entry.get("name") or gate_id or "report"),
                category=category,
                status=str(entry.get("status") or report_payload.get("status") or "unknown"),
                generated_at_utc=str(entry.get("generated_at_utc") or report_payload.get("generated_at_utc") or ""),
                report_artifact_path=str(artifact_path or ""),
                report_source_path=str(entry.get("report_path") or ""),
                report_payload=report_payload,
            )
            report_categories[category].append(record)
            if gate_id:
                reports_by_gate_id[gate_id] = record

    return report_categories, reports_by_gate_id


def _load_preview_images(
    *,
    manifest: dict[str, Any],
    pack_root: Path,
    errors: list[ErrorRecord],
) -> list[PreviewImageRecord]:
    preview_images = []
    for entry in list((manifest.get("artifacts") or {}).get("preview_images") or []):
        image_path = _artifact_path(pack_root, str(entry.get("relative_path") or ""))
        if not image_path.exists():
            errors.append(
                ErrorRecord(
                    code="artifact_missing",
                    message=f"Missing preview image '{entry.get('title') or entry.get('key') or 'image'}'.",
                    path=str(image_path),
                )
            )
        preview_images.append(
            PreviewImageRecord(
                key=str(entry.get("key") or ""),
                title=str(entry.get("title") or entry.get("key") or "image"),
                section=str(entry.get("section") or ""),
                image_path=str(image_path),
                source_path=str(entry.get("source_path") or ""),
            )
        )
    return preview_images


def _extract_r3_metrics(reports_by_gate_id: dict[str, ReportRecord]) -> list[dict[str, Any]]:
    record = reports_by_gate_id.get("live_fx_visual_quality_r3")
    if not record or not record.report_payload:
        return []
    metrics_rows: list[dict[str, Any]] = []
    for package in list(record.report_payload.get("per_package_results") or []):
        package_id = str(package.get("package_id") or "")
        for shot in list(package.get("shot_results") or []):
            crop_metrics = dict(shot.get("crop_metrics") or {})
            full_metrics = dict(shot.get("full_frame_metrics") or {})
            metrics_rows.append(
                {
                    "package_id": package_id,
                    "shot_id": str(shot.get("shot_id") or ""),
                    "status": str(shot.get("status") or ""),
                    "crop_histogram_l1": float(crop_metrics.get("histogram_l1") or 0.0),
                    "crop_mean_abs_pixel_delta": float(crop_metrics.get("mean_abs_pixel_delta") or 0.0),
                    "full_histogram_l1": float(full_metrics.get("histogram_l1") or 0.0),
                    "full_mean_abs_pixel_delta": float(full_metrics.get("mean_abs_pixel_delta") or 0.0),
                }
            )
    return metrics_rows


def _default_report_gate_id(report_categories: dict[str, list[ReportRecord]]) -> str | None:
    for category in CATEGORY_ORDER:
        records = list(report_categories.get(category) or [])
        if records:
            return records[0].gate_id or records[0].name
    return None


def load_workbench_state(manifest_path: str | Path) -> AppState:
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
    report_categories, reports_by_gate_id = _load_report_categories(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    preview_images = _load_preview_images(
        manifest=manifest,
        pack_root=pack_root,
        errors=errors,
    )
    slot_debugger = dict(manifest.get("slot_debugger") or {})
    summary_counts = _coerce_summary_counts(dict(manifest.get("report_index") or {}))
    default_report_gate_id = _default_report_gate_id(report_categories)
    default_image_key = preview_images[0].key if preview_images else None
    slot_packages = list(slot_debugger.get("packages") or [])
    default_package_id = str(slot_packages[0].get("package_id") or "") if slot_packages else None
    return AppState(
        status="pass" if not errors else "error",
        manifest_path=str(resolved_manifest_path),
        pack_root=str(pack_root),
        generated_at_utc=str(manifest.get("generated_at_utc") or ""),
        summary_counts=summary_counts,
        report_categories=report_categories,
        reports_by_gate_id=reports_by_gate_id,
        preview_images=preview_images,
        r3_metrics=_extract_r3_metrics(reports_by_gate_id),
        slot_debugger=slot_debugger,
        errors=errors,
        default_report_gate_id=default_report_gate_id,
        default_image_key=default_image_key,
        default_package_id=default_package_id,
    )


def report_payload_to_text(report_record: ReportRecord | None) -> str:
    if report_record is None:
        return "{}"
    return json.dumps(report_record.report_payload or {}, ensure_ascii=False, indent=2)


def view_state_to_dict(view_state: ViewState) -> dict[str, Any]:
    return asdict(view_state)
