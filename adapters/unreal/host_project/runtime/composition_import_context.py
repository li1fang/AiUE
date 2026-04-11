from __future__ import annotations

from .common import *
from .composition_import_assets import load_existing_import_blueprint, resolve_texture_files


def derive_import_context(request: dict) -> dict:
    manifest_path = Path(request["manifest"]).expanduser().resolve()
    manifest = read_json(manifest_path)
    output_fbx = resolve_manifest_artifact(manifest_path, manifest.get("output_fbx"))
    if not output_fbx or not output_fbx.exists():
        raise FileNotFoundError(f"Resolved FBX not found for manifest: {manifest_path}")
    asset_root = request.get("asset_root") or "/Game/PMXPipeline"
    existing = load_existing_import_blueprint(manifest_path)
    pipeline_strategy = manifest.get("pipeline_strategy") or {}
    unreal_import_strategy = pipeline_strategy.get("unreal_import") or {}
    unreal_validation_strategy = pipeline_strategy.get("unreal_validation") or {}
    content_bucket = (
        request.get("content_bucket")
        or unreal_import_strategy.get("content_bucket")
        or existing.get("content_bucket")
        or "Characters"
    )
    mesh_name = output_fbx.stem.replace(".", "_")
    asset_label = existing.get("asset_label") or f"{sanitize_segment(manifest.get('sample_id') or output_fbx.parent.name)}_{sanitize_segment(output_fbx.stem)}"
    package_root = remap_asset_root((existing.get("destination_paths") or {}).get("package_root"), asset_root) or f"{asset_root}/{content_bucket}/{asset_label}"
    mesh_destination = remap_asset_root((existing.get("destination_paths") or {}).get("mesh_destination"), asset_root) or f"{package_root}/Meshes"
    texture_destination = remap_asset_root((existing.get("destination_paths") or {}).get("texture_destination"), asset_root) or f"{package_root}/Textures"
    import_report_path = manifest_path.parent / "ue_import_report.local.json"
    validation_report_path = manifest_path.parent / "ue_validation_report.local.json"
    consumer_contract_path = manifest_path.parent / "ue_consumer_contract.json"
    consumer_contract = read_json(consumer_contract_path) if consumer_contract_path.exists() else {}
    texture_files = resolve_texture_files(manifest_path, manifest, output_fbx)
    expected_slot_names = [entry.get("normalized_name") for entry in manifest.get("materials", []) if entry.get("normalized_name")]
    expected_texture_count = len(texture_files)
    create_physics_asset = bool(unreal_import_strategy.get("create_physics_asset", True))
    physics_asset_policy = str(unreal_validation_strategy.get("physics_asset_policy") or "required")
    physics_asset_required = physics_asset_policy.lower() != "optional"
    return {
        "manifest_path": manifest_path,
        "manifest": manifest,
        "output_fbx": output_fbx,
        "asset_root": asset_root,
        "content_bucket": content_bucket,
        "asset_label": asset_label,
        "mesh_name": mesh_name,
        "package_root": package_root,
        "mesh_destination": mesh_destination,
        "texture_destination": texture_destination,
        "import_report_path": import_report_path,
        "validation_report_path": validation_report_path,
        "consumer_contract_path": consumer_contract_path if consumer_contract_path.exists() else None,
        "consumer_contract": consumer_contract,
        "texture_files": texture_files,
        "expected_slot_names": expected_slot_names,
        "expected_texture_count": expected_texture_count,
        "package_role": request.get("package_role") or manifest.get("package_hints", {}).get("package_role") or consumer_contract.get("package_role"),
        "package_id": request.get("package_id") or manifest.get("package_id") or consumer_contract.get("package_id"),
        "source_relative_path": manifest.get("source_relative_path"),
        "pipeline_strategy": pipeline_strategy,
        "create_physics_asset": create_physics_asset,
        "physics_asset_policy": physics_asset_policy,
        "physics_asset_required": physics_asset_required,
        "profile": request.get("profile") or unreal_import_strategy.get("profile"),
    }


__all__ = ["derive_import_context"]
