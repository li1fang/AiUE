from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


TOY_YARD_VIEW_KEYS = ("toy_yard_pmx_view_root", "toy_yard_aiue_pmx_view_root")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_manifest_artifact(manifest_path: Path, artifact_path: str | None) -> Path | None:
    if not artifact_path:
        return None
    candidate = Path(artifact_path).expanduser()
    if candidate.exists():
        return candidate.resolve()
    local_sibling = manifest_path.parent / candidate.name
    if local_sibling.exists():
        return local_sibling.resolve()
    return candidate.resolve(strict=False)


def is_under_root(path: Path | None, root: Path | None) -> bool:
    if path is None or root is None:
        return False
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def resolve_view_root(workspace: dict | None = None, view_root: Path | None = None) -> Path | None:
    if view_root is not None:
        candidate = view_root.expanduser().resolve()
        return candidate if candidate.exists() else candidate
    paths = dict((workspace or {}).get("paths") or {})
    for key in TOY_YARD_VIEW_KEYS:
        value = paths.get(key)
        if not value:
            continue
        candidate = Path(value).expanduser().resolve()
        if candidate.exists():
            return candidate
    conversion_root_value = paths.get("conversion_root")
    if conversion_root_value:
        conversion_root = Path(conversion_root_value).expanduser().resolve()
        if conversion_root.exists():
            return conversion_root.parent.resolve()
    return None


def resolve_export_root_from_summary(summary: Path | None) -> Path | None:
    if summary is None:
        return None
    resolved = summary.expanduser().resolve()
    if resolved.is_dir():
        if resolved.name.lower() == "summary":
            return resolved.parent.resolve()
        return resolved
    if resolved.name.lower() == "ue_suite_summary.json" and resolved.parent.name.lower() == "summary":
        return resolved.parent.parent.resolve()
    return resolved.parent.resolve()


def discover_manifest_paths(
    *,
    workspace: dict | None = None,
    view_root: Path | None = None,
    summary: Path | None = None,
    manifest_path: Path | None = None,
) -> tuple[Path | None, list[Path]]:
    if manifest_path is not None:
        resolved_manifest = manifest_path.expanduser().resolve()
        root = resolve_export_root_from_summary(summary) or resolve_view_root(workspace=workspace, view_root=view_root)
        if root is None and "conversion" in resolved_manifest.parts:
            root = resolved_manifest.parents[1]
        return root, [resolved_manifest]

    root = resolve_export_root_from_summary(summary) or resolve_view_root(workspace=workspace, view_root=view_root)
    if root is None:
        return None, []
    conversion_root = root / "conversion"
    if not conversion_root.exists():
        return root, []
    manifests = sorted(conversion_root.rglob("manifest.json"))
    return root, manifests


def classify_path_reference(raw_path: str | None, resolved_path: Path | None, export_root: Path | None) -> list[str]:
    issues: list[str] = []
    if not raw_path:
        return issues
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute() and export_root is not None and not is_under_root(resolved_path, export_root):
        issues.append("absolute_path_outside_export_root")
    return issues


def inspect_manifest_artifacts(manifest_path: Path, export_root: Path | None = None) -> dict:
    manifest = load_json(manifest_path)
    issues: list[str] = []

    output_fbx_raw = manifest.get("output_fbx")
    output_fbx_resolved = resolve_manifest_artifact(manifest_path, output_fbx_raw)
    output_fbx_exists = bool(output_fbx_resolved and output_fbx_resolved.exists())
    output_fbx_in_export_root = is_under_root(output_fbx_resolved, export_root)
    if not output_fbx_exists:
        issues.append("output_fbx_missing")
    if output_fbx_raw and not output_fbx_in_export_root:
        issues.extend(classify_path_reference(output_fbx_raw, output_fbx_resolved, export_root))

    source_file_raw = manifest.get("source_file")
    source_file_resolved = resolve_manifest_artifact(manifest_path, source_file_raw)
    source_file_exists = bool(source_file_resolved and source_file_resolved.exists())
    source_file_in_export_root = is_under_root(source_file_resolved, export_root)
    if source_file_raw and not source_file_in_export_root:
        issues.append("source_file_external_reference")

    textures = []
    missing_texture_count = 0
    external_texture_reference_count = 0
    for index, texture in enumerate(manifest.get("textures") or [], start=1):
        relocated_raw = texture.get("relocated_path")
        original_raw = texture.get("original_path")
        relocated_resolved = resolve_manifest_artifact(manifest_path, relocated_raw)
        original_resolved = resolve_manifest_artifact(manifest_path, original_raw)
        relocated_exists = bool(relocated_resolved and relocated_resolved.exists())
        original_exists = bool(original_resolved and original_resolved.exists())
        chosen_resolved = relocated_resolved if relocated_exists else original_resolved
        chosen_exists = relocated_exists or original_exists
        chosen_in_export_root = is_under_root(chosen_resolved, export_root)
        texture_issues: list[str] = []
        if not chosen_exists:
            texture_issues.append("texture_artifact_missing")
            missing_texture_count += 1
        if (relocated_raw or original_raw) and not chosen_in_export_root:
            texture_issues.append("texture_reference_outside_export_root")
            external_texture_reference_count += 1
        textures.append(
            {
                "index": index,
                "material_name": texture.get("material_name"),
                "relocated_path_raw": relocated_raw,
                "relocated_path_resolved": str(relocated_resolved) if relocated_resolved else "",
                "relocated_exists": relocated_exists,
                "original_path_raw": original_raw,
                "original_path_resolved": str(original_resolved) if original_resolved else "",
                "original_exists": original_exists,
                "chosen_path": str(chosen_resolved) if chosen_resolved else "",
                "chosen_exists": chosen_exists,
                "chosen_in_export_root": chosen_in_export_root,
                "issues": texture_issues,
            }
        )
    if missing_texture_count:
        issues.append(f"missing_texture_artifacts:{missing_texture_count}")
    if external_texture_reference_count:
        issues.append(f"external_texture_references:{external_texture_reference_count}")

    import_report_path = manifest_path.parent / "ue_import_report.local.json"
    validation_report_path = manifest_path.parent / "ue_validation_report.local.json"
    consumer_contract_path = manifest_path.parent / "ue_consumer_contract.json"

    return {
        "status": "pass" if not issues else "attention",
        "manifest_path": str(manifest_path),
        "package_id": manifest.get("package_id"),
        "sample_id": manifest.get("sample_id"),
        "export_root": str(export_root) if export_root else "",
        "source_file": {
            "raw": source_file_raw,
            "resolved": str(source_file_resolved) if source_file_resolved else "",
            "exists": source_file_exists,
            "in_export_root": source_file_in_export_root,
        },
        "output_fbx": {
            "raw": output_fbx_raw,
            "resolved": str(output_fbx_resolved) if output_fbx_resolved else "",
            "exists": output_fbx_exists,
            "in_export_root": output_fbx_in_export_root,
        },
        "textures": textures,
        "texture_count_declared": len(manifest.get("textures") or []),
        "sidecar_reports": {
            "consumer_contract_path": str(consumer_contract_path),
            "consumer_contract_exists": consumer_contract_path.exists(),
            "ue_import_report_path": str(import_report_path),
            "ue_import_report_exists": import_report_path.exists(),
            "ue_validation_report_path": str(validation_report_path),
            "ue_validation_report_exists": validation_report_path.exists(),
        },
        "issues": issues,
    }


def build_manifest_artifact_check_report(*, manifest_paths: list[Path], export_root: Path | None, source_workspace_config: Path | None = None) -> dict:
    per_manifest = [inspect_manifest_artifacts(path, export_root=export_root) for path in manifest_paths]
    counts = {
        "manifest_count": len(per_manifest),
        "pass_count": sum(1 for entry in per_manifest if entry["status"] == "pass"),
        "attention_count": sum(1 for entry in per_manifest if entry["status"] != "pass"),
        "output_fbx_missing_count": sum(1 for entry in per_manifest if "output_fbx_missing" in entry["issues"]),
        "source_file_external_reference_count": sum(1 for entry in per_manifest if "source_file_external_reference" in entry["issues"]),
        "missing_texture_manifest_count": sum(1 for entry in per_manifest if any(issue.startswith("missing_texture_artifacts:") for issue in entry["issues"])),
        "external_texture_manifest_count": sum(1 for entry in per_manifest if any(issue.startswith("external_texture_references:") for issue in entry["issues"])),
    }
    return {
        "tool_name": "AiUE T1",
        "report_kind": "toy_yard_manifest_artifact_check",
        "generated_at_utc": now_utc(),
        "status": "pass" if counts["attention_count"] == 0 else "attention",
        "source_workspace_config": str(source_workspace_config) if source_workspace_config else "",
        "export_root": str(export_root) if export_root else "",
        "counts": counts,
        "per_manifest_results": per_manifest,
    }


def write_manifest_artifact_check_report(
    *,
    repo_root: Path,
    manifest_path: Path | None = None,
    workspace: dict | None = None,
    workspace_config_path: Path | None = None,
    view_root: Path | None = None,
    summary: Path | None = None,
    output_path: Path | None = None,
) -> dict:
    export_root, manifest_paths = discover_manifest_paths(
        workspace=workspace,
        view_root=view_root,
        summary=summary,
        manifest_path=manifest_path,
    )
    payload = build_manifest_artifact_check_report(
        manifest_paths=manifest_paths,
        export_root=export_root,
        source_workspace_config=workspace_config_path,
    )
    final_output_path = output_path or (repo_root / "Saved" / "tooling" / "toy_yard_manifest_checks" / "latest" / "manifest_artifact_check.json")
    final_output_path = final_output_path.expanduser().resolve()
    write_json(final_output_path, payload)
    payload["artifacts"] = {
        "report_path": str(final_output_path),
    }
    return payload
