from __future__ import annotations

from pathlib import Path
from typing import Any

from aiue_core.schema_utils import write_json


SUPPORTED_READY_FORMATS = {"fbx", "glb"}
PROVIDER_VERSION = "aiue-converted-model-provider-0.1"
PROVIDER_NAME = "aiue_body_platform_c2"


def default_latest_converted_model_provider_path(repo_root: str | Path) -> Path:
    resolved_repo_root = Path(repo_root).expanduser().resolve()
    return resolved_repo_root / "Saved" / "body_platform" / "c2" / "latest" / "converted_model_provider_v0_1.json"


def _path_exists(path_value: str | Path | None) -> bool:
    if not path_value:
        return False
    return Path(path_value).expanduser().exists()


def _provider_status_from_c2_report(c2_report: dict[str, Any]) -> str:
    if not c2_report:
        return "not_found"
    fixture = dict(c2_report.get("canonical_fusion_fixture") or {})
    primary_path = str(fixture.get("primary_mesh_abs_path") or "")
    manifest_path = str(fixture.get("manifest_path") or "")
    if not primary_path or not _path_exists(primary_path):
        return "missing_primary_asset"
    if not bool(fixture.get("manifest_present")) or not manifest_path or not _path_exists(manifest_path):
        return "missing_manifest"
    if str(c2_report.get("status") or "") == "pass":
        return "ready"
    return "conversion_failed"


def _companion_entry(
    *,
    role: str,
    path_value: str | Path,
    artifact_format: str,
) -> dict[str, Any]:
    resolved = Path(path_value).expanduser().resolve()
    return {
        "role": role,
        "path": str(resolved),
        "format": artifact_format,
    }


def build_converted_model_provider_from_c2_report(
    c2_report: dict[str, Any],
    *,
    report_source_path: str | Path = "",
) -> dict[str, Any]:
    fixture = dict(c2_report.get("canonical_fusion_fixture") or {})
    exporter = dict(fixture.get("exporter") or {})
    quality = dict(fixture.get("quality") or {})
    source_inventory_summary = dict(c2_report.get("source_inventory_summary") or {})
    status = _provider_status_from_c2_report(c2_report)

    primary_mesh_path = str(fixture.get("primary_mesh_abs_path") or "")
    primary_mesh_format = str(fixture.get("primary_mesh_format") or "").lower()
    body_family_id = str(c2_report.get("body_family_id") or fixture.get("body_family_id") or "")
    fixture_id = str(c2_report.get("fixture_id") or fixture.get("fixture_id") or "")
    fixture_scope = str(fixture.get("fixture_scope") or "")
    source_root = str(fixture.get("source_root") or "")
    source_module_ids = [str(item) for item in list(fixture.get("source_module_ids") or []) if str(item)]
    source_gate_id = "canonical_fusion_fixture_c2"

    companions: list[dict[str, Any]] = []
    manifest_path = str(fixture.get("manifest_path") or "")
    if manifest_path:
        companions.append(_companion_entry(role="upstream_manifest", path_value=manifest_path, artifact_format="json"))

    material_bundle_relative_root = str(fixture.get("material_bundle_relative_root") or "")
    if source_root and material_bundle_relative_root:
        material_bundle_root = Path(source_root).expanduser().resolve() / material_bundle_relative_root
        if material_bundle_root.exists():
            companions.append(
                _companion_entry(
                    role="material_bundle_root",
                    path_value=material_bundle_root,
                    artifact_format="directory",
                )
            )
            discovered_texture_paths = list(fixture.get("discovered_texture_relative_paths") or [])
            if discovered_texture_paths:
                companions.append(
                    _companion_entry(
                        role="textures_root",
                        path_value=material_bundle_root,
                        artifact_format="directory",
                    )
                )

    if report_source_path:
        companions.append(
            _companion_entry(
                role="body_platform_report",
                path_value=report_source_path,
                artifact_format="json",
            )
        )

    warnings: list[str] = []
    if status == "ready" and not bool(quality.get("runtime_ready")):
        warnings.append("converted_model_not_runtime_ready_for_ue")
    if not list(fixture.get("discovered_texture_relative_paths") or []):
        warnings.append("no_texture_bundle_declared")
    warnings.extend(
        str(item.get("id") or "")
        for item in list(c2_report.get("failed_requirements") or [])
        if str(item.get("id") or "")
    )

    notes: list[str] = []
    if source_module_ids:
        notes.append("lineage_tracks_source_module_ids")
    if not bool(quality.get("runtime_ready")):
        notes.append("c2_fixture_is_offline_handoff_not_runtime_avatar")

    ready_for_bodypaint = status == "ready" and primary_mesh_format in SUPPORTED_READY_FORMATS
    ready_for_ue = ready_for_bodypaint and bool(quality.get("runtime_ready"))

    return {
        "version": PROVIDER_VERSION,
        "status": status,
        "provider": PROVIDER_NAME,
        "consumer_hints": {
            "ready_for_bodypaint": ready_for_bodypaint,
            "ready_for_ue": ready_for_ue,
        },
        "identity": {
            "sample_id": body_family_id,
            "package_id": fixture_id,
            "profile": body_family_id,
            "body_family_id": body_family_id,
            "fixture_id": fixture_id,
        },
        "primary_asset": {
            "path": primary_mesh_path,
            "format": primary_mesh_format,
            "role": "converted_model",
            "relative_path": str(fixture.get("primary_mesh_relative_path") or ""),
        },
        "companions": companions,
        "lineage": {
            "source_profile": body_family_id,
            "source_root": str(source_inventory_summary.get("source_root") or source_root),
            "source_format": "body_platform_module_family",
            "source_module_ids": source_module_ids,
            "body_family_id": body_family_id,
            "fixture_scope": fixture_scope,
            "source_gate_id": source_gate_id,
        },
        "conversion": {
            "tool": str(exporter.get("tool") or ""),
            "tool_version": str(exporter.get("version") or ""),
            "generated_at_utc": str(c2_report.get("generated_at_utc") or ""),
            "source_gate_id": source_gate_id,
        },
        "body_platform": {
            "source_gate_id": source_gate_id,
            "body_family_id": body_family_id,
            "fixture_id": fixture_id,
            "fixture_scope": fixture_scope,
            "fusion_recipe_id": str(fixture.get("fusion_recipe_id") or ""),
            "rig_profile_id": str(fixture.get("rig_profile_id") or ""),
            "material_profile_id": str(fixture.get("material_profile_id") or ""),
        },
        "warnings": warnings,
        "notes": notes,
    }


def write_converted_model_provider(path: str | Path, payload: dict[str, Any]) -> Path:
    return write_json(path, payload)
