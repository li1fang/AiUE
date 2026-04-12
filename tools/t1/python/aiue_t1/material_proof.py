from __future__ import annotations

import json
import string
from pathlib import Path
from typing import Any


VALID_SIMPLE_ESCAPES = {'"', "\\", "/", "b", "f", "n", "r", "t"}


def load_lenient_json(path: str | Path) -> tuple[dict[str, Any], list[str]]:
    resolved_path = Path(path).expanduser().resolve()
    raw_text = resolved_path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw_text), []
    except json.JSONDecodeError as exc:
        sanitized_text = _escape_invalid_json_backslashes(raw_text)
        try:
            return json.loads(sanitized_text), [f"lenient_backslash_fallback:{exc.msg}"]
        except json.JSONDecodeError:
            raise


def _escape_invalid_json_backslashes(text: str) -> str:
    output: list[str] = []
    in_string = False
    index = 0
    text_length = len(text)
    while index < text_length:
        char = text[index]
        if not in_string:
            output.append(char)
            if char == '"':
                in_string = True
            index += 1
            continue
        if char == "\\":
            next_char = text[index + 1] if index + 1 < text_length else ""
            if next_char in VALID_SIMPLE_ESCAPES:
                output.append("\\")
                output.append(next_char)
                index += 2
                continue
            if (
                next_char == "u"
                and index + 5 < text_length
                and all(candidate in string.hexdigits for candidate in text[index + 2 : index + 6])
            ):
                output.append(text[index : index + 6])
                index += 6
                continue
            output.append("\\\\")
            index += 1
            continue
        output.append(char)
        if char == '"':
            in_string = False
        index += 1
    return "".join(output)


def resolve_conversion_search_roots(workspace: dict, equipment_report: dict, equipment_report_path: str | Path | None = None) -> list[Path]:
    roots: list[Path] = []
    registry_json_path = str(equipment_report.get("registry_json_path") or "").strip()
    if registry_json_path:
        registry_path = Path(registry_json_path).expanduser().resolve()
        for candidate in (registry_path.parents[1] / "conversion", registry_path.parents[2] / "conversion"):
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    if equipment_report_path:
        report_path = Path(equipment_report_path).expanduser().resolve()
        report_parent = report_path.parent
        if report_parent.name == "ue":
            candidate = report_parent.parent / "conversion"
            if candidate.exists() and candidate not in roots:
                roots.append(candidate)
    conversion_root = Path(workspace["paths"]["conversion_root"]).expanduser().resolve()
    for candidate in (conversion_root / "_e2e_runs", conversion_root):
        if candidate.exists() and candidate not in roots:
            roots.append(candidate)
    return roots


def build_material_report_index(search_roots: list[Path]) -> dict[str, dict[str, Any]]:
    validation_by_package: dict[str, dict[str, Any]] = {}
    validation_by_sample: dict[str, list[dict[str, Any]]] = {}
    import_by_package: dict[str, dict[str, Any]] = {}
    scan_errors: list[dict[str, Any]] = []

    for root in search_roots:
        if not root.exists():
            continue
        for validation_path in root.rglob("ue_validation_report.local.json"):
            try:
                payload, warnings = load_lenient_json(validation_path)
                summary = validation_summary_from_payload(payload, validation_path, warnings=warnings)
            except Exception as exc:
                scan_errors.append(
                    {
                        "path": str(validation_path.resolve()),
                        "kind": "validation",
                        "error": str(exc),
                    }
                )
                continue
            package_id = str(summary.get("package_id") or "")
            if package_id and _prefer_report(summary, validation_by_package.get(package_id)):
                validation_by_package[package_id] = summary
            sample_id = str(summary.get("sample_id") or "")
            if sample_id:
                validation_by_sample.setdefault(sample_id, []).append(summary)
            import_report_path = str(summary.get("import_report_path") or "")
            if import_report_path:
                import_path = Path(import_report_path).expanduser()
                if import_path.exists():
                    try:
                        import_payload, warnings = load_lenient_json(import_path)
                        import_summary = import_summary_from_payload(import_payload, import_path, warnings=warnings)
                        import_package_id = str(import_summary.get("package_id") or "")
                        if import_package_id and _prefer_report(import_summary, import_by_package.get(import_package_id)):
                            import_by_package[import_package_id] = import_summary
                    except Exception as exc:
                        scan_errors.append(
                            {
                                "path": str(import_path.resolve()),
                                "kind": "import",
                                "error": str(exc),
                            }
                        )
        for import_path in root.rglob("ue_import_report.local.json"):
            try:
                payload, warnings = load_lenient_json(import_path)
                summary = import_summary_from_payload(payload, import_path, warnings=warnings)
            except Exception as exc:
                scan_errors.append(
                    {
                        "path": str(import_path.resolve()),
                        "kind": "import",
                        "error": str(exc),
                    }
                )
                continue
            package_id = str(summary.get("package_id") or "")
            if package_id and _prefer_report(summary, import_by_package.get(package_id)):
                import_by_package[package_id] = summary

    return {
        "search_roots": [str(item.resolve()) for item in search_roots],
        "validation_by_package": validation_by_package,
        "validation_by_sample": validation_by_sample,
        "import_by_package": import_by_package,
        "scan_errors": scan_errors,
    }


def validation_summary_from_payload(
    payload: dict[str, Any],
    source_path: str | Path,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    checks = dict(payload.get("checks") or {})
    expected_material_slot_names = [
        str(item)
        for item in list(checks.get("expected_material_slot_names") or payload.get("expected_material_slot_names") or [])
        if str(item)
    ]
    actual_material_slot_names = [
        str(item)
        for item in list(checks.get("actual_material_slot_names") or payload.get("actual_material_slot_names") or [])
        if str(item)
    ]
    expected_texture_count = _optional_int(
        checks.get("expected_texture_count"),
        fallback=payload.get("expected_texture_count"),
    )
    imported_texture_count = _optional_int(
        checks.get("imported_texture_count"),
        fallback=payload.get("imported_texture_count"),
    )
    material_slot_names_match = expected_material_slot_names == actual_material_slot_names and bool(expected_material_slot_names)
    return {
        "package_id": str(payload.get("package_id") or ""),
        "sample_id": str(payload.get("sample_id") or ""),
        "status": str(payload.get("status") or "unknown"),
        "content_bucket": str(payload.get("content_bucket") or ""),
        "package_role": str(payload.get("package_role") or ""),
        "source_path": str(Path(source_path).expanduser().resolve()),
        "import_report_path": str(payload.get("import_report_path") or ""),
        "expected_texture_count": expected_texture_count,
        "imported_texture_count": imported_texture_count,
        "expected_material_slot_names": expected_material_slot_names,
        "actual_material_slot_names": actual_material_slot_names,
        "material_slot_names_match": material_slot_names_match,
        "consumer_ready": bool(dict(payload.get("consumer") or {}).get("consumer_ready")),
        "warnings": [str(item) for item in list(payload.get("warnings") or [])] + list(warnings or []),
        "failures": [str(item) for item in list(payload.get("failures") or [])],
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
    }


def import_summary_from_payload(
    payload: dict[str, Any],
    source_path: str | Path,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    imported_assets = dict(payload.get("imported_assets") or {})
    imported_textures = [
        str(item)
        for item in list(imported_assets.get("textures") or [])
        if str(item)
    ]
    destination_paths = dict(payload.get("destination_paths") or {})
    pipeline_strategy = dict(payload.get("pipeline_strategy") or {})
    unreal_import = dict(pipeline_strategy.get("unreal_import") or {})
    return {
        "package_id": str(payload.get("package_id") or ""),
        "sample_id": str(payload.get("sample_id") or ""),
        "status": str(payload.get("status") or "unknown"),
        "content_bucket": str(payload.get("content_bucket") or ""),
        "package_role": str(payload.get("package_role") or ""),
        "source_path": str(Path(source_path).expanduser().resolve()),
        "manifest_path": str(payload.get("manifest_path") or ""),
        "texture_destination": str(destination_paths.get("texture_destination") or ""),
        "mesh_destination": str(destination_paths.get("mesh_destination") or ""),
        "imported_texture_assets": imported_textures,
        "imported_texture_count": len(imported_textures),
        "import_textures_requested": bool(unreal_import.get("import_textures")),
        "warnings": [str(item) for item in list(payload.get("warnings") or [])] + list(warnings or []),
        "generated_at_utc": str(payload.get("generated_at_utc") or ""),
    }


def resolve_package_material_evidence(
    report_index_payload: dict[str, Any],
    *,
    package_id: str,
    sample_id: str,
) -> dict[str, Any]:
    validation_by_package = dict(report_index_payload.get("validation_by_package") or {})
    import_by_package = dict(report_index_payload.get("import_by_package") or {})
    validation = dict(validation_by_package.get(package_id) or {})
    import_summary = dict(import_by_package.get(package_id) or {})
    if validation and not import_summary:
        import_report_path = str(validation.get("import_report_path") or "")
        if import_report_path:
            import_path = Path(import_report_path).expanduser()
            if import_path.exists():
                payload, warnings = load_lenient_json(import_path)
                import_summary = import_summary_from_payload(payload, import_path, warnings=warnings)
    if not validation:
        for candidate in list(report_index_payload.get("validation_by_sample") or {}).get(sample_id, []):
            if str(candidate.get("package_id") or "") == package_id:
                validation = dict(candidate)
                break
    return {
        "validation": validation,
        "import": import_summary,
    }


def build_material_proof_quality_summary(report_index_payload: dict[str, Any]) -> dict[str, Any]:
    entry = dict((report_index_payload.get("reports_by_gate_id") or {}).get("material_texture_proof_m1") or {})
    report = dict(entry.get("report") or {})
    if not report:
        return {
            "status": "missing",
            "gate_id": "material_texture_proof_m1",
            "report_source_path": "",
            "package_count": 0,
            "passing_package_count": 0,
            "packages": [],
        }
    packages = []
    for item in list(report.get("per_package_results") or []):
        import_evidence = dict(item.get("import_evidence") or {})
        host_visual_evidence = dict(item.get("host_visual_evidence") or {})
        character_import = dict(import_evidence.get("character") or {})
        weapon_import = dict(import_evidence.get("default_weapon") or {})
        material_evidence = dict(host_visual_evidence.get("material_evidence") or {})
        main_mesh_materials = dict(material_evidence.get("main_mesh") or {})
        weapon_materials = dict(material_evidence.get("weapon_mesh") or {})
        packages.append(
            {
                "package_id": str(item.get("package_id") or ""),
                "status": str(item.get("status") or "unknown"),
                "sample_id": str(item.get("sample_id") or ""),
                "character_expected_texture_count": _optional_int(character_import.get("expected_texture_count")) or 0,
                "character_imported_texture_count": _optional_int(character_import.get("imported_texture_count")) or 0,
                "weapon_expected_texture_count": _optional_int(weapon_import.get("expected_texture_count")) or 0,
                "weapon_imported_texture_count": _optional_int(weapon_import.get("imported_texture_count")) or 0,
                "main_mesh_material_slot_count": int(main_mesh_materials.get("material_slot_count") or 0),
                "weapon_material_slot_count": int(weapon_materials.get("material_slot_count") or 0),
                "material_asset_count": len([path for path in list(main_mesh_materials.get("material_asset_paths") or []) if str(path)]),
                "weapon_material_asset_count": len([path for path in list(weapon_materials.get("material_asset_paths") or []) if str(path)]),
                "primary_image_path": _primary_pass_image(host_visual_evidence),
                "failed_requirement_ids": [
                    str(requirement.get("id") or "")
                    for requirement in list(item.get("failed_requirements") or [])
                    if str(requirement.get("id") or "")
                ],
            }
        )
    return {
        "status": str(report.get("status") or "unknown"),
        "gate_id": "material_texture_proof_m1",
        "report_source_path": str(entry.get("report_path") or ""),
        "package_count": len(packages),
        "passing_package_count": sum(1 for item in packages if item.get("status") == "pass"),
        "packages": packages,
    }


def _primary_pass_image(host_visual_evidence: dict[str, Any]) -> str:
    for shot in list(host_visual_evidence.get("shots") or []):
        image_path = str(shot.get("image_path") or "")
        if image_path:
            return image_path
    return ""


def _prefer_report(candidate: dict[str, Any], existing: dict[str, Any] | None) -> bool:
    if existing is None:
        return True
    candidate_path = Path(str(candidate.get("source_path") or "")).expanduser()
    existing_path = Path(str(existing.get("source_path") or "")).expanduser()
    try:
        candidate_mtime = candidate_path.stat().st_mtime
    except OSError:
        candidate_mtime = 0.0
    try:
        existing_mtime = existing_path.stat().st_mtime
    except OSError:
        existing_mtime = 0.0
    return candidate_mtime >= existing_mtime


def _optional_int(value: Any, *, fallback: Any = None) -> int | None:
    for candidate in (value, fallback):
        if candidate is None:
            continue
        if isinstance(candidate, str) and not candidate.strip():
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


__all__ = [
    "build_material_proof_quality_summary",
    "build_material_report_index",
    "import_summary_from_payload",
    "load_lenient_json",
    "resolve_conversion_search_roots",
    "resolve_package_material_evidence",
    "validation_summary_from_payload",
]
