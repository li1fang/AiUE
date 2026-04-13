from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Convert a BVH animation file into an FBX file via Blender.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    return parser.parse_args(argv)


def write_report(path: Path | None, payload: dict) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for datablock_collection in (bpy.data.actions, bpy.data.armatures, bpy.data.meshes, bpy.data.objects):
        for datablock in list(datablock_collection):
            try:
                datablock_collection.remove(datablock)
            except Exception:
                continue


def attach_dummy_skinned_mesh(armature_object) -> bpy.types.Object:
    if armature_object is None or getattr(armature_object, "type", "") != "ARMATURE":
        raise RuntimeError("dummy_skin_requires_armature")
    armature_data = getattr(armature_object, "data", None)
    bones = list(getattr(armature_data, "bones", []) or [])
    if not bones:
        raise RuntimeError("dummy_skin_requires_bones")
    root_bone_name = str(bones[0].name)

    mesh_data = bpy.data.meshes.new("__aiue_motion_source_mesh")
    mesh_object = bpy.data.objects.new("__aiue_motion_source_mesh", mesh_data)
    bpy.context.scene.collection.objects.link(mesh_object)
    mesh_data.from_pydata(
        [(0.0, 0.0, 0.0), (0.0, 0.01, 0.0), (0.0, 0.0, 0.01)],
        [],
        [(0, 1, 2)],
    )
    mesh_data.update()

    vertex_group = mesh_object.vertex_groups.new(name=root_bone_name)
    vertex_group.add([0, 1, 2], 1.0, "REPLACE")

    modifier = mesh_object.modifiers.new(name="Armature", type="ARMATURE")
    modifier.object = armature_object
    mesh_object.parent = armature_object
    mesh_object.parent_type = "OBJECT"
    return mesh_object


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    report_path = Path(args.report).expanduser().resolve() if args.report else None

    payload = {
        "status": "fail",
        "input_path": str(input_path),
        "output_path": str(output_path),
        "warnings": [],
        "errors": [],
    }
    try:
        if not input_path.exists():
            raise FileNotFoundError(f"bvh_input_missing:{input_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        clear_scene()
        bpy.ops.import_anim.bvh(filepath=str(input_path), axis_forward="-Z", axis_up="Y")
        imported_objects = list(bpy.context.scene.objects)
        if not imported_objects:
            raise RuntimeError("bvh_import_produced_no_objects")
        active_object = next((obj for obj in imported_objects if obj.type == "ARMATURE"), imported_objects[0])
        dummy_mesh_object = attach_dummy_skinned_mesh(active_object)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in imported_objects:
            obj.select_set(obj == active_object and obj.type == "ARMATURE")
        dummy_mesh_object.select_set(True)
        bpy.context.view_layer.objects.active = active_object
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            check_existing=False,
            use_selection=True,
            object_types={"ARMATURE", "MESH"},
            add_leaf_bones=False,
            use_armature_deform_only=True,
            armature_nodetype="ROOT",
            bake_anim=True,
            bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=False,
            bake_anim_use_all_actions=False,
            bake_anim_force_startend_keying=True,
            path_mode="AUTO",
            axis_forward="-Z",
            axis_up="Y",
            primary_bone_axis="Y",
            secondary_bone_axis="X",
        )
        if not output_path.exists():
            raise RuntimeError("fbx_export_missing")
        payload.update(
            {
                "status": "pass",
                "imported_object_count": len(imported_objects) + 1,
                "active_object_name": str(getattr(active_object, "name", "") or ""),
                "dummy_mesh_object_name": str(getattr(dummy_mesh_object, "name", "") or ""),
            }
        )
    except Exception as exc:
        payload["errors"] = [str(exc), traceback.format_exc()]
        write_report(report_path, payload)
        return 1

    write_report(report_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
