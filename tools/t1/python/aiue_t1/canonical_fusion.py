from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Any

from aiue_core.schema_utils import load_json


SUPPORTED_FUSION_MESH_EXTENSIONS = {
    ".abc",
    ".fbx",
    ".obj",
    ".usd",
    ".usda",
    ".usdc",
}

SUPPORTED_TEXTURE_EXTENSIONS = {
    ".bmp",
    ".exr",
    ".jpeg",
    ".jpg",
    ".png",
    ".tga",
    ".tif",
    ".tiff",
}

MANIFEST_CANDIDATES = (
    "canonical_fusion_fixture_manifest.json",
    "fusion_fixture_manifest.json",
    "manifest.json",
)


def _iter_files(root: Path, *, extensions: set[str]) -> list[Path]:
    files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in extensions]
    files.sort()
    return files


def _find_manifest(root: Path) -> Path | None:
    candidates: list[Path] = []
    for file_name in MANIFEST_CANDIDATES:
        candidates.extend(path for path in root.rglob(file_name) if path.is_file())
    if not candidates:
        return None
    candidates.sort(key=lambda path: (len(path.relative_to(root).parts), str(path).lower()))
    return candidates[0]


def _copy_tree(source_root: Path, destination_root: Path) -> Path:
    if destination_root.exists():
        shutil.rmtree(destination_root)
    shutil.copytree(source_root, destination_root)
    return destination_root


def _extract_zip(zip_path: Path, destination_root: Path) -> Path:
    if destination_root.exists():
        shutil.rmtree(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(destination_root)
    return destination_root


def stage_canonical_fusion_source(source_path: str | Path, *, output_root: str | Path) -> dict[str, Any]:
    resolved_source_path = Path(source_path).expanduser().resolve()
    resolved_output_root = Path(output_root).expanduser().resolve()
    staging_root = resolved_output_root / "staged_input"
    if resolved_source_path.suffix.lower() == ".zip":
        staged_root = _extract_zip(resolved_source_path, staging_root)
        input_kind = "zip"
    else:
        staged_root = _copy_tree(resolved_source_path, staging_root)
        input_kind = "directory"
    return {
        "source_input_path": str(resolved_source_path),
        "source_input_kind": input_kind,
        "staged_root": str(staged_root),
    }


def inspect_canonical_fusion_fixture(source_root: str | Path) -> dict[str, Any]:
    resolved_source_root = Path(source_root).expanduser().resolve()
    manifest_path = _find_manifest(resolved_source_root)
    manifest = load_json(manifest_path) if manifest_path else {}
    mesh_files = _iter_files(resolved_source_root, extensions=SUPPORTED_FUSION_MESH_EXTENSIONS)
    texture_files = _iter_files(resolved_source_root, extensions=SUPPORTED_TEXTURE_EXTENSIONS)

    primary_mesh_relative_path = str(manifest.get("primary_mesh_relative_path") or "")
    primary_mesh_path = (resolved_source_root / primary_mesh_relative_path).resolve() if primary_mesh_relative_path else None
    if primary_mesh_path and not primary_mesh_path.exists():
        primary_mesh_path = None
    if primary_mesh_path is None and len(mesh_files) == 1:
        primary_mesh_path = mesh_files[0]
        primary_mesh_relative_path = str(primary_mesh_path.relative_to(resolved_source_root)).replace("\\", "/")

    fixture_scope = str(manifest.get("fixture_scope") or "")
    exporter = dict(manifest.get("exporter") or {})
    coordinate_system = dict(manifest.get("coordinate_system") or {})
    source_module_ids = [str(item) for item in list(manifest.get("source_module_ids") or []) if str(item)]
    material_bundle_relative_root = str(manifest.get("material_bundle_relative_root") or "")
    texture_relative_paths = [str(item) for item in list(manifest.get("texture_relative_paths") or []) if str(item)]

    return {
        "source_root": str(resolved_source_root),
        "manifest_path": str(manifest_path.resolve()) if manifest_path else "",
        "manifest_present": bool(manifest_path),
        "manifest": manifest,
        "fixture_id": str(manifest.get("fixture_id") or ""),
        "body_family_id": str(manifest.get("body_family_id") or ""),
        "fixture_scope": fixture_scope,
        "source_module_ids": source_module_ids,
        "primary_mesh_relative_path": primary_mesh_relative_path,
        "primary_mesh_abs_path": str(primary_mesh_path.resolve()) if primary_mesh_path else "",
        "primary_mesh_format": primary_mesh_path.suffix.lower().lstrip(".") if primary_mesh_path else "",
        "discovered_mesh_relative_paths": [
            str(path.relative_to(resolved_source_root)).replace("\\", "/")
            for path in mesh_files
        ],
        "discovered_texture_relative_paths": [
            str(path.relative_to(resolved_source_root)).replace("\\", "/")
            for path in texture_files
        ],
        "material_bundle_relative_root": material_bundle_relative_root,
        "texture_relative_paths": texture_relative_paths,
        "exporter": exporter,
        "coordinate_system": coordinate_system,
        "quality": dict(manifest.get("quality") or {}),
        "counts": {
            "discovered_mesh_count": len(mesh_files),
            "discovered_texture_count": len(texture_files),
            "declared_texture_count": len(texture_relative_paths),
            "source_module_count": len(source_module_ids),
        },
    }
