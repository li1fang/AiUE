from __future__ import annotations

import json
from pathlib import Path


TOY_YARD_VIEW_KEYS = ("toy_yard_pmx_view_root", "toy_yard_aiue_pmx_view_root")


def resolve_toy_yard_view_root(workspace: dict) -> Path | None:
    paths = workspace.get("paths") or {}
    for key in TOY_YARD_VIEW_KEYS:
        value = paths.get(key)
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists():
            return candidate
    return None


def resolve_toy_yard_view_file(workspace: dict, *relative_parts: str) -> Path | None:
    root = resolve_toy_yard_view_root(workspace)
    if root is None:
        return None
    candidate = root.joinpath(*relative_parts)
    if candidate.exists():
        return candidate.resolve()
    return None


def resolve_toy_yard_summary_path(workspace: dict) -> Path | None:
    return resolve_toy_yard_view_file(workspace, "summary", "ue_suite_summary.json")


def resolve_toy_yard_registry_path(workspace: dict) -> Path | None:
    return resolve_toy_yard_view_file(workspace, "summary", "ue_equipment_registry.json")


def resolve_toy_yard_equipment_report_path(workspace: dict) -> Path | None:
    for filename in ("ue_equipment_assets_report.local.json", "ue_equipment_assets_report.json"):
        candidate = resolve_toy_yard_view_file(workspace, "summary", filename)
        if candidate is not None:
            return candidate
    return None


def build_toy_yard_manifest_index(summary_path: Path) -> tuple[Path, dict[str, Path]]:
    conversion_root = summary_path.parent.parent / "conversion"
    if not conversion_root.exists():
        raise FileNotFoundError(f"Local conversion root missing for toy-yard view: {conversion_root}")
    manifest_index: dict[str, Path] = {}
    for manifest_path in sorted(conversion_root.rglob("manifest.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        package_id = str(payload.get("package_id") or "").strip()
        if package_id:
            manifest_index[package_id] = manifest_path.resolve()
    return conversion_root.resolve(), manifest_index
