from __future__ import annotations
from .common import *
from .composition_import import *

def import_package_dry_run(request: dict) -> dict:
    context = derive_import_context(request)
    imported_textures = []
    for texture_file in context["texture_files"]:
        name = texture_file.stem.replace(".", "_")
        imported_textures.append(f"{context['texture_destination']}/{name}.{name}")
    return {
        "manifest_path": str(context["manifest_path"]),
        "source_file": context["manifest"].get("source_file"),
        "sample_id": context["manifest"].get("sample_id"),
        "output_fbx": str(context["output_fbx"]),
        "original_output_fbx": context["manifest"].get("output_fbx"),
        "asset_root": context["asset_root"],
        "asset_label": context["asset_label"],
        "content_bucket": context["content_bucket"],
        "destination_paths": {
            "package_root": context["package_root"],
            "mesh_destination": context["mesh_destination"],
            "texture_destination": context["texture_destination"],
        },
        "imported_assets": {
            "skeletal_mesh": f"{context['mesh_destination']}/{context['mesh_name']}.{context['mesh_name']}",
            "skeleton": f"{context['mesh_destination']}/{context['mesh_name']}_Skeleton.{context['mesh_name']}_Skeleton",
            "physics_asset": (
                f"{context['mesh_destination']}/{context['mesh_name']}_PhysicsAsset.{context['mesh_name']}_PhysicsAsset"
                if context["create_physics_asset"] or context["physics_asset_required"]
                else None
            ),
            "textures": imported_textures,
            "other": [],
        },
        "dry_run": True,
        "warnings": [
            "dry_run_only_no_assets_imported",
            "package_role_and_contract_type_are_inferred_from_local_manifest_context",
        ],
        "errors": [],
    }

def import_package(request: dict) -> dict:
    context = derive_import_context(request)
    ensure_directory(context["package_root"])
    ensure_directory(context["mesh_destination"])
    ensure_directory(context["texture_destination"])
    imported_textures = import_files(context["texture_files"], context["texture_destination"])
    mesh_assets = import_skeletal_mesh(context["output_fbx"], context["mesh_destination"], context["create_physics_asset"])
    mesh_assets = enrich_related_assets(mesh_assets, context["mesh_destination"], context["mesh_name"])
    if (context["create_physics_asset"] or context["physics_asset_required"]) and not mesh_assets["physics_asset"]:
        mesh_assets["physics_asset"] = create_physics_asset_for_mesh(
            mesh_assets["skeletal_mesh"],
            mesh_assets["skeleton"],
            context["mesh_destination"],
            context["mesh_name"],
        )
        mesh_assets = enrich_related_assets(mesh_assets, context["mesh_destination"], context["mesh_name"])
    imported_assets = {
        "skeletal_mesh": mesh_assets["skeletal_mesh"],
        "skeleton": mesh_assets["skeleton"],
        "physics_asset": mesh_assets["physics_asset"],
        "textures": imported_textures,
        "other": mesh_assets["other"],
    }
    save_directory(context["package_root"])
    actual_slot_names = material_slot_names(imported_assets["skeletal_mesh"])
    failures = []
    warnings = []
    if not imported_assets["skeletal_mesh"]:
        failures.append("skeletal_mesh_missing_after_import")
    if not imported_assets["skeleton"]:
        failures.append("skeleton_missing_after_import")
    if context["physics_asset_required"] and not imported_assets["physics_asset"]:
        failures.append("physics_asset_missing_after_import")
    if len(imported_assets["textures"]) < context["expected_texture_count"]:
        warnings.append(f"imported_texture_count_below_expected:{len(imported_assets['textures'])}/{context['expected_texture_count']}")
    missing_slots = [name for name in context["expected_slot_names"] if name not in actual_slot_names]
    if missing_slots:
        warnings.append(f"missing_material_slots:{len(missing_slots)}")
    import_report = {
        "generated_at_utc": now_utc(),
        "sample_id": context["manifest"].get("sample_id"),
        "package_id": context["package_id"],
        "source_file": context["manifest"].get("source_file"),
        "source_relative_path": context["source_relative_path"],
        "manifest_path": str(context["manifest_path"]),
        "output_fbx": str(context["output_fbx"]),
        "profile_path": None,
        "requested_profile": context["profile"],
        "resolved_profile": context["profile"] or "default_skeletal_import",
        "asset_root": context["asset_root"],
        "asset_label": context["asset_label"],
        "content_bucket": context["content_bucket"],
        "package_role": context["package_role"],
        "pipeline_strategy": {
            "unreal_import": context["pipeline_strategy"].get("unreal_import", {}),
            "unreal_validation": context["pipeline_strategy"].get("unreal_validation", {}),
            "risk_level": context["pipeline_strategy"].get("risk_level"),
        },
        "destination_paths": {
            "package_root": context["package_root"],
            "mesh_destination": context["mesh_destination"],
            "texture_destination": context["texture_destination"],
        },
        "imported_assets": imported_assets,
        "warnings": warnings,
        "consumer_contract_path": str(context["consumer_contract_path"]) if context["consumer_contract_path"] else None,
        "consumer_contract_summary": {
            "contract_type": context["consumer_contract"].get("contract_type"),
            "consumer_ready": context["consumer_contract"].get("consumer_ready"),
            "preferred_owner_package_id": context["consumer_contract"].get("preferred_owner_package_id"),
        },
        "bundle_context": context["consumer_contract"].get("bundle_context"),
        "attachment": context["consumer_contract"].get("attachment"),
    }
    validation_report = {
        "generated_at_utc": now_utc(),
        "sample_id": context["manifest"].get("sample_id"),
        "package_id": context["package_id"],
        "source_file": context["manifest"].get("source_file"),
        "source_relative_path": context["source_relative_path"],
        "manifest_path": str(context["manifest_path"]),
        "import_report_path": str(context["import_report_path"]),
        "content_bucket": context["content_bucket"],
        "package_role": context["package_role"],
        "checks": {
            "skeletal_mesh_exists": bool(imported_assets["skeletal_mesh"]),
            "skeleton_exists": bool(imported_assets["skeleton"]),
            "physics_asset_exists": bool(imported_assets["physics_asset"]),
            "physics_asset_required": context["physics_asset_required"],
            "expected_material_slot_names": context["expected_slot_names"],
            "actual_material_slot_names": actual_slot_names,
            "tolerated_missing_material_slots": [],
            "expected_texture_count": context["expected_texture_count"],
            "imported_texture_count": len(imported_assets["textures"]),
        },
        "strategy": {
            "physics_asset_policy": context["physics_asset_policy"],
            "allow_minor_trailing_material_drops": False,
            "minor_trailing_material_candidates": [],
        },
        "consumer": {
            "contract_path": str(context["consumer_contract_path"]) if context["consumer_contract_path"] else None,
            "contract_type": context["consumer_contract"].get("contract_type"),
            "consumer_ready": context["consumer_contract"].get("consumer_ready"),
            "preferred_owner_package_id": context["consumer_contract"].get("preferred_owner_package_id"),
            "preferred_attach_target": context["consumer_contract"].get("preferred_attach_target"),
        },
        "failures": failures,
        "warnings": warnings,
        "score": 100 if not failures and not warnings else 90 if not failures else 0,
        "status": "pass" if not failures else "fail",
    }
    write_json(context["import_report_path"], import_report)
    write_json(context["validation_report_path"], validation_report)
    return {
        **import_report,
        "import_report_path": str(context["import_report_path"]),
        "validation_report_path": str(context["validation_report_path"]),
        "validation_status": validation_report["status"],
        "validation_score": validation_report["score"],
        "dry_run": False,
        "warnings": warnings,
        "errors": failures,
    }

__all__ = ["import_package_dry_run", "import_package"]
