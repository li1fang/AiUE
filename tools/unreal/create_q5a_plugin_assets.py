from __future__ import annotations

import unreal


ASSET_DIR = "/AiUEPmxRuntime/Q5A"
BASE_MATERIAL_PATH = f"{ASSET_DIR}/M_Q5A_UnlitMaskBase.M_Q5A_UnlitMaskBase"
BODY_INSTANCE_PATH = f"{ASSET_DIR}/MI_Q5A_BodyMask_Green.MI_Q5A_BodyMask_Green"
SLOT_INSTANCE_PATH = f"{ASSET_DIR}/MI_Q5A_SlotMask_Red.MI_Q5A_SlotMask_Red"
BODY_MATERIAL_PATH = f"{ASSET_DIR}/M_Q5A_BodyMask_Green.M_Q5A_BodyMask_Green"
SLOT_MATERIAL_PATH = f"{ASSET_DIR}/M_Q5A_SlotMask_Red.M_Q5A_SlotMask_Red"


def save_asset(asset) -> None:
    try:
        unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    except Exception:
        pass


def ensure_directory(path: str) -> None:
    if not unreal.EditorAssetLibrary.does_directory_exist(path):
        unreal.EditorAssetLibrary.make_directory(path)


def configure_base_material(material) -> None:
    if not material:
        return
    for property_name, value in (
        ("two_sided", True),
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_UNLIT),
        ("used_with_skeletal_mesh", True),
    ):
        try:
            material.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        unreal.MaterialEditingLibrary.recompile_material(material)
    except Exception:
        pass
    save_asset(material)


def configure_mask_material(material) -> None:
    if not material:
        return
    for property_name, value in (
        ("two_sided", True),
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_UNLIT),
        ("used_with_skeletal_mesh", True),
        ("used_with_static_meshes", True),
    ):
        try:
            material.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        unreal.MaterialEditingLibrary.recompile_material(material)
    except Exception:
        pass
    save_asset(material)


def ensure_base_material():
    material = unreal.EditorAssetLibrary.load_asset(BASE_MATERIAL_PATH)
    if material:
        configure_base_material(material)
        return material
    ensure_directory(ASSET_DIR)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = asset_tools.create_asset("M_Q5A_UnlitMaskBase", ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError("Failed to create M_Q5A_UnlitMaskBase.")
    parameter_expression = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionVectorParameter,
        -384,
        0,
    )
    parameter_expression.set_editor_property("parameter_name", "MaskColor")
    parameter_expression.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    configure_base_material(material)
    return material


def ensure_color_material(asset_name: str, asset_path: str, color: unreal.LinearColor):
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if material:
        configure_mask_material(material)
        return material
    ensure_directory(ASSET_DIR)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    material = asset_tools.create_asset(asset_name, ASSET_DIR, unreal.Material, unreal.MaterialFactoryNew())
    if not material:
        raise RuntimeError(f"Failed to create {asset_name}.")
    expression = unreal.MaterialEditingLibrary.create_material_expression(
        material,
        unreal.MaterialExpressionConstant3Vector,
        -384,
        0,
    )
    expression.set_editor_property("constant", color)
    unreal.MaterialEditingLibrary.connect_material_property(expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
    unreal.MaterialEditingLibrary.connect_material_property(expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    configure_mask_material(material)
    return material


def ensure_instance(instance_name: str, instance_path: str, parent_material, color: unreal.LinearColor):
    instance = unreal.EditorAssetLibrary.load_asset(instance_path)
    if instance:
        try:
            instance.set_editor_property("parent", parent_material)
        except Exception:
            pass
        try:
            unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(instance, "MaskColor", color)
        except Exception:
            pass
        save_asset(instance)
        return instance
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    instance = asset_tools.create_asset(instance_name, ASSET_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    if not instance:
        raise RuntimeError(f"Failed to create {instance_name}.")
    instance.set_editor_property("parent", parent_material)
    unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(instance, "MaskColor", color)
    save_asset(instance)
    return instance


def main():
    parent_material = ensure_base_material()
    ensure_color_material("M_Q5A_BodyMask_Green", BODY_MATERIAL_PATH, unreal.LinearColor(0.0, 1.0, 0.0, 1.0))
    ensure_color_material("M_Q5A_SlotMask_Red", SLOT_MATERIAL_PATH, unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    ensure_instance("MI_Q5A_BodyMask_Green", BODY_INSTANCE_PATH, parent_material, unreal.LinearColor(0.0, 1.0, 0.0, 1.0))
    ensure_instance("MI_Q5A_SlotMask_Red", SLOT_INSTANCE_PATH, parent_material, unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    try:
        unreal.EditorAssetLibrary.save_directory(ASSET_DIR, only_if_is_dirty=False, recursive=True)
    except Exception:
        pass
    unreal.log("Q5A plugin assets ensured.")


if __name__ == "__main__":
    main()
