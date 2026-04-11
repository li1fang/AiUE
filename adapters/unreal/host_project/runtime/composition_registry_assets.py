from __future__ import annotations

from .common import *


def derive_suite_identity(registry_path: Path, registry_payload: dict, request: dict) -> tuple[str, str]:
    if request.get("suite_name"):
        suite_name = str(request["suite_name"])
    else:
        suite_file = registry_payload.get("suite_file")
        suite_name = Path(suite_file).stem if suite_file else registry_path.parent.parent.name
    suite_slug = str(request.get("suite_slug") or sanitize_segment(suite_name))
    return suite_name, suite_slug


def find_latest_registry_json(conversion_root: Path) -> Path:
    candidates = sorted(conversion_root.rglob("ue_equipment_registry.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No ue_equipment_registry.json found under {conversion_root}")
    return candidates[0]


def create_or_load_data_asset(asset_name: str, package_path: str, asset_class):
    ensure_directory(package_path)
    object_path = f"{package_path}/{asset_name}.{asset_name}"
    if unreal.EditorAssetLibrary.does_asset_exist(object_path):
        asset = unreal.EditorAssetLibrary.load_asset(object_path)
        return asset, object_path, False

    factory = unreal.DataAssetFactory()
    set_if_present(factory, "data_asset_class", asset_class)
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(asset_name, package_path, asset_class, factory)
    if not asset:
        raise RuntimeError(f"Failed to create asset at {object_path}")
    return asset, object_path, True


def loadout_asset_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}/Characters"
    asset_name = f"DA_PMXCharacterLoadout_{index:03d}_{sanitize_segment(sample_id)}"
    return package_path, asset_name


def pair_asset_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}/Pairs"
    asset_name = f"DA_PMXEquipmentPair_{index:03d}_{sanitize_segment(sample_id)}"
    return package_path, asset_name


def registry_asset_path(asset_root: str, suite_slug: str) -> tuple[str, str]:
    package_path = f"{asset_root}/Registry/Suites/{suite_slug}"
    asset_name = f"DA_PMXEquipmentRegistry_{suite_slug}"
    return package_path, asset_name


def component_blueprint_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> str:
    return f"{asset_root}/Registry/Suites/{suite_slug}/Components/BP_PMXCharacterEquipmentComponent_{index:03d}_{sanitize_segment(sample_id)}"


def host_blueprint_path(asset_root: str, suite_slug: str, index: int, sample_id: str) -> str:
    return f"{asset_root}/Registry/Suites/{suite_slug}/Hosts/BP_PMXCharacterHost_{index:03d}_{sanitize_segment(sample_id)}"


def create_or_load_blueprint(asset_path: str, parent_class):
    object_path = object_path_from_asset_path(asset_path)
    if unreal.EditorAssetLibrary.does_asset_exist(object_path):
        blueprint = unreal.EditorAssetLibrary.load_asset(object_path)
        return blueprint, object_path, False

    package_path = asset_path.rsplit("/", 1)[0]
    ensure_directory(package_path)
    blueprint = unreal.BlueprintEditorLibrary.create_blueprint_asset_with_parent(asset_path, parent_class)
    if not blueprint:
        raise RuntimeError(f"Failed to create blueprint at {asset_path}")
    return blueprint, object_path, True


def compile_blueprint_asset(blueprint) -> None:
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    save_loaded_asset(blueprint)


def blueprint_generated_class(blueprint):
    generated_class = unreal.BlueprintEditorLibrary.generated_class(blueprint)
    if not generated_class:
        compile_blueprint_asset(blueprint)
        generated_class = unreal.BlueprintEditorLibrary.generated_class(blueprint)
    return generated_class


def blueprint_cdo(blueprint):
    generated_class = blueprint_generated_class(blueprint)
    if not generated_class:
        return None
    return unreal.get_default_object(generated_class)


def ensure_shared_blueprint_assets(asset_root: str) -> tuple[dict, list[str]]:
    definitions = [
        ("registry_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXEquipmentRegistryAsset", unreal.PMXEquipmentRegistryAsset),
        ("pair_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXEquipmentPairAsset", unreal.PMXEquipmentPairAsset),
        ("loadout_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterEquipmentLoadoutAsset", unreal.PMXEquipmentLoadoutAsset),
        ("component_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterEquipmentComponent", unreal.PMXCharacterEquipmentComponent),
        ("host_character_blueprint_asset", f"{asset_root}/Registry/Blueprints/BP_PMXCharacterHost", unreal.PMXCharacterHost),
    ]
    payload = {}
    warnings = []
    for key, asset_path, parent_class in definitions:
        try:
            blueprint, _, _ = create_or_load_blueprint(asset_path, parent_class)
            compile_blueprint_asset(blueprint)
            payload[key] = asset_path
        except Exception as exc:
            payload[key] = None
            warnings.append(f"shared_blueprint_create_failed:{key}:{exc}")
    return payload, warnings


__all__ = [
    "derive_suite_identity",
    "find_latest_registry_json",
    "create_or_load_data_asset",
    "loadout_asset_path",
    "pair_asset_path",
    "registry_asset_path",
    "component_blueprint_path",
    "host_blueprint_path",
    "create_or_load_blueprint",
    "compile_blueprint_asset",
    "blueprint_generated_class",
    "blueprint_cdo",
    "ensure_shared_blueprint_assets",
]
