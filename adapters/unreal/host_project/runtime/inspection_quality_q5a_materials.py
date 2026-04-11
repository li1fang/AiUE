from __future__ import annotations

from .common import *


Q5A_BODY_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_BodyMask_Green.M_Q5A_BodyMask_Green"
Q5A_SLOT_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_SlotMask_Red.M_Q5A_SlotMask_Red"
Q5A_BASE_MASK_MATERIAL_PATH = "/AiUEPmxRuntime/Q5A/M_Q5A_UnlitMaskBase.M_Q5A_UnlitMaskBase"
Q5A_ASSET_DIRECTORY = "/AiUEPmxRuntime/Q5A"


def _configure_q5a_base_material(base_material) -> None:
    if not base_material:
        return
    for property_name, value in (
        ("two_sided", True),
        ("blend_mode", unreal.BlendMode.BLEND_OPAQUE),
        ("shading_model", unreal.MaterialShadingModel.MSM_UNLIT),
        ("used_with_skeletal_mesh", True),
    ):
        try:
            base_material.set_editor_property(property_name, value)
        except Exception:
            pass
    try:
        unreal.MaterialEditingLibrary.recompile_material(base_material)
    except Exception:
        pass
    save_loaded_asset(base_material)


def _configure_q5a_color_material(material) -> None:
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
    save_loaded_asset(material)


def _ensure_q5a_color_material(asset_name: str, asset_path: str, color) -> object | None:
    material = unreal.EditorAssetLibrary.load_asset(asset_path)
    if material:
        _configure_q5a_color_material(material)
        return material
    try:
        if not unreal.EditorAssetLibrary.does_directory_exist(Q5A_ASSET_DIRECTORY):
            unreal.EditorAssetLibrary.make_directory(Q5A_ASSET_DIRECTORY)
    except Exception:
        pass
    try:
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        factory = unreal.MaterialFactoryNew()
        material = asset_tools.create_asset(asset_name, Q5A_ASSET_DIRECTORY, unreal.Material, factory)
        if material:
            color_expression = unreal.MaterialEditingLibrary.create_material_expression(
                material,
                unreal.MaterialExpressionConstant3Vector,
                -384,
                0,
            )
            color_expression.set_editor_property("constant", color)
            unreal.MaterialEditingLibrary.connect_material_property(color_expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
            unreal.MaterialEditingLibrary.connect_material_property(color_expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
            _configure_q5a_color_material(material)
        return material
    except Exception:
        return unreal.EditorAssetLibrary.load_asset(asset_path)


def _ensure_q5a_mask_materials() -> tuple[object, object, list[str]]:
    warnings = []
    body_material = unreal.EditorAssetLibrary.load_asset(Q5A_BODY_MASK_MATERIAL_PATH)
    slot_material = unreal.EditorAssetLibrary.load_asset(Q5A_SLOT_MASK_MATERIAL_PATH)
    if body_material and slot_material:
        _configure_q5a_color_material(body_material)
        _configure_q5a_color_material(slot_material)
        return body_material, slot_material, warnings

    try:
        if not unreal.EditorAssetLibrary.does_directory_exist(Q5A_ASSET_DIRECTORY):
            unreal.EditorAssetLibrary.make_directory(Q5A_ASSET_DIRECTORY)
    except Exception as exc:
        warnings.append(f"qa_material_directory_prepare_failed:{exc}")

    base_material = unreal.EditorAssetLibrary.load_asset(Q5A_BASE_MASK_MATERIAL_PATH)
    if not base_material:
        try:
            asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
            factory = unreal.MaterialFactoryNew()
            base_material = asset_tools.create_asset("M_Q5A_UnlitMaskBase", Q5A_ASSET_DIRECTORY, unreal.Material, factory)
            if base_material:
                parameter_expression = unreal.MaterialEditingLibrary.create_material_expression(
                    base_material,
                    unreal.MaterialExpressionVectorParameter,
                    -384,
                    0,
                )
                parameter_expression.set_editor_property("parameter_name", "MaskColor")
                parameter_expression.set_editor_property("default_value", unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
                unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_BASE_COLOR)
                unreal.MaterialEditingLibrary.connect_material_property(parameter_expression, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
                _configure_q5a_base_material(base_material)
        except Exception as exc:
            warnings.append(f"qa_material_create_failed:base:{exc}")
            base_material = unreal.EditorAssetLibrary.load_asset(Q5A_BASE_MASK_MATERIAL_PATH)
    if base_material:
        _configure_q5a_base_material(base_material)

    body_material = body_material or _ensure_q5a_color_material("M_Q5A_BodyMask_Green", Q5A_BODY_MASK_MATERIAL_PATH, unreal.LinearColor(0.0, 1.0, 0.0, 1.0))
    slot_material = slot_material or _ensure_q5a_color_material("M_Q5A_SlotMask_Red", Q5A_SLOT_MASK_MATERIAL_PATH, unreal.LinearColor(1.0, 0.0, 0.0, 1.0))
    if not body_material:
        body_material = unreal.EditorAssetLibrary.load_asset("/AiUEPmxRuntime/Q5A/MI_Q5A_BodyMask_Green.MI_Q5A_BodyMask_Green")
    if not slot_material:
        slot_material = unreal.EditorAssetLibrary.load_asset("/AiUEPmxRuntime/Q5A/MI_Q5A_SlotMask_Red.MI_Q5A_SlotMask_Red")
    try:
        save_directory(Q5A_ASSET_DIRECTORY)
    except Exception:
        pass
    return body_material, slot_material, warnings
