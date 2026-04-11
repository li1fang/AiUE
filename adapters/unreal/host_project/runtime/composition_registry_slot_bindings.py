from __future__ import annotations

from .common import *


def default_slot_binding_dict(
    *,
    slot_name: str = "weapon",
    item_package_id: str = "",
    item_kind: str = "skeletal_mesh",
    attach_socket_name: str = "WeaponSocket",
    skeletal_mesh_path: str | None = None,
    static_mesh_path: str | None = None,
    niagara_system_path: str | None = None,
    consumer_ready: bool = False,
) -> dict:
    normalized_kind = normalized_item_kind_text(
        item_kind,
        skeletal_mesh=load_asset(skeletal_mesh_path),
        static_mesh=load_asset(static_mesh_path),
        niagara_system=load_asset(niagara_system_path),
    )
    return {
        "slot_name": slot_name_text(slot_name),
        "item_package_id": str(item_package_id or ""),
        "item_kind": normalized_kind,
        "attach_socket_name": str(attach_socket_name or "WeaponSocket"),
        "skeletal_mesh_asset": str(skeletal_mesh_path or "") if normalized_kind == "skeletal_mesh" else str(skeletal_mesh_path or ""),
        "static_mesh_asset": str(static_mesh_path or "") if normalized_kind == "static_mesh" else str(static_mesh_path or ""),
        "niagara_system_asset": str(niagara_system_path or "") if normalized_kind == "niagara_system" else str(niagara_system_path or ""),
        "consumer_ready": bool(consumer_ready),
    }


def pair_slot_bindings(pair: dict) -> list[dict]:
    attach_target = pair.get("preferred_attach_target") or {}
    return [
        default_slot_binding_dict(
            slot_name=pair.get("equip_slot") or "weapon",
            item_package_id=pair.get("weapon_package_id") or "",
            item_kind="skeletal_mesh",
            attach_socket_name=attach_target.get("name") or "WeaponSocket",
            skeletal_mesh_path=pair.get("weapon_skeletal_mesh"),
            consumer_ready=True,
        )
    ]


def loadout_slot_bindings(related_pairs: list[dict]) -> list[dict]:
    if not related_pairs:
        return []
    return pair_slot_bindings(related_pairs[0])


def unreal_slot_binding(binding: dict):
    entry = unreal.PMXEquipmentSlotBindingEntry()
    set_if_present(entry, "slot_name", binding.get("slot_name") or "weapon")
    set_if_present(entry, "item_package_id", str(binding.get("item_package_id") or ""))
    set_if_present(entry, "item_kind", str(binding.get("item_kind") or "skeletal_mesh"))
    set_if_present(entry, "attach_socket_name", binding.get("attach_socket_name") or "WeaponSocket")
    set_if_present(entry, "skeletal_mesh", load_asset(binding.get("skeletal_mesh_asset")))
    set_if_present(entry, "static_mesh", load_asset(binding.get("static_mesh_asset")))
    set_if_present(entry, "niagara_system", load_asset(binding.get("niagara_system_asset")))
    set_if_present(entry, "b_consumer_ready", bool(binding.get("consumer_ready")))
    set_if_present(entry, "consumer_ready", bool(binding.get("consumer_ready")))
    return entry


def unreal_slot_bindings(bindings: list[dict]) -> list:
    return [unreal_slot_binding(binding) for binding in bindings]


def configure_pair_asset(asset, pair: dict) -> None:
    entry = asset.get_editor_property("pair")
    slot_bindings = pair_slot_bindings(pair)
    set_if_present(entry, "sample_id", str(pair.get("sample_id") or ""))
    set_if_present(entry, "pair_id", str(pair.get("pair_id") or pair_id_for(pair.get("character_package_id"), pair.get("weapon_package_id"))))
    set_if_present(entry, "character_package_id", str(pair.get("character_package_id") or ""))
    set_if_present(entry, "weapon_package_id", str(pair.get("weapon_package_id") or ""))
    set_if_present(entry, "character_mesh", load_asset(pair.get("character_skeletal_mesh")))
    set_if_present(entry, "weapon_mesh", load_asset(pair.get("weapon_skeletal_mesh")))
    set_if_present(entry, "equip_slot", pair.get("equip_slot") or "weapon")
    attach_target = pair.get("preferred_attach_target") or {}
    set_if_present(entry, "attach_socket_name", attach_target.get("name") or "WeaponSocket")
    set_if_present(entry, "b_consumer_ready", True)
    set_if_present(entry, "consumer_ready", True)
    set_if_present(entry, "slot_bindings", unreal_slot_bindings(slot_bindings))
    asset.set_editor_property("pair", entry)
    save_loaded_asset(asset)


def configure_loadout_asset(asset, character: dict, default_pair_asset, related_pair_assets: list, related_pairs: list[dict]) -> None:
    loadout = asset.get_editor_property("loadout")
    default_pair = related_pairs[0] if related_pairs else {}
    slot_bindings = loadout_slot_bindings(related_pairs)
    set_if_present(loadout, "sample_id", str(character.get("sample_id") or ""))
    set_if_present(loadout, "character_package_id", str(character.get("package_id") or ""))
    set_if_present(loadout, "default_weapon_package_id", str(default_pair.get("weapon_package_id") or ""))
    set_if_present(loadout, "character_mesh", load_asset(character.get("skeletal_mesh")))
    set_if_present(loadout, "weapon_mesh", load_asset(default_pair.get("weapon_skeletal_mesh")))
    set_if_present(loadout, "equip_slot", default_pair.get("equip_slot") or "weapon")
    attach_target = default_pair.get("preferred_attach_target") or {}
    set_if_present(loadout, "attach_socket_name", attach_target.get("name") or "WeaponSocket")
    set_if_present(loadout, "default_pair_asset", default_pair_asset)
    set_if_present(loadout, "available_pair_assets", related_pair_assets)
    set_if_present(loadout, "available_weapon_package_ids", [str(pair.get("weapon_package_id") or "") for pair in related_pairs if pair.get("weapon_package_id")])
    set_if_present(loadout, "b_consumer_ready", bool(character.get("consumer_ready")))
    set_if_present(loadout, "consumer_ready", bool(character.get("consumer_ready")))
    set_if_present(loadout, "slot_bindings", unreal_slot_bindings(slot_bindings))
    asset.set_editor_property("loadout", loadout)
    save_loaded_asset(asset)


def configure_registry_asset(asset, suite_name: str, suite_slug: str, pair_assets: list, loadout_assets: list) -> None:
    asset.set_editor_property("suite_name", suite_name)
    asset.set_editor_property("suite_slug", suite_slug)
    asset.set_editor_property("pair_assets", pair_assets)
    asset.set_editor_property("character_loadouts", loadout_assets)
    save_loaded_asset(asset)


__all__ = [
    "default_slot_binding_dict",
    "pair_slot_bindings",
    "loadout_slot_bindings",
    "unreal_slot_binding",
    "unreal_slot_bindings",
    "configure_pair_asset",
    "configure_loadout_asset",
    "configure_registry_asset",
]
