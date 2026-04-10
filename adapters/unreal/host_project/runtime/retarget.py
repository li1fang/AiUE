from __future__ import annotations

from .common import *
from .capture import load_level
def animation_asset_payload(animation_asset) -> dict:
    payload = {
        "asset_path": "",
        "class_name": "",
        "skeleton_asset_path": "",
        "play_length_seconds": 0.0,
    }
    if not animation_asset:
        return payload
    try:
        payload["asset_path"] = animation_asset.get_path_name()
    except Exception:
        pass
    try:
        payload["class_name"] = animation_asset.get_class().get_name()
    except Exception:
        pass
    skeleton_asset = None
    for method_name in ("get_skeleton",):
        if hasattr(animation_asset, method_name):
            try:
                skeleton_asset = getattr(animation_asset, method_name)()
                if skeleton_asset:
                    break
            except Exception:
                continue
    if not skeleton_asset and hasattr(animation_asset, "get_editor_property"):
        try:
            skeleton_asset = animation_asset.get_editor_property("skeleton")
        except Exception:
            skeleton_asset = None
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
    for method_name in ("get_play_length",):
        if hasattr(animation_asset, method_name):
            try:
                payload["play_length_seconds"] = float(getattr(animation_asset, method_name)())
                break
            except Exception:
                continue
    if not payload["play_length_seconds"] and hasattr(animation_asset, "get_editor_property"):
        for property_name in ("sequence_length", "target_frame_rate"):
            try:
                raw_value = animation_asset.get_editor_property(property_name)
                if property_name == "sequence_length":
                    payload["play_length_seconds"] = float(raw_value or 0.0)
                    if payload["play_length_seconds"] > 0.0:
                        break
            except Exception:
                continue
    return payload


def load_asset_from_any_path(asset_path: str):
    if not asset_path:
        return None
    candidates = [str(asset_path)]
    if "." not in str(asset_path) and str(asset_path).startswith("/Game/"):
        candidates.append(object_path_from_asset_path(str(asset_path)))
    for candidate in candidates:
        try:
            asset = unreal.EditorAssetLibrary.load_asset(candidate)
        except Exception:
            asset = None
        if asset:
            return asset
    return None


def canonical_asset_path(asset_path: str) -> str:
    text = str(asset_path or "").strip()
    if not text:
        return ""
    tail = text.rsplit("/", 1)[-1]
    if "." in tail:
        return text.split(".", 1)[0]
    return text


def package_path_and_asset_name(asset_path: str) -> tuple[str, str]:
    normalized = canonical_asset_path(asset_path)
    if "/" not in normalized:
        return "", normalized
    package_path, asset_name = normalized.rsplit("/", 1)
    return package_path, asset_name


def skeletal_mesh_asset_from_component(component):
    if not component:
        return None
    for method_name in ("get_skeletal_mesh_asset",):
        if hasattr(component, method_name):
            try:
                skeletal_mesh_asset = getattr(component, method_name)()
                if skeletal_mesh_asset:
                    return skeletal_mesh_asset
            except Exception:
                continue
    if hasattr(component, "get_editor_property"):
        for property_name in ("skeletal_mesh_asset", "skeletal_mesh"):
            try:
                skeletal_mesh_asset = component.get_editor_property(property_name)
                if skeletal_mesh_asset:
                    return skeletal_mesh_asset
            except Exception:
                continue
    return None


def skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset):
    if not skeletal_mesh_asset:
        return None
    for method_name in ("get_skeleton",):
        if hasattr(skeletal_mesh_asset, method_name):
            try:
                skeleton_asset = getattr(skeletal_mesh_asset, method_name)()
                if skeleton_asset:
                    return skeleton_asset
            except Exception:
                continue
    if hasattr(skeletal_mesh_asset, "get_editor_property"):
        try:
            skeleton_asset = skeletal_mesh_asset.get_editor_property("skeleton")
            if skeleton_asset:
                return skeleton_asset
        except Exception:
            pass
    return None


def component_skeletal_mesh_and_skeleton_paths(component) -> tuple[str, str]:
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    skeletal_mesh_path = ""
    skeleton_path = ""
    if skeletal_mesh_asset:
        try:
            skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
        except Exception:
            skeletal_mesh_path = ""
    if skeleton_asset:
        try:
            skeleton_path = skeleton_asset.get_path_name()
        except Exception:
            skeleton_path = ""
    return skeletal_mesh_path, skeleton_path


def mesh_skeleton_payload(component) -> dict:
    payload = {
        "mesh_asset_path": component_asset_path(component),
        "skeleton_asset_path": "",
    }
    if not component:
        return payload
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
    return payload


def compatible_skeleton_paths(skeleton_asset) -> list[str]:
    if not skeleton_asset or not hasattr(skeleton_asset, "get_editor_property"):
        return []
    resolved = []
    try:
        items = list(skeleton_asset.get_editor_property("compatible_skeletons") or [])
    except Exception:
        items = []
    for item in items:
        try:
            path = item.get_path_name()
        except Exception:
            path = ""
        if path:
            resolved.append(path)
    return sorted(set(resolved))


def normalize_bone_name(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u4e00-\u9fff]+", "", normalized)


CANONICAL_HUMANOID_MARKERS = {
    "root": ["root"],
    "pelvis": ["pelvis", "hips", "hip", "center", "waist"],
    "spine_lower": ["spine", "spine1", "spine01", "spinelower"],
    "spine_upper": ["spine2", "spine02", "spine3", "spine03", "chest", "upperchest"],
    "neck": ["neck"],
    "head": ["head"],
    "arm_l": ["upperarml", "leftarm", "lupperarm", "arml", "leftupperarm"],
    "arm_r": ["upperarmr", "rightarm", "rupperarm", "armr", "rightupperarm"],
    "hand_l": ["handl", "lefthand", "lhand"],
    "hand_r": ["handr", "righthand", "rhand"],
    "leg_l": ["thighl", "uplegl", "leftleg", "lthigh", "leftupleg"],
    "leg_r": ["thighr", "uplegr", "rightleg", "rthigh", "rightupleg"],
    "foot_l": ["footl", "leftfoot", "lfoot"],
    "foot_r": ["footr", "rightfoot", "rfoot"],
}


def reference_skeleton_from_assets(skeleton_asset=None, skeletal_mesh_asset=None):
    for owner in (skeletal_mesh_asset, skeleton_asset):
        if not owner:
            continue
        for method_name in ("get_reference_skeleton", "get_ref_skeleton"):
            if hasattr(owner, method_name):
                try:
                    reference_skeleton = getattr(owner, method_name)()
                    if reference_skeleton:
                        return reference_skeleton
                except Exception:
                    continue
        if hasattr(owner, "get_editor_property"):
            for property_name in ("reference_skeleton", "ref_skeleton"):
                try:
                    reference_skeleton = owner.get_editor_property(property_name)
                    if reference_skeleton:
                        return reference_skeleton
                except Exception:
                    continue
    return None


def reference_skeleton_bone_names(reference_skeleton) -> tuple[list[str], str]:
    if not reference_skeleton:
        return [], "missing_reference_skeleton"
    for method_name in ("get_raw_bone_names", "get_bone_names"):
        if hasattr(reference_skeleton, method_name):
            try:
                names = [str(item) for item in list(getattr(reference_skeleton, method_name)() or []) if str(item)]
            except Exception:
                names = []
            if names:
                return names, f"reference_skeleton:{method_name}"
    if hasattr(reference_skeleton, "get_editor_property"):
        for property_name in ("raw_bone_names", "bone_names"):
            try:
                raw_names = list(reference_skeleton.get_editor_property(property_name) or [])
            except Exception:
                raw_names = []
            names = [str(item) for item in raw_names if str(item)]
            if names:
                return names, f"reference_skeleton_property:{property_name}"
    count = 0
    for method_name in ("get_num", "get_raw_bone_num", "get_bone_count"):
        if hasattr(reference_skeleton, method_name):
            try:
                count = int(getattr(reference_skeleton, method_name)() or 0)
            except Exception:
                count = 0
            if count:
                break
    if count and hasattr(reference_skeleton, "get_bone_name"):
        names = []
        for index in range(count):
            try:
                bone_name = str(reference_skeleton.get_bone_name(index))
            except Exception:
                bone_name = ""
            if bone_name:
                names.append(bone_name)
        if names:
            return names, "reference_skeleton:indexed"
    return [], "reference_skeleton_unresolved"


def skeleton_bone_names(skeleton_asset=None, skeletal_mesh_asset=None) -> tuple[list[str], str]:
    reference_skeleton = reference_skeleton_from_assets(skeleton_asset, skeletal_mesh_asset)
    names, source = reference_skeleton_bone_names(reference_skeleton)
    if names:
        return names, source
    skeleton_owner = skeleton_asset
    if not skeleton_owner and skeletal_mesh_asset:
        try:
            skeleton_owner = getattr(skeletal_mesh_asset, "skeleton")
        except Exception:
            skeleton_owner = None
        if not skeleton_owner and hasattr(skeletal_mesh_asset, "get_editor_property"):
            try:
                skeleton_owner = skeletal_mesh_asset.get_editor_property("skeleton")
            except Exception:
                skeleton_owner = None
    if skeleton_owner and hasattr(skeleton_owner, "get_reference_pose"):
        try:
            reference_pose = skeleton_owner.get_reference_pose()
        except Exception:
            reference_pose = None
        if reference_pose and hasattr(reference_pose, "get_bone_names"):
            try:
                pose_names = [str(item) for item in list(reference_pose.get_bone_names() or []) if str(item)]
            except Exception:
                pose_names = []
            if pose_names:
                return pose_names, "reference_pose:get_bone_names"
    if skeleton_asset and hasattr(skeleton_asset, "get_editor_property"):
        try:
            bone_tree = list(skeleton_asset.get_editor_property("bone_tree") or [])
        except Exception:
            bone_tree = []
        extracted = []
        for entry in bone_tree:
            bone_name = ""
            for attribute_name in ("name", "bone_name"):
                try:
                    value = getattr(entry, attribute_name)
                    bone_name = str(value) if value else ""
                except Exception:
                    bone_name = ""
                if bone_name:
                    break
            if bone_name:
                extracted.append(bone_name)
        if extracted:
            return extracted, "skeleton:bone_tree"
    return [], source


def skeleton_socket_names(skeleton_asset) -> list[str]:
    if not skeleton_asset or not hasattr(skeleton_asset, "get_editor_property"):
        return []
    try:
        sockets = list(skeleton_asset.get_editor_property("sockets") or [])
    except Exception:
        sockets = []
    names = []
    for socket in sockets:
        try:
            socket_name = str(socket.get_editor_property("socket_name"))
        except Exception:
            socket_name = ""
        if socket_name:
            names.append(socket_name)
    return sorted(set(names))


def humanoid_marker_summary(bone_names: list[str]) -> dict:
    normalized = {}
    for raw_name in bone_names:
        key = normalize_bone_name(raw_name)
        if key and key not in normalized:
            normalized[key] = str(raw_name)
    hits = {}
    for marker, aliases in CANONICAL_HUMANOID_MARKERS.items():
        matched_name = ""
        for alias in aliases:
            alias_key = normalize_bone_name(alias)
            if alias_key in normalized:
                matched_name = normalized[alias_key]
                break
        hits[marker] = matched_name
    matched = sorted([marker for marker, name in hits.items() if name])
    missing = sorted([marker for marker, name in hits.items() if not name])
    core_markers = ["pelvis", "head", "arm_l", "arm_r", "leg_l", "leg_r"]
    core_present = sorted([marker for marker in core_markers if hits.get(marker)])
    return {
        "matched_markers": matched,
        "missing_markers": missing,
        "marker_hits": hits,
        "canonical_marker_score": round(float(len(matched)) / float(len(CANONICAL_HUMANOID_MARKERS)), 4),
        "core_chain_markers_present": len(core_present),
        "core_chain_markers_total": len(core_markers),
        "core_ready": len(core_present) >= 4,
        "manual_chain_mapping_likely": len(core_present) < 6,
    }


def skeleton_profile_payload_from_assets(skeleton_asset=None, skeletal_mesh_asset=None) -> dict:
    bone_names, bone_source = skeleton_bone_names(skeleton_asset, skeletal_mesh_asset)
    socket_names = skeleton_socket_names(skeleton_asset)
    payload = {
        "skeleton_asset_path": "",
        "skeletal_mesh_asset_path": "",
        "preview_mesh_asset_path": "",
        "bone_count": len(bone_names),
        "root_bone_name": bone_names[0] if bone_names else "",
        "bone_name_source": bone_source,
        "bone_name_sample": bone_names[:24],
        "socket_count": len(socket_names),
        "socket_names": socket_names[:24],
        "humanoid_markers": humanoid_marker_summary(bone_names),
        "warnings": [],
    }
    if skeleton_asset:
        try:
            payload["skeleton_asset_path"] = skeleton_asset.get_path_name()
        except Exception:
            pass
        if hasattr(skeleton_asset, "get_preview_mesh"):
            try:
                preview_mesh = skeleton_asset.get_preview_mesh()
            except Exception:
                preview_mesh = None
            if preview_mesh:
                try:
                    payload["preview_mesh_asset_path"] = preview_mesh.get_path_name()
                except Exception:
                    pass
    if skeletal_mesh_asset:
        try:
            payload["skeletal_mesh_asset_path"] = skeletal_mesh_asset.get_path_name()
        except Exception:
            pass
    if not bone_names:
        payload["warnings"].append("bone_names_unresolved")
    return payload


def skeleton_profile_payload_from_component(component) -> dict:
    skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    payload = skeleton_profile_payload_from_assets(skeleton_asset, skeletal_mesh_asset)
    payload["component_mesh_asset_path"] = component_asset_path(component)
    return payload


def animation_skeleton_profile_payload(animation_asset) -> dict:
    animation_payload = animation_asset_payload(animation_asset)
    skeleton_asset = load_asset_from_any_path(animation_payload.get("skeleton_asset_path") or "")
    payload = skeleton_profile_payload_from_assets(skeleton_asset)
    payload["animation_asset_path"] = animation_payload.get("asset_path") or ""
    payload["animation_class_name"] = animation_payload.get("class_name") or ""
    payload["animation_play_length_seconds"] = float(animation_payload.get("play_length_seconds") or 0.0)
    return payload


def asset_entries_by_class_names(asset_root: str, class_names: set[str], limit: int = 500) -> list[dict]:
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = list(registry.get_assets_by_path(to_name(asset_root), recursive=True))
    entries = []
    for asset_data in assets:
        class_name = asset_class_name(asset_data)
        if class_name not in class_names:
            continue
        entries.append(
            {
                "object_path": asset_object_path(asset_data),
                "package_name": str(asset_data.package_name),
                "asset_name": str(asset_data.asset_name),
                "asset_class": class_name,
            }
        )
    entries = sorted(entries, key=lambda item: item["object_path"])
    return entries[:limit]


def struct_field_value(struct_value, field_names: list[str]):
    for field_name in field_names:
        try:
            value = getattr(struct_value, field_name)
        except Exception:
            value = None
        if value not in (None, ""):
            return value
        if hasattr(struct_value, "get_editor_property"):
            try:
                value = struct_value.get_editor_property(field_name)
            except Exception:
                value = None
            if value not in (None, ""):
                return value
    return None


def ik_rig_chain_records(controller) -> list[dict]:
    try:
        raw_chains = list(controller.get_retarget_chains() or [])
    except Exception:
        raw_chains = []
    records = []
    for chain in raw_chains:
        chain_name = str(struct_field_value(chain, ["chain_name", "chain"]) or "")
        start_bone = ""
        end_bone = ""
        goal_name = ""
        if chain_name:
            try:
                start_bone = str(controller.get_retarget_chain_start_bone(to_name(chain_name)) or "")
            except Exception:
                start_bone = ""
            try:
                end_bone = str(controller.get_retarget_chain_end_bone(to_name(chain_name)) or "")
            except Exception:
                end_bone = ""
            try:
                goal_name = str(controller.get_retarget_chain_goal(to_name(chain_name)) or "")
            except Exception:
                goal_name = ""
        if not start_bone:
            start_bone = str(struct_field_value(chain, ["start_bone_name"]) or "")
        if not end_bone:
            end_bone = str(struct_field_value(chain, ["end_bone_name"]) or "")
        if not goal_name:
            goal_name = str(struct_field_value(chain, ["ik_goal_name", "goal_name"]) or "")
        records.append(
            {
                "chain_name": chain_name,
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": goal_name,
            }
        )
    return records


def ik_rig_profile_payload(ik_rig_asset) -> dict:
    if not ik_rig_asset:
        return {
            "asset_path": "",
            "skeletal_mesh_asset_path": "",
            "skeleton_asset_path": "",
            "retarget_root": "",
            "chain_count": 0,
            "chains": [],
        }
    controller = unreal.IKRigController.get_controller(ik_rig_asset)
    skeletal_mesh_asset = controller.get_skeletal_mesh() if controller else None
    skeletal_mesh_path = ""
    skeleton_path = ""
    if skeletal_mesh_asset:
        try:
            skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
        except Exception:
            skeletal_mesh_path = ""
        skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
        if skeleton_asset:
            try:
                skeleton_path = skeleton_asset.get_path_name()
            except Exception:
                skeleton_path = ""
    retarget_root = ""
    if controller:
        try:
            retarget_root = str(controller.get_retarget_root() or "")
        except Exception:
            retarget_root = ""
    chains = ik_rig_chain_records(controller) if controller else []
    asset_path = ""
    try:
        asset_path = canonical_asset_path(ik_rig_asset.get_path_name())
    except Exception:
        asset_path = ""
    return {
        "asset_path": asset_path,
        "skeletal_mesh_asset_path": skeletal_mesh_path,
        "skeleton_asset_path": skeleton_path,
        "retarget_root": retarget_root,
        "chain_count": len(chains),
        "chains": chains,
    }


def base_name_from_asset_path(asset_path: str) -> str:
    text = str(asset_path or "")
    if not text:
        return ""
    package_name = text.split(".", 1)[0]
    return package_name.rsplit("/", 1)[-1]


def matching_asset_entries(entries: list[dict], keywords: list[str], class_name: str | None = None) -> list[dict]:
    lowered_keywords = [str(item).strip().lower() for item in keywords if str(item).strip()]
    matched = []
    for entry in entries:
        if class_name and entry.get("asset_class") != class_name:
            continue
        haystack = " ".join([entry.get("object_path") or "", entry.get("package_name") or "", entry.get("asset_name") or ""]).lower()
        if not lowered_keywords or any(keyword in haystack for keyword in lowered_keywords):
            matched.append(entry)
    return matched


def retarget_tooling_inventory(sample_id: str, package_id: str, source_profile: dict, target_profile: dict) -> dict:
    entries = asset_entries_by_class_names("/Game", {"IKRigDefinition", "IKRetargeter"}, limit=500)
    source_keywords = [
        sample_id,
        package_id,
        base_name_from_asset_path(source_profile.get("skeleton_asset_path") or ""),
        "pmxpipeline",
    ]
    target_keywords = [
        "mannequin",
        base_name_from_asset_path(target_profile.get("skeleton_asset_path") or ""),
        base_name_from_asset_path(target_profile.get("preview_mesh_asset_path") or ""),
    ]
    retargeter_keywords = source_keywords + target_keywords + ["retarget"]
    return {
        "ik_rig_definition_available": hasattr(unreal, "IKRigDefinition"),
        "ik_retargeter_available": hasattr(unreal, "IKRetargeter"),
        "can_author_new_retarget_assets": bool(hasattr(unreal, "IKRigDefinition") and hasattr(unreal, "IKRetargeter")),
        "project_asset_counts": {
            "ik_rigs": sum(1 for entry in entries if entry.get("asset_class") == "IKRigDefinition"),
            "ik_retargeters": sum(1 for entry in entries if entry.get("asset_class") == "IKRetargeter"),
        },
        "matching_source_ik_rigs": matching_asset_entries(entries, source_keywords, class_name="IKRigDefinition")[:16],
        "matching_target_ik_rigs": matching_asset_entries(entries, target_keywords, class_name="IKRigDefinition")[:16],
        "matching_retargeters": matching_asset_entries(entries, retargeter_keywords, class_name="IKRetargeter")[:16],
        "asset_sample": entries[:24],
    }


def retarget_recommendations(compatibility: dict, source_profile: dict, target_profile: dict, tooling: dict) -> list[str]:
    recommendations = []
    if compatibility.get("compatible"):
        recommendations.append("Direct skeleton compatibility already exists; you can skip retarget setup and move straight to a real animation preview.")
        return recommendations
    if not tooling.get("can_author_new_retarget_assets"):
        recommendations.append("Enable the IKRig plugin in AiUEdemo so Unreal exposes IKRigDefinition and IKRetargeter authoring APIs.")
    if source_profile.get("skeleton_asset_path"):
        recommendations.append(f"Create a source IKRig for the imported PMX skeleton: {source_profile.get('skeleton_asset_path')}.")
    if target_profile.get("skeleton_asset_path"):
        recommendations.append(f"Create or reuse a target mannequin IKRig for: {target_profile.get('skeleton_asset_path')}.")
    if not tooling.get("matching_retargeters"):
        recommendations.append("Create an IKRetargeter that maps the imported PMX rig to the mannequin rig before retrying animation-preview.")
    if (source_profile.get("humanoid_markers") or {}).get("manual_chain_mapping_likely"):
        recommendations.append("Expect manual retarget chain setup because the imported skeleton does not expose the full set of canonical humanoid bone names.")
    if not recommendations:
        recommendations.append("Inspect existing IKRig and IKRetargeter assets in the project and bind the imported skeleton to the closest mannequin retarget path.")
    return recommendations


def resolve_enum_member(enum_type_names: tuple[str, ...], member_names: tuple[str, ...]):
    for enum_name in enum_type_names:
        enum_type = getattr(unreal, enum_name, None)
        if not enum_type:
            continue
        for member_name in member_names:
            if hasattr(enum_type, member_name):
                return getattr(enum_type, member_name)
    return None


def retarget_source_enum_value():
    return resolve_enum_member(("RetargetSourceOrTarget", "ERetargetSourceOrTarget"), ("Source", "SOURCE"))


def retarget_target_enum_value():
    return resolve_enum_member(("RetargetSourceOrTarget", "ERetargetSourceOrTarget"), ("Target", "TARGET"))


def auto_map_chain_type_value():
    return resolve_enum_member(("AutoMapChainType", "EAutoMapChainType"), ("Exact", "EXACT", "Fuzzy", "FUZZY"))


SOURCE_CHAIN_SPECS = [
    {
        "chain_name": "root",
        "start_aliases": [["root"], ["\u5168\u3066\u306e\u89aa"], ["\u30bb\u30f3\u30bf\u30fc"], ["center"], ["groove"]],
        "end_aliases": [["hips"], ["pelvis"], ["\u4e0b\u534a\u8eab"], ["\u8170"], ["center"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "Spine",
        "start_aliases": [["spine", "1"], ["\u4e0a\u534a\u8eab"], ["spine"]],
        "end_aliases": [["spine", "2"], ["\u4e0a\u534a\u8eab2"], ["chest"], ["spine", "3"], ["upper", "chest"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "Neck",
        "start_aliases": [["neck"], ["\u9996"]],
        "end_aliases": [["neck"], ["\u9996"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "head",
        "start_aliases": [["head"], ["\u982d"]],
        "end_aliases": [["head"], ["\u982d"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "LeftClavicle",
        "start_aliases": [["left", "clavicle"], ["clavicle", "l"], ["left", "shoulder"], ["\u5de6\u80a9"]],
        "end_aliases": [["left", "clavicle"], ["clavicle", "l"], ["left", "shoulder"], ["\u5de6\u80a9"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "RightClavicle",
        "start_aliases": [["right", "clavicle"], ["clavicle", "r"], ["right", "shoulder"], ["\u53f3\u80a9"]],
        "end_aliases": [["right", "clavicle"], ["clavicle", "r"], ["right", "shoulder"], ["\u53f3\u80a9"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "LeftArm",
        "start_aliases": [["left", "upper", "arm"], ["upperarm", "l"], ["arm", "l"], ["\u5de6\u8155"]],
        "end_aliases": [["left", "hand"], ["hand", "l"], ["\u5de6\u624b\u9996"], ["\u5de6\u624b"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "RightArm",
        "start_aliases": [["right", "upper", "arm"], ["upperarm", "r"], ["arm", "r"], ["\u53f3\u8155"]],
        "end_aliases": [["right", "hand"], ["hand", "r"], ["\u53f3\u624b\u9996"], ["\u53f3\u624b"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "LeftLeg",
        "start_aliases": [["left", "thigh"], ["thigh", "l"], ["left", "leg"], ["\u5de6\u8db3"], ["\u5de6\u8db3\u4e0a"]],
        "end_aliases": [["left", "foot"], ["foot", "l"], ["\u5de6\u8db3\u9996"], ["\u5de6\u8db3"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "RightLeg",
        "start_aliases": [["right", "thigh"], ["thigh", "r"], ["right", "leg"], ["\u53f3\u8db3"], ["\u53f3\u8db3\u4e0a"]],
        "end_aliases": [["right", "foot"], ["foot", "r"], ["\u53f3\u8db3\u9996"], ["\u53f3\u8db3"]],
        "allow_same_bone": False,
    },
    {
        "chain_name": "LeftToe",
        "start_aliases": [["left", "toe"], ["toe", "l"], ["\u5de6\u3064\u307e\u5148"]],
        "end_aliases": [["left", "toe"], ["toe", "l"], ["\u5de6\u3064\u307e\u5148"]],
        "allow_same_bone": True,
    },
    {
        "chain_name": "RightToe",
        "start_aliases": [["right", "toe"], ["toe", "r"], ["\u53f3\u3064\u307e\u5148"]],
        "end_aliases": [["right", "toe"], ["toe", "r"], ["\u53f3\u3064\u307e\u5148"]],
        "allow_same_bone": True,
    },
]


def numeric_suffix(text: str) -> int:
    match = re.search(r"(\d+)$", str(text or ""))
    return int(match.group(1)) if match else -1


def pmx_plain_side_bones(bone_names: list[str], side_token: str) -> list[str]:
    pattern = re.compile(rf"^Bone_{re.escape(side_token)}_(\d+)$", re.IGNORECASE)
    matched = []
    for bone_name in bone_names:
        if pattern.match(str(bone_name or "")):
            matched.append(str(bone_name))
    matched.sort(key=numeric_suffix)
    return matched


def pmx_neutral_numbered_bones(bone_names: list[str]) -> list[str]:
    pattern = re.compile(r"^Bone_(\d+)$", re.IGNORECASE)
    matched = []
    for bone_name in bone_names:
        if pattern.match(str(bone_name or "")):
            matched.append(str(bone_name))
    matched.sort(key=numeric_suffix)
    return matched


def pmx_numbered_prefix_groups(bone_names: list[str], limit: int = 12) -> list[dict]:
    grouped = {}
    for bone_name in bone_names:
        text = str(bone_name or "")
        match = re.match(r"^(.*?)(\d+)$", text)
        if not match:
            continue
        prefix = match.group(1)
        grouped.setdefault(prefix, []).append(text)
    records = []
    for prefix, names in grouped.items():
        ordered = sorted(names, key=numeric_suffix)
        records.append(
            {
                "prefix": prefix,
                "count": len(ordered),
                "sample": ordered[: min(8, len(ordered))],
            }
        )
    records.sort(key=lambda item: (-int(item["count"]), item["prefix"]))
    return records[:limit]


def pmx_upper_body_fallback_chains(bone_names: list[str]) -> tuple[list[dict], list[str], dict]:
    planned = []
    warnings = []
    diagnostics = {
        "strategy": "pmx_numeric_upper_body",
        "plain_right_bones": pmx_plain_side_bones(bone_names, "R"),
        "plain_left_bones": pmx_plain_side_bones(bone_names, "L"),
        "neutral_numbered_bones": pmx_neutral_numbered_bones(bone_names),
    }

    def add_chain(chain_name: str, start_bone: str, end_bone: str, reason: str) -> None:
        if not start_bone or not end_bone:
            return
        planned.append(
            {
                "chain_name": chain_name,
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": "",
                "planning_reason": reason,
            }
        )

    groove_bone = pick_best_bone_name(bone_names, [["groove"], ["center"], ["\u5168\u3066\u306e\u89aa"], ["\u30bb\u30f3\u30bf\u30fc"]])
    waist_bone = pick_best_bone_name(bone_names, [["waist"], ["\u8170"], ["\u4e0b\u534a\u8eab"]])
    neutral_numbered = diagnostics["neutral_numbered_bones"]
    first_neutral = neutral_numbered[0] if neutral_numbered else ""
    second_neutral = neutral_numbered[1] if len(neutral_numbered) > 1 else ""
    if groove_bone:
        add_chain("root", groove_bone, groove_bone, "pmx_generic_root")
    if waist_bone and first_neutral and waist_bone != first_neutral:
        add_chain("Spine", waist_bone, first_neutral, "pmx_generic_waist_to_first_neutral")
    elif waist_bone and second_neutral and waist_bone != second_neutral:
        add_chain("Spine", waist_bone, second_neutral, "pmx_generic_waist_to_second_neutral")

    right_plain = diagnostics["plain_right_bones"]
    left_plain = diagnostics["plain_left_bones"]
    if len(right_plain) >= 1:
        add_chain("RightClavicle", right_plain[0], right_plain[0], "pmx_plain_r_first")
    if len(right_plain) >= 4:
        add_chain("RightArm", right_plain[1], right_plain[4] if len(right_plain) >= 5 else right_plain[-1], "pmx_plain_r_arm_span")
    elif len(right_plain) >= 3:
        add_chain("RightArm", right_plain[1], right_plain[-1], "pmx_plain_r_arm_short")
    if len(left_plain) >= 1:
        add_chain("LeftClavicle", left_plain[0], left_plain[0], "pmx_plain_l_first")
    if len(left_plain) >= 4:
        add_chain("LeftArm", left_plain[1], left_plain[4] if len(left_plain) >= 5 else left_plain[-1], "pmx_plain_l_arm_span")
    elif len(left_plain) >= 3:
        add_chain("LeftArm", left_plain[1], left_plain[-1], "pmx_plain_l_arm_short")

    if not any(item["chain_name"] == "RightArm" for item in planned):
        warnings.append("pmx_upper_body_fallback_right_arm_unresolved")
    if not any(item["chain_name"] == "LeftArm" for item in planned):
        warnings.append("pmx_upper_body_fallback_left_arm_unresolved")
    return planned, warnings, diagnostics


def bone_names_from_ik_rig_controller(controller) -> tuple[list[str], str]:
    if not controller:
        return [], "controller_missing"
    try:
        skeletal_mesh_asset = controller.get_skeletal_mesh()
    except Exception:
        skeletal_mesh_asset = None
    if not skeletal_mesh_asset:
        return [], "ik_rig_skeletal_mesh_missing"
    skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    try:
        direct_skeleton = skeletal_mesh_asset.skeleton
        if direct_skeleton:
            skeleton_asset = direct_skeleton
    except Exception:
        pass
    if skeleton_asset and hasattr(skeleton_asset, "get_reference_pose"):
        try:
            reference_pose = skeleton_asset.get_reference_pose()
        except Exception:
            reference_pose = None
        if reference_pose and hasattr(reference_pose, "get_bone_names"):
            try:
                names = [str(item) for item in list(reference_pose.get_bone_names() or []) if str(item)]
            except Exception:
                names = []
            if names:
                return names, "ik_rig_skeletal_mesh.skeleton.reference_pose"
    return skeleton_bone_names(skeleton_asset, skeletal_mesh_asset)


def pick_best_bone_name(bone_names: list[str], alias_groups: list[list[str]]) -> str:
    normalized_pairs = [(str(name), normalize_bone_name(name)) for name in bone_names if str(name)]
    best_name = ""
    best_score = -1
    for original_name, normalized_name in normalized_pairs:
        for alias_group in alias_groups:
            if not alias_group:
                continue
            score = 0
            for alias in alias_group:
                alias_key = normalize_bone_name(alias)
                if alias_key and alias_key in normalized_name:
                    score += len(alias_key)
                else:
                    score = -1
                    break
            if score > best_score:
                best_score = score
                best_name = original_name
    return best_name if best_score > 0 else ""


def planned_source_chain_records(bone_names: list[str]) -> tuple[list[dict], list[str], dict]:
    planned = []
    warnings = []
    alias_match_records = []
    for spec in SOURCE_CHAIN_SPECS:
        start_bone = pick_best_bone_name(bone_names, spec["start_aliases"])
        end_bone = pick_best_bone_name(bone_names, spec["end_aliases"])
        if not start_bone and end_bone:
            start_bone = end_bone
        if not end_bone and start_bone and spec.get("allow_same_bone"):
            end_bone = start_bone
        if not start_bone or not end_bone:
            warnings.append(f"source_chain_unresolved:{spec['chain_name']}")
            continue
        if start_bone == end_bone and not spec.get("allow_same_bone"):
            warnings.append(f"source_chain_same_bone_skipped:{spec['chain_name']}:{start_bone}")
            continue
        planned.append(
            {
                "chain_name": spec["chain_name"],
                "start_bone": start_bone,
                "end_bone": end_bone,
                "goal_name": "",
                "planning_reason": "alias_match",
            }
        )
        alias_match_records.append(
            {
                "chain_name": spec["chain_name"],
                "start_bone": start_bone,
                "end_bone": end_bone,
            }
        )

    planned_by_name = {entry["chain_name"]: dict(entry) for entry in planned}
    pmx_fallback_plans, pmx_warnings, pmx_diagnostics = pmx_upper_body_fallback_chains(bone_names)
    warnings.extend(pmx_warnings)
    for fallback in pmx_fallback_plans:
        chain_name = str(fallback.get("chain_name") or "")
        if chain_name and chain_name not in planned_by_name:
            planned_by_name[chain_name] = dict(fallback)

    preferred_order = [str(spec.get("chain_name") or "") for spec in SOURCE_CHAIN_SPECS]
    planned = []
    for chain_name in preferred_order:
        if chain_name and chain_name in planned_by_name:
            planned.append(planned_by_name[chain_name])
    for chain_name, payload in planned_by_name.items():
        if chain_name not in preferred_order:
            planned.append(payload)

    diagnostics = {
        "alias_match_records": alias_match_records,
        "pmx_fallback": pmx_diagnostics,
        "numbered_prefix_groups": pmx_numbered_prefix_groups(bone_names),
        "planned_chain_names": [item.get("chain_name") for item in planned if item.get("chain_name")],
    }
    return planned, warnings, diagnostics


def create_or_load_ik_rig_asset(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    existing = load_asset_from_any_path(normalized)
    if existing:
        return existing, False
    package_path, asset_name = package_path_and_asset_name(normalized)
    ensure_directory(package_path)
    created = unreal.IKRigDefinitionFactory.create_new_ik_rig_asset(package_path, asset_name)
    return created, True


def create_or_load_retargeter_asset(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    existing = load_asset_from_any_path(normalized)
    if existing:
        return existing, False
    package_path, asset_name = package_path_and_asset_name(normalized)
    ensure_directory(package_path)
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    created = asset_tools.create_asset(asset_name, package_path, unreal.IKRetargeter, unreal.IKRetargetFactory())
    return created, True


def choose_target_ik_rig_asset(animation_asset, preferred_asset_path: str = "") -> tuple[object | None, dict]:
    if preferred_asset_path:
        preferred_asset = load_asset_from_any_path(preferred_asset_path)
        if preferred_asset:
            return preferred_asset, {
                "selection_mode": "preferred_asset_path",
                "requested_asset_path": preferred_asset_path,
                "resolved_asset_path": canonical_asset_path(preferred_asset.get_path_name()),
                "candidate_count": 1,
            }
    animation_payload = animation_asset_payload(animation_asset)
    animation_skeleton_path = str(animation_payload.get("skeleton_asset_path") or "")
    entries = asset_entries_by_class_names("/Game", {"IKRigDefinition"}, limit=500)
    best_asset = None
    best_metadata = None
    best_score = -1
    for entry in entries:
        asset = load_asset_from_any_path(entry["object_path"])
        if not asset:
            continue
        controller = unreal.IKRigController.get_controller(asset)
        if not controller:
            continue
        try:
            skeletal_mesh_asset = controller.get_skeletal_mesh()
        except Exception:
            skeletal_mesh_asset = None
        skeletal_mesh_path = ""
        skeleton_path = ""
        if skeletal_mesh_asset:
            try:
                skeletal_mesh_path = skeletal_mesh_asset.get_path_name()
            except Exception:
                skeletal_mesh_path = ""
            skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
            if skeleton_asset:
                try:
                    skeleton_path = skeleton_asset.get_path_name()
                except Exception:
                    skeleton_path = ""
        score = 0
        reasons = []
        if animation_skeleton_path and skeleton_path and animation_skeleton_path == skeleton_path:
            score += 100
            reasons.append("exact_animation_skeleton_match")
        lowered = " ".join([entry.get("object_path") or "", skeletal_mesh_path, skeleton_path]).lower()
        if "mannequin" in lowered:
            score += 20
            reasons.append("mannequin_keyword")
        if "ue5" in lowered:
            score += 5
            reasons.append("ue5_keyword")
        if skeletal_mesh_asset:
            score += 3
            reasons.append("has_skeletal_mesh")
        if score > best_score:
            best_score = score
            best_asset = asset
            best_metadata = {
                "selection_mode": "auto_search",
                "requested_asset_path": preferred_asset_path,
                "resolved_asset_path": canonical_asset_path(entry["object_path"]),
                "candidate_count": len(entries),
                "score": score,
                "reasons": reasons,
                "skeletal_mesh_asset_path": skeletal_mesh_path,
                "skeleton_asset_path": skeleton_path,
            }
    return best_asset, (best_metadata or {
        "selection_mode": "auto_search",
        "requested_asset_path": preferred_asset_path,
        "resolved_asset_path": "",
        "candidate_count": len(entries),
        "score": best_score,
        "reasons": [],
    })


def animation_compatibility_payload(component, animation_asset) -> dict:
    mesh_payload = mesh_skeleton_payload(component)
    animation_payload = animation_asset_payload(animation_asset)
    compatible_paths = []
    mesh_skeleton_asset = None
    if component:
        skeletal_mesh_asset = skeletal_mesh_asset_from_component(component)
        mesh_skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(skeletal_mesh_asset)
    compatible_paths = compatible_skeleton_paths(mesh_skeleton_asset)
    mesh_skeleton_path = mesh_payload.get("skeleton_asset_path") or ""
    animation_skeleton_path = animation_payload.get("skeleton_asset_path") or ""
    exact_match = bool(mesh_skeleton_path and animation_skeleton_path and mesh_skeleton_path == animation_skeleton_path)
    listed_compatible = bool(animation_skeleton_path and animation_skeleton_path in compatible_paths)
    return {
        "mesh_asset_path": mesh_payload.get("mesh_asset_path") or "",
        "mesh_skeleton_asset_path": mesh_skeleton_path,
        "animation_asset_path": animation_payload.get("asset_path") or "",
        "animation_class_name": animation_payload.get("class_name") or "",
        "animation_skeleton_asset_path": animation_skeleton_path,
        "animation_play_length_seconds": float(animation_payload.get("play_length_seconds") or 0.0),
        "compatible_skeleton_paths": compatible_paths,
        "exact_skeleton_match": exact_match,
        "listed_compatible_skeleton": listed_compatible,
        "compatible": bool(exact_match or listed_compatible),
    }


def retarget_preflight(request: dict) -> dict:
    warnings = []
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(
        {
            **request,
            "runtime_ready_only": request.get("runtime_ready_only", True),
        }
    )
    warnings.extend(host_warnings)
    actor_subsystem = editor_actor_subsystem()
    blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
    if not blueprint_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
        }

    animation_asset_path = str(request.get("animation_asset_path") or "")
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetPreflight_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    blocking_reasons = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        compatibility = animation_compatibility_payload(primary_mesh, animation_asset)
        source_profile = skeleton_profile_payload_from_component(primary_mesh)
        target_profile = animation_skeleton_profile_payload(animation_asset)
        tooling = retarget_tooling_inventory(
            str(host_record.get("sample_id") if host_record else request.get("sample_id") or ""),
            str(host_record.get("character_package_id") if host_record else request.get("package_id") or ""),
            source_profile,
            target_profile,
        )

        if not compatibility.get("mesh_skeleton_asset_path"):
            blocking_reasons.append("source_skeleton_missing")
        if not compatibility.get("animation_skeleton_asset_path"):
            blocking_reasons.append("animation_skeleton_missing")

        requires_retarget = not compatibility.get("compatible")
        viable = bool(
            compatibility.get("compatible")
            or (
                tooling.get("can_author_new_retarget_assets")
                and source_profile.get("skeleton_asset_path")
                and target_profile.get("skeleton_asset_path")
            )
        )
        if requires_retarget and not tooling.get("can_author_new_retarget_assets"):
            blocking_reasons.append("ik_retarget_tooling_unavailable")
        if requires_retarget and (source_profile.get("humanoid_markers") or {}).get("manual_chain_mapping_likely"):
            warnings.append("source_skeleton_will_need_manual_chain_mapping")

        next_steps = retarget_recommendations(compatibility, source_profile, target_profile, tooling)
        return {
            "status": "pass" if viable and not blocking_reasons else "fail",
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "animation_compatibility": compatibility,
            "source_skeleton_profile": source_profile,
            "target_skeleton_profile": target_profile,
            "retarget_tooling": tooling,
            "retarget_readiness": {
                "direct_animation_compatible": bool(compatibility.get("compatible")),
                "requires_retarget": requires_retarget,
                "viable": viable and not blocking_reasons,
                "blocking_reasons": sorted(set(blocking_reasons)),
                "recommended_next_steps": next_steps,
            },
            "warnings": warnings,
            "errors": [] if viable and not blocking_reasons else sorted(set(blocking_reasons)),
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_bootstrap(request: dict) -> dict:
    warnings = []
    level_path = request.get("level_path") or request.get("scene_level_path")
    if level_path:
        load_result = load_level({"level_path": level_path})
        warnings.extend(load_result.get("warnings") or [])
        if load_result.get("errors"):
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": list(load_result.get("errors") or []),
            }

    host_asset_path, host_record, host_warnings = resolve_host_blueprint_asset_path(
        {
            **request,
            "runtime_ready_only": request.get("runtime_ready_only", True),
        }
    )
    warnings.extend(host_warnings)
    actor_subsystem = editor_actor_subsystem()
    blueprint_asset = unreal.EditorAssetLibrary.load_asset(object_path_from_asset_path(host_asset_path))
    if not blueprint_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"host_blueprint_load_failed:{host_asset_path}"],
        }

    animation_asset_path = str(request.get("animation_asset_path") or "")
    animation_asset = load_asset_from_any_path(animation_asset_path)
    if not animation_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"animation_asset_load_failed:{animation_asset_path or 'missing'}"],
        }

    spawn_location = vector_from_request(request.get("location"), unreal.Vector(0.0, 0.0, 120.0))
    spawn_rotation = rotator_from_request(request.get("rotation"), make_rotator(0.0, 180.0, 0.0))
    actor_label = str(request.get("actor_label") or f"AIUE_RetargetBootstrap_{sanitize_segment(host_record.get('character_package_id') if host_record else host_asset_path)}")
    spawned_host = actor_subsystem.spawn_actor_from_object(blueprint_asset, spawn_location, spawn_rotation, True)
    if not spawned_host:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"failed_to_spawn_host:{host_asset_path}"],
        }

    spawned_host.set_actor_label(actor_label)
    errors = []
    try:
        try:
            spawned_host.apply_configured_loadout()
        except Exception as exc:
            warnings.append(f"apply_configured_loadout_failed:{exc}")

        time.sleep(max(float(request.get("settle_delay_seconds") or 0.2), 0.05))
        primary_mesh = actor_primary_mesh_component(spawned_host)
        source_mesh_asset = skeletal_mesh_asset_from_component(primary_mesh)
        source_mesh_path = ""
        source_skeleton_path = ""
        if source_mesh_asset:
            try:
                source_mesh_path = source_mesh_asset.get_path_name()
            except Exception:
                source_mesh_path = ""
            source_skeleton_asset = skeleton_asset_from_skeletal_mesh_asset(source_mesh_asset)
            if source_skeleton_asset:
                try:
                    source_skeleton_path = source_skeleton_asset.get_path_name()
                except Exception:
                    source_skeleton_path = ""
        if not source_mesh_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["source_skeletal_mesh_missing"],
            }

        target_ik_rig_asset, target_selection = choose_target_ik_rig_asset(animation_asset, str(request.get("target_ik_rig_asset_path") or ""))
        if not target_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["target_ik_rig_missing"],
            }

        source_ik_rig_request_path = str(request.get("source_ik_rig_asset_path") or "")
        if not source_ik_rig_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            source_ik_rig_request_path = f"{asset_root}/Retarget/Source/IK_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}"
        source_ik_rig_asset, source_ik_rig_created = create_or_load_ik_rig_asset(source_ik_rig_request_path)
        if not source_ik_rig_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"source_ik_rig_create_failed:{source_ik_rig_request_path}"],
            }

        source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
        source_mesh_applied = False
        auto_retarget_definition_applied = False
        if source_controller:
            try:
                source_mesh_applied = bool(source_controller.set_skeletal_mesh(source_mesh_asset))
            except Exception as exc:
                warnings.append(f"source_ik_rig_set_skeletal_mesh_failed:{exc}")
            try:
                auto_retarget_definition_applied = bool(source_controller.apply_auto_generated_retarget_definition())
            except Exception as exc:
                warnings.append(f"source_ik_rig_auto_retarget_definition_failed:{exc}")
        else:
            errors.append("source_ik_rig_controller_missing")

        target_controller = unreal.IKRigController.get_controller(target_ik_rig_asset)
        target_mesh_asset = target_controller.get_skeletal_mesh() if target_controller else None
        target_mesh_path = ""
        if target_mesh_asset:
            try:
                target_mesh_path = target_mesh_asset.get_path_name()
            except Exception:
                target_mesh_path = ""

        retargeter_request_path = str(request.get("retargeter_asset_path") or "")
        if not retargeter_request_path:
            asset_root = str(request.get("asset_root") or "/Game/PMXPipeline").rstrip("/")
            target_slug = sanitize_segment(base_name_from_asset_path(target_selection.get("resolved_asset_path") or target_mesh_path or "target"))
            retargeter_request_path = f"{asset_root}/Retarget/Demo/RTG_{sanitize_segment(host_record.get('character_package_id') if host_record else 'pmx_source')}_to_{target_slug}"
        retargeter_asset, retargeter_created = create_or_load_retargeter_asset(retargeter_request_path)
        if not retargeter_asset:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": [f"retargeter_create_failed:{retargeter_request_path}"],
            }

        retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
        if not retargeter_controller:
            return {
                "status": "fail",
                "warnings": warnings,
                "errors": ["retargeter_controller_missing"],
            }

        source_enum = retarget_source_enum_value()
        target_enum = retarget_target_enum_value()
        auto_map_enum = auto_map_chain_type_value()
        if source_enum is None or target_enum is None:
            errors.append("retarget_source_or_target_enum_missing")

        source_assignment_ok = False
        target_assignment_ok = False
        if source_enum is not None and target_enum is not None:
            try:
                retargeter_controller.set_ik_rig(source_enum, source_ik_rig_asset)
                source_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_source_ik_rig_failed:{exc}")
            try:
                retargeter_controller.set_ik_rig(target_enum, target_ik_rig_asset)
                target_assignment_ok = True
            except Exception as exc:
                warnings.append(f"retargeter_set_target_ik_rig_failed:{exc}")
            if source_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(source_enum, source_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_source_preview_mesh_failed:{exc}")
            if target_mesh_asset:
                try:
                    retargeter_controller.set_preview_mesh(target_enum, target_mesh_asset)
                except Exception as exc:
                    warnings.append(f"retargeter_set_target_preview_mesh_failed:{exc}")

        try:
            retargeter_controller.add_default_ops()
        except Exception as exc:
            warnings.append(f"retargeter_add_default_ops_failed:{exc}")
        if source_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_source_ik_rig_failed:{exc}")
        if target_enum is not None:
            try:
                retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
            except Exception as exc:
                warnings.append(f"retargeter_assign_target_ik_rig_failed:{exc}")

        op_count = 0
        try:
            op_count = int(retargeter_controller.get_num_retarget_ops() or 0)
        except Exception:
            op_count = 0
        for index in range(op_count):
            try:
                retargeter_controller.run_op_initial_setup(index)
            except Exception as exc:
                warnings.append(f"retargeter_run_op_initial_setup_failed:{index}:{exc}")
        auto_map_invoked = False
        if auto_map_enum is not None:
            try:
                retargeter_controller.auto_map_chains(auto_map_enum, True)
                auto_map_invoked = True
            except Exception as exc:
                warnings.append(f"retargeter_auto_map_failed:{exc}")

        source_ik_rig_profile = ik_rig_profile_payload(source_ik_rig_asset)
        target_ik_rig_profile = ik_rig_profile_payload(target_ik_rig_asset)
        target_chain_names = [item.get("chain_name") or "" for item in target_ik_rig_profile.get("chains") or [] if item.get("chain_name")]
        mapped_chain_records = []
        mapped_chain_count = 0
        for target_chain_name in target_chain_names:
            source_chain_name = ""
            try:
                source_chain_name = str(retargeter_controller.get_source_chain(to_name(target_chain_name)) or "")
            except Exception:
                source_chain_name = ""
            if source_chain_name in {"None", "NAME_None"}:
                source_chain_name = ""
            if source_chain_name:
                mapped_chain_count += 1
            mapped_chain_records.append(
                {
                    "target_chain_name": target_chain_name,
                    "source_chain_name": source_chain_name,
                    "mapped": bool(source_chain_name),
                }
            )

        save_loaded_asset(source_ik_rig_asset)
        save_loaded_asset(retargeter_asset)
        status = "pass" if source_assignment_ok and target_assignment_ok and not errors else "fail"
        if source_ik_rig_profile.get("chain_count", 0) == 0:
            warnings.append("source_ik_rig_has_no_retarget_chains")
        if mapped_chain_count == 0:
            warnings.append("retargeter_has_no_mapped_target_chains")
        recommended_next_step_id = "retry_animation_preview_with_retargeter" if mapped_chain_count > 0 else "author_source_retarget_chains"
        recommended_next_step_reason = (
            "The retargeter has at least one mapped chain, so the next step is retrying a real animation preview through the new retarget assets."
            if mapped_chain_count > 0
            else "The bootstrap assets exist, but the imported PMX source rig still has no mapped retarget chains."
        )
        return {
            "status": status,
            "package_id": host_record.get("character_package_id") if host_record else request.get("package_id"),
            "sample_id": host_record.get("sample_id") if host_record else request.get("sample_id"),
            "host_id": spawned_host.get_path_name(),
            "host_blueprint_asset": host_asset_path,
            "level_path": level_path or get_current_level_path(),
            "animation_asset_path": animation_asset_path,
            "source_mesh_asset_path": source_mesh_path,
            "source_skeleton_asset_path": source_skeleton_path,
            "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
            "source_ik_rig_created": source_ik_rig_created,
            "source_mesh_applied_to_ik_rig": source_mesh_applied,
            "source_auto_generated_retarget_definition_applied": auto_retarget_definition_applied,
            "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()),
            "target_ik_rig_selection": target_selection,
            "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
            "retargeter_created": retargeter_created,
            "source_ik_rig_assigned": source_assignment_ok,
            "target_ik_rig_assigned": target_assignment_ok,
            "auto_map_invoked": auto_map_invoked,
            "operation_count": op_count,
            "source_ik_rig_profile": source_ik_rig_profile,
            "target_ik_rig_profile": target_ik_rig_profile,
            "mapped_chain_count": mapped_chain_count,
            "mapped_chain_records": mapped_chain_records,
            "recommended_next_step_id": recommended_next_step_id,
            "recommended_next_step_reason": recommended_next_step_reason,
            "warnings": warnings,
            "errors": errors,
        }
    finally:
        try:
            actor_subsystem.destroy_actor(spawned_host)
        except Exception:
            pass


def retarget_author_chains(request: dict) -> dict:
    warnings = []
    source_ik_rig_asset_path = str(request.get("source_ik_rig_asset_path") or "")
    retargeter_asset_path = str(request.get("retargeter_asset_path") or "")
    target_ik_rig_asset_path = str(request.get("target_ik_rig_asset_path") or "")

    source_ik_rig_asset = load_asset_from_any_path(source_ik_rig_asset_path)
    if not source_ik_rig_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"source_ik_rig_load_failed:{source_ik_rig_asset_path or 'missing'}"],
        }
    retargeter_asset = load_asset_from_any_path(retargeter_asset_path)
    if not retargeter_asset:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": [f"retargeter_load_failed:{retargeter_asset_path or 'missing'}"],
        }
    target_ik_rig_asset = load_asset_from_any_path(target_ik_rig_asset_path) if target_ik_rig_asset_path else None

    source_controller = unreal.IKRigController.get_controller(source_ik_rig_asset)
    retargeter_controller = unreal.IKRetargeterController.get_controller(retargeter_asset)
    if not source_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_ik_rig_controller_missing"],
        }
    if not retargeter_controller:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["retargeter_controller_missing"],
        }

    bone_names, bone_name_source = bone_names_from_ik_rig_controller(source_controller)
    if not bone_names:
        return {
            "status": "fail",
            "warnings": warnings,
            "errors": ["source_bone_names_unresolved"],
        }

    existing_chains = ik_rig_chain_records(source_controller)
    clear_existing = bool(request.get("clear_existing_chains", True))
    removed_chain_names = []
    if clear_existing:
        for chain_record in existing_chains:
            chain_name = str(chain_record.get("chain_name") or "")
            if not chain_name:
                continue
            try:
                if source_controller.remove_retarget_chain(to_name(chain_name)):
                    removed_chain_names.append(chain_name)
            except Exception as exc:
                warnings.append(f"remove_source_chain_failed:{chain_name}:{exc}")

    planned_chains, planning_warnings, planning_diagnostics = planned_source_chain_records(bone_names)
    warnings.extend(planning_warnings)

    authored_chain_records = []
    for chain in planned_chains:
        chain_name = chain["chain_name"]
        start_bone = chain["start_bone"]
        end_bone = chain["end_bone"]
        goal_name = chain.get("goal_name") or ""
        try:
            created_name = source_controller.add_retarget_chain(
                to_name(chain_name),
                to_name(start_bone),
                to_name(end_bone),
                to_name(goal_name) if goal_name else unreal.Name("None"),
            )
            authored_chain_records.append(
                {
                    "requested_chain_name": chain_name,
                    "created_chain_name": str(created_name or chain_name),
                    "start_bone": start_bone,
                    "end_bone": end_bone,
                    "goal_name": goal_name,
                    "planning_reason": chain.get("planning_reason") or "",
                }
            )
        except Exception as exc:
            warnings.append(f"add_source_chain_failed:{chain_name}:{exc}")

    pelvis_bone = pick_best_bone_name(bone_names, [["pelvis"], ["hips"], ["\u4e0b\u534a\u8eab"], ["\u8170"], ["center"]])
    if not pelvis_bone:
        spine_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "Spine"), None)
        root_chain = next((item for item in planned_chains if str(item.get("chain_name") or "") == "root"), None)
        pelvis_bone = str((spine_chain or {}).get("start_bone") or (root_chain or {}).get("end_bone") or "")
    retarget_root_set = False
    if pelvis_bone:
        try:
            retarget_root_set = bool(source_controller.set_retarget_root(to_name(pelvis_bone)))
        except Exception as exc:
            warnings.append(f"set_source_retarget_root_failed:{pelvis_bone}:{exc}")
    else:
        warnings.append("source_retarget_root_unresolved")

    source_enum = retarget_source_enum_value()
    target_enum = retarget_target_enum_value()
    auto_map_enum = auto_map_chain_type_value()
    if source_enum is not None:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            retargeter_controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"retargeter_reassign_target_ik_rig_failed:{exc}")
    auto_map_invoked = False
    if auto_map_enum is not None:
        try:
            retargeter_controller.auto_map_chains(auto_map_enum, True)
            auto_map_invoked = True
        except Exception as exc:
            warnings.append(f"retargeter_auto_map_failed:{exc}")

    source_profile = ik_rig_profile_payload(source_ik_rig_asset)
    target_profile = ik_rig_profile_payload(target_ik_rig_asset) if target_ik_rig_asset else {
        "asset_path": canonical_asset_path(target_ik_rig_asset_path),
        "skeletal_mesh_asset_path": "",
        "skeleton_asset_path": "",
        "retarget_root": "",
        "chain_count": 0,
        "chains": [],
    }
    target_chain_names = [item.get("chain_name") or "" for item in target_profile.get("chains") or [] if item.get("chain_name")]
    mapped_chain_records = []
    mapped_chain_count = 0
    exact_named_mapped_chain_count = 0
    exact_named_mapped_chain_names = []
    for target_chain_name in target_chain_names:
        source_chain_name = ""
        try:
            source_chain_name = str(retargeter_controller.get_source_chain(to_name(target_chain_name)) or "")
        except Exception:
            source_chain_name = ""
        if source_chain_name in {"None", "NAME_None"}:
            source_chain_name = ""
        if source_chain_name:
            mapped_chain_count += 1
        exact_named_match = bool(source_chain_name and source_chain_name == target_chain_name)
        if exact_named_match:
            exact_named_mapped_chain_count += 1
            exact_named_mapped_chain_names.append(target_chain_name)
        mapped_chain_records.append(
            {
                "target_chain_name": target_chain_name,
                "source_chain_name": source_chain_name,
                "mapped": bool(source_chain_name),
                "exact_named_match": exact_named_match,
            }
        )

    save_loaded_asset(source_ik_rig_asset)
    save_loaded_asset(retargeter_asset)
    errors = []
    if source_profile.get("chain_count", 0) == 0:
        errors.append("source_chain_authoring_failed")
    if mapped_chain_count == 0:
        warnings.append("retargeter_still_has_no_mapped_target_chains")
    meaningful_required_chain_names = ["root", "Spine", "LeftClavicle", "RightClavicle", "LeftArm", "RightArm"]
    authored_chain_name_set = {str(item.get("created_chain_name") or item.get("requested_chain_name") or "") for item in authored_chain_records}
    missing_meaningful_source_chain_names = [name for name in meaningful_required_chain_names if name not in authored_chain_name_set]
    missing_meaningful_mapped_chain_names = [name for name in meaningful_required_chain_names if name not in exact_named_mapped_chain_names]
    if missing_meaningful_source_chain_names:
        warnings.append(f"meaningful_source_chains_missing:{','.join(missing_meaningful_source_chain_names)}")
    if exact_named_mapped_chain_count == 0:
        warnings.append("retargeter_has_no_exact_named_chain_mappings")
    if exact_named_mapped_chain_count < 4:
        warnings.append("retargeter_exact_named_chain_mapping_insufficient_for_upper_body_preview")

    ready_for_animation_retry = bool(exact_named_mapped_chain_count >= 4 and not missing_meaningful_mapped_chain_names[:4])
    recommended_next_step_id = "retry_animation_preview_with_retargeter" if ready_for_animation_retry else "refine_source_chain_mapping"
    recommended_next_step_reason = (
        "The PMX source rig now has enough exact-named upper-body chain mappings to justify retrying animation preview through the retargeter."
        if ready_for_animation_retry
        else "The PMX source rig is no longer blank, but its exact-named upper-body chain mappings are still incomplete."
    )

    return {
        "status": "pass" if not errors else "fail",
        "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
        "retargeter_asset_path": canonical_asset_path(retargeter_asset.get_path_name()),
        "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()) if target_ik_rig_asset else canonical_asset_path(target_ik_rig_asset_path),
        "source_bone_name_source": bone_name_source,
        "source_bone_count": len(bone_names),
        "source_bone_name_sample": bone_names[:40],
        "removed_chain_names": removed_chain_names,
        "planned_chains": planned_chains,
        "planning_diagnostics": planning_diagnostics,
        "authored_chain_records": authored_chain_records,
        "retarget_root_bone": pelvis_bone,
        "retarget_root_set": retarget_root_set,
        "auto_map_invoked": auto_map_invoked,
        "source_ik_rig_profile": source_profile,
        "target_ik_rig_profile": target_profile,
        "mapped_chain_count": mapped_chain_count,
        "exact_named_mapped_chain_count": exact_named_mapped_chain_count,
        "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
        "meaningful_required_chain_names": meaningful_required_chain_names,
        "missing_meaningful_source_chain_names": missing_meaningful_source_chain_names,
        "missing_meaningful_mapped_chain_names": missing_meaningful_mapped_chain_names,
        "mapped_chain_records": mapped_chain_records,
        "ready_for_animation_retry": ready_for_animation_retry,
        "recommended_next_step_id": recommended_next_step_id,
        "recommended_next_step_reason": recommended_next_step_reason,
        "warnings": warnings,
        "errors": errors,
    }


def asset_data_from_asset_path(asset_path: str):
    normalized = canonical_asset_path(asset_path)
    if not normalized:
        return None
    object_path = object_path_from_asset_path(normalized)
    if hasattr(unreal.EditorAssetLibrary, "find_asset_data"):
        try:
            asset_data = unreal.EditorAssetLibrary.find_asset_data(object_path)
        except Exception:
            asset_data = None
        if asset_data and asset_object_path(asset_data):
            return asset_data
    loaded_asset = load_asset_from_any_path(normalized)
    if loaded_asset and hasattr(unreal.AssetRegistryHelpers, "create_asset_data"):
        try:
            asset_data = unreal.AssetRegistryHelpers.create_asset_data(loaded_asset)
        except Exception:
            asset_data = None
        if asset_data and asset_object_path(asset_data):
            return asset_data
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    try:
        asset_data = registry.get_asset_by_object_path(object_path)
    except Exception:
        asset_data = None
    if asset_data and asset_object_path(asset_data):
        return asset_data
    package_path, asset_name = package_path_and_asset_name(normalized)
    if package_path:
        try:
            candidates = list(registry.get_assets_by_path(to_name(package_path), recursive=False) or [])
        except Exception:
            candidates = []
        for candidate in candidates:
            if str(candidate.asset_name) == asset_name or asset_object_path(candidate) == object_path:
                return candidate
    return None


def skeletal_mesh_from_ik_rig_asset(ik_rig_asset):
    if not ik_rig_asset:
        return None
    controller = unreal.IKRigController.get_controller(ik_rig_asset)
    if not controller:
        return None
    try:
        mesh = controller.get_skeletal_mesh()
    except Exception:
        mesh = None
    return mesh


def reverse_preview_retargeter_asset_path(source_ik_rig_asset_path: str, target_ik_rig_asset_path: str, package_id: str | None = None) -> str:
    source_slug = sanitize_segment(base_name_from_asset_path(source_ik_rig_asset_path) or "source")
    target_slug = sanitize_segment(package_id or base_name_from_asset_path(target_ik_rig_asset_path) or "target")
    return f"/Game/PMXPipeline/Retarget/Demo/RTG_{source_slug}_to_{target_slug}_Preview"


def exact_chain_names_for_ik_rig(ik_rig_asset) -> list[str]:
    profile = ik_rig_profile_payload(ik_rig_asset)
    return sorted({str(item.get("chain_name") or "") for item in (profile.get("chains") or []) if str(item.get("chain_name") or "")})


def configure_retargeter_for_preview_export(retargeter_asset, source_ik_rig_asset, target_ik_rig_asset, source_mesh_asset, target_mesh_asset) -> dict:
    warnings = []
    controller = unreal.IKRetargeterController.get_controller(retargeter_asset) if retargeter_asset else None
    if not controller:
        return {
            "success": False,
            "warnings": ["preview_retargeter_controller_missing"],
            "errors": ["preview_retargeter_controller_missing"],
            "exact_chain_names": [],
            "mapped_chain_records": [],
        }

    source_enum = retarget_source_enum_value()
    target_enum = retarget_target_enum_value()
    auto_map_enum = auto_map_chain_type_value()
    if source_enum is not None and source_ik_rig_asset:
        try:
            controller.set_ik_rig(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            controller.set_ik_rig(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_target_ik_rig_failed:{exc}")
    if source_enum is not None and source_mesh_asset:
        try:
            controller.set_preview_mesh(source_enum, source_mesh_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_source_preview_mesh_failed:{exc}")
    if target_enum is not None and target_mesh_asset:
        try:
            controller.set_preview_mesh(target_enum, target_mesh_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_set_target_preview_mesh_failed:{exc}")

    try:
        controller.remove_all_ops()
    except Exception as exc:
        warnings.append(f"preview_retargeter_remove_all_ops_failed:{exc}")
    try:
        controller.add_default_ops()
    except Exception as exc:
        warnings.append(f"preview_retargeter_add_default_ops_failed:{exc}")

    op_count = 0
    try:
        op_count = int(controller.get_num_retarget_ops() or 0)
    except Exception:
        op_count = 0
    for index in range(op_count):
        try:
            controller.run_op_initial_setup(index)
        except Exception as exc:
            warnings.append(f"preview_retargeter_run_op_initial_setup_failed:{index}:{exc}")
    if source_enum is not None and source_ik_rig_asset:
        try:
            controller.assign_ik_rig_to_all_ops(source_enum, source_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_assign_source_ik_rig_failed:{exc}")
    if target_enum is not None and target_ik_rig_asset:
        try:
            controller.assign_ik_rig_to_all_ops(target_enum, target_ik_rig_asset)
        except Exception as exc:
            warnings.append(f"preview_retargeter_assign_target_ik_rig_failed:{exc}")
    if auto_map_enum is not None:
        try:
            controller.auto_map_chains(auto_map_enum, True)
        except Exception as exc:
            warnings.append(f"preview_retargeter_auto_map_failed:{exc}")

    source_chain_names = set(exact_chain_names_for_ik_rig(source_ik_rig_asset))
    target_chain_names = set(exact_chain_names_for_ik_rig(target_ik_rig_asset))
    exact_chain_names = sorted(source_chain_names.intersection(target_chain_names))
    exact_mapping_errors = []
    for chain_name in exact_chain_names:
        try:
            if not controller.set_source_chain(to_name(chain_name), to_name(chain_name)):
                exact_mapping_errors.append(chain_name)
        except Exception:
            exact_mapping_errors.append(chain_name)
    if exact_mapping_errors:
        warnings.append(f"preview_retargeter_set_exact_source_chain_failed:{','.join(sorted(exact_mapping_errors))}")

    mapped_chain_records = []
    for chain_name in sorted(target_chain_names):
        source_chain_name = ""
        try:
            source_chain_name = str(controller.get_source_chain(to_name(chain_name)) or "")
        except Exception:
            source_chain_name = ""
        if source_chain_name in {"None", "NAME_None"}:
            source_chain_name = ""
        mapped_chain_records.append(
            {
                "target_chain_name": chain_name,
                "source_chain_name": source_chain_name,
                "exact_named_match": bool(source_chain_name and source_chain_name == chain_name),
            }
        )

    save_loaded_asset(retargeter_asset)
    exact_named_mapped_chain_names = sorted(
        [item["target_chain_name"] for item in mapped_chain_records if item.get("exact_named_match")]
    )
    return {
        "success": True,
        "warnings": warnings,
        "errors": [],
        "op_count": op_count,
        "exact_chain_names": exact_chain_names,
        "mapped_chain_records": mapped_chain_records,
        "exact_named_mapped_chain_names": exact_named_mapped_chain_names,
    }


def resolve_retargeted_animation_asset(results) -> tuple[object | None, str]:
    asset_data_list = list(results or [])
    if not asset_data_list:
        return None, ""
    chosen_asset_path = ""
    chosen_asset = None
    for asset_data in asset_data_list:
        class_name = asset_class_name(asset_data)
        object_path = asset_object_path(asset_data)
        canonical_path = canonical_asset_path(object_path)
        if class_name == "AnimSequence":
            chosen_asset_path = canonical_path
            chosen_asset = load_asset_from_any_path(canonical_path)
            if chosen_asset:
                return chosen_asset, chosen_asset_path
    first_object_path = asset_object_path(asset_data_list[0])
    chosen_asset_path = canonical_asset_path(first_object_path)
    return load_asset_from_any_path(chosen_asset_path), chosen_asset_path


def generate_retargeted_animation_for_preview(primary_mesh, animation_asset, request: dict) -> dict:
    warnings = []
    errors = []
    if not primary_mesh or not animation_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": ["preview_mesh_or_animation_missing"],
        }

    source_ik_rig_asset_path = str(request.get("retarget_source_ik_rig_asset_path") or "")
    target_ik_rig_asset_path = str(request.get("retarget_target_ik_rig_asset_path") or "")
    source_ik_rig_asset = load_asset_from_any_path(source_ik_rig_asset_path)
    target_ik_rig_asset = load_asset_from_any_path(target_ik_rig_asset_path)
    if not source_ik_rig_asset or not target_ik_rig_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [
                f"retarget_preview_ik_rig_missing:source={bool(source_ik_rig_asset)}:target={bool(target_ik_rig_asset)}"
            ],
        }

    source_mesh_asset = load_asset_from_any_path(str(request.get("retarget_source_mesh_asset_path") or "")) or skeletal_mesh_from_ik_rig_asset(source_ik_rig_asset)
    target_mesh_asset = load_asset_from_any_path(str(request.get("retarget_target_mesh_asset_path") or "")) or skeletal_mesh_asset_from_component(primary_mesh)
    if not source_mesh_asset or not target_mesh_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [
                f"retarget_preview_mesh_missing:source={bool(source_mesh_asset)}:target={bool(target_mesh_asset)}"
            ],
        }

    preview_retargeter_asset_path = str(
        request.get("retargeter_asset_path")
        or reverse_preview_retargeter_asset_path(source_ik_rig_asset_path, target_ik_rig_asset_path, request.get("package_id"))
    )
    preview_retargeter_asset, preview_retargeter_created = create_or_load_retargeter_asset(preview_retargeter_asset_path)
    if not preview_retargeter_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": [f"preview_retargeter_create_failed:{preview_retargeter_asset_path}"],
        }

    configuration = configure_retargeter_for_preview_export(
        preview_retargeter_asset,
        source_ik_rig_asset,
        target_ik_rig_asset,
        source_mesh_asset,
        target_mesh_asset,
    )
    warnings.extend(configuration.get("warnings") or [])
    errors.extend(configuration.get("errors") or [])

    asset_data = asset_data_from_asset_path(animation_asset.get_path_name())
    if not asset_data:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + [f"animation_asset_data_unresolved:{animation_asset.get_path_name()}"],
        }

    batch_class = getattr(unreal, "IKRetargetBatchOperation", None)
    batch_function = None
    for attribute_name in ("duplicate_and_retarget", "DuplicateAndRetarget"):
        if batch_class and hasattr(batch_class, attribute_name):
            batch_function = getattr(batch_class, attribute_name)
            break
    if not batch_function:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + ["ik_retarget_batch_operation_unavailable"],
        }

    suffix = str(request.get("retarget_output_suffix") or "_PMXPreview")
    prefix = str(request.get("retarget_output_prefix") or "RTG_")
    try:
        retargeted_assets = batch_function(
            [asset_data],
            source_mesh_asset,
            target_mesh_asset,
            preview_retargeter_asset,
            "",
            "",
            prefix,
            suffix,
            False,
            True,
        )
    except Exception as exc:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + [f"duplicate_and_retarget_failed:{exc}"],
        }

    retargeted_animation_asset, retargeted_animation_asset_path = resolve_retargeted_animation_asset(retargeted_assets)
    if not retargeted_animation_asset:
        return {
            "success": False,
            "warnings": warnings,
            "errors": errors + ["retargeted_animation_asset_unresolved"],
            "retargeter_asset_path": canonical_asset_path(preview_retargeter_asset.get_path_name()),
        }
    retargeted_compatibility = animation_compatibility_payload(primary_mesh, retargeted_animation_asset)
    save_loaded_asset(retargeted_animation_asset)
    return {
        "success": bool(retargeted_compatibility.get("compatible")),
        "warnings": warnings,
        "errors": errors if retargeted_compatibility.get("compatible") else errors + ["retargeted_animation_still_incompatible"],
        "retargeter_asset_path": canonical_asset_path(preview_retargeter_asset.get_path_name()),
        "retargeter_created": preview_retargeter_created,
        "source_ik_rig_asset_path": canonical_asset_path(source_ik_rig_asset.get_path_name()),
        "target_ik_rig_asset_path": canonical_asset_path(target_ik_rig_asset.get_path_name()),
        "source_mesh_asset_path": canonical_asset_path(source_mesh_asset.get_path_name()),
        "target_mesh_asset_path": canonical_asset_path(target_mesh_asset.get_path_name()),
        "source_animation_asset_path": canonical_asset_path(animation_asset.get_path_name()),
        "retargeted_animation_asset_path": canonical_asset_path(retargeted_animation_asset_path or retargeted_animation_asset.get_path_name()),
        "retargeted_animation_class_name": retargeted_animation_asset.get_class().get_name() if retargeted_animation_asset else "",
        "retargeted_compatibility": retargeted_compatibility,
        "exact_named_mapped_chain_names": list(configuration.get("exact_named_mapped_chain_names") or []),
        "mapped_chain_records": list(configuration.get("mapped_chain_records") or []),
    }


def interesting_member_names(obj, interesting_names: list[str]) -> list[str]:
    if not obj:
        return []
    try:
        available = set(dir(obj))
    except Exception:
        return []
    return sorted([name for name in interesting_names if name in available])


def call_method_variants(target, label: str, candidate_names: list[str], arg_variants: list[tuple], call_trace: list[dict], warnings: list[str], applied_methods: list[str]):
    for method_name in candidate_names:
        if not hasattr(target, method_name):
            continue
        method = getattr(target, method_name)
        for args in arg_variants:
            trace_record = {
                "label": label,
                "method_name": method_name,
                "args": [repr(arg) for arg in args],
                "success": False,
            }
            try:
                result = method(*args)
                trace_record["success"] = True
                if result is not None:
                    trace_record["result_repr"] = repr(result)
                call_trace.append(trace_record)
                applied_methods.append(f"{label}:{method_name}")
                return True, result
            except Exception as exc:
                trace_record["error"] = str(exc)
                call_trace.append(trace_record)
        warnings.append(f"{label}_failed:{method_name}")
    return False, None


def set_editor_property_variants(target, label: str, property_updates: list[tuple[str, object]], call_trace: list[dict], warnings: list[str], applied_methods: list[str]) -> bool:
    if not target or not hasattr(target, "set_editor_property"):
        return False
    any_success = False
    for property_name, property_value in property_updates:
        trace_record = {
            "label": label,
            "property_name": property_name,
            "value_repr": repr(property_value),
            "success": False,
        }
        try:
            target.set_editor_property(property_name, property_value)
            trace_record["success"] = True
            call_trace.append(trace_record)
            applied_methods.append(f"{label}:{property_name}")
            any_success = True
        except Exception as exc:
            trace_record["error"] = str(exc)
            call_trace.append(trace_record)
    if not any_success:
        warnings.append(f"{label}_property_update_failed")
    return any_success


def bone_space_world_value():
    bone_spaces = getattr(unreal, "BoneSpaces", None)
    if bone_spaces:
        for candidate in ("WORLD_SPACE", "WorldSpace"):
            if hasattr(bone_spaces, candidate):
                return getattr(bone_spaces, candidate)
    return None


def probe_component_pose(component, probe_bone_names: list[str] | None = None) -> dict:
    requested_bone_names = [str(name) for name in list(probe_bone_names or []) if str(name)]
    pose = {
        "component_world_location": {},
        "component_world_rotation": {},
        "component_asset_path": component_asset_path(component),
        "sampled_bones": {},
        "requested_bone_names": requested_bone_names,
        "available_probe_methods": [],
    }
    if not component:
        pose["warnings"] = ["component_missing"]
        return pose

    try:
        pose["component_world_location"] = serialize_vector(component.get_component_location())
    except Exception:
        pose["component_world_location"] = {}
    try:
        pose["component_world_rotation"] = serialize_rotator(component.get_component_rotation())
    except Exception:
        pose["component_world_rotation"] = {}

    available_methods = interesting_member_names(
        component,
        [
            "get_bone_location",
            "GetBoneLocation",
            "get_socket_location",
            "GetSocketLocation",
            "get_socket_transform",
            "GetSocketTransform",
            "does_socket_exist",
            "DoesSocketExist",
        ],
    )
    pose["available_probe_methods"] = available_methods
    if not requested_bone_names:
        return pose

    world_space = bone_space_world_value()
    sampled = {}
    for bone_name in requested_bone_names:
        location = None
        source = ""
        if hasattr(component, "get_socket_location"):
            try:
                location = component.get_socket_location(to_name(bone_name))
                source = "get_socket_location"
            except Exception:
                location = None
        if location is None and hasattr(component, "GetSocketLocation"):
            try:
                location = component.GetSocketLocation(to_name(bone_name))
                source = "GetSocketLocation"
            except Exception:
                location = None
        if location is None and hasattr(component, "get_bone_location") and world_space is not None:
            try:
                location = component.get_bone_location(to_name(bone_name), world_space)
                source = "get_bone_location"
            except Exception:
                location = None
        if location is None and hasattr(component, "GetBoneLocation") and world_space is not None:
            try:
                location = component.GetBoneLocation(to_name(bone_name), world_space)
                source = "GetBoneLocation"
            except Exception:
                location = None
        if location is not None:
            sampled[bone_name] = {
                "location": serialize_vector(location),
                "source": source,
            }
    pose["sampled_bones"] = sampled
    return pose


def pose_delta_payload(before_pose: dict, after_pose: dict) -> dict:
    before_bones = dict((before_pose or {}).get("sampled_bones") or {})
    after_bones = dict((after_pose or {}).get("sampled_bones") or {})
    delta_by_bone = {}
    moving_bone_count = 0
    max_location_delta = 0.0
    for bone_name in sorted(set(before_bones.keys()).intersection(after_bones.keys())):
        before_location = vector_from_request(before_bones[bone_name].get("location"))
        after_location = vector_from_request(after_bones[bone_name].get("location"))
        delta_vector = after_location - before_location
        location_delta = math.sqrt((delta_vector.x * delta_vector.x) + (delta_vector.y * delta_vector.y) + (delta_vector.z * delta_vector.z))
        moving = location_delta >= 0.5
        moving_bone_count += int(moving)
        max_location_delta = max(max_location_delta, float(location_delta))
        delta_by_bone[bone_name] = {
            "location_delta": float(location_delta),
            "moving": moving,
            "before_location": serialize_vector(before_location),
            "after_location": serialize_vector(after_location),
        }
    return {
        "moving_bone_count": moving_bone_count,
        "max_location_delta": float(max_location_delta),
        "delta_by_bone": delta_by_bone,
    }


def serialize_quat(quat) -> dict:
    if quat is None:
        return {}
    payload = {}
    for attribute_name in ("x", "y", "z", "w"):
        try:
            payload[attribute_name] = float(getattr(quat, attribute_name))
        except Exception:
            continue
    return payload


def transform_translation_value(transform):
    if transform is None:
        return None
    for method_name in ("get_translation",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("translation", "location"):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def transform_rotation_value(transform):
    if transform is None:
        return None
    for method_name in ("get_rotation",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("rotation",):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def transform_scale_value(transform):
    if transform is None:
        return None
    for method_name in ("get_scale3d",):
        if hasattr(transform, method_name):
            try:
                return getattr(transform, method_name)()
            except Exception:
                continue
    for attribute_name in ("scale3d", "scale"):
        try:
            value = getattr(transform, attribute_name)
            if value is not None:
                return value
        except Exception:
            continue
    return None


def serialize_transform_payload(transform) -> dict:
    translation = transform_translation_value(transform)
    rotation = transform_rotation_value(transform)
    scale = transform_scale_value(transform)
    rotator = None
    if rotation is not None and hasattr(rotation, "rotator"):
        try:
            rotator = rotation.rotator()
        except Exception:
            rotator = None
    return {
        "translation": serialize_vector(translation) if translation is not None else {},
        "rotation_quat": serialize_quat(rotation) if rotation is not None else {},
        "rotation_rotator": serialize_rotator(rotator) if rotator is not None else {},
        "scale": serialize_vector(scale) if scale is not None else {},
        "repr": repr(transform),
    }


def reference_skeleton_pose_records(reference_skeleton) -> dict[str, dict]:
    names, _ = reference_skeleton_bone_names(reference_skeleton)
    if not names:
        return {}
    pose_values = None
    for method_name in ("get_raw_ref_bone_pose", "get_ref_bone_pose"):
        if hasattr(reference_skeleton, method_name):
            try:
                pose_values = list(getattr(reference_skeleton, method_name)() or [])
            except Exception:
                pose_values = None
            if pose_values:
                break
    records = {}
    for index, bone_name in enumerate(names):
        local_transform = pose_values[index] if pose_values and index < len(pose_values) else None
        parent_index = -1
        for method_name in ("get_parent_index",):
            if hasattr(reference_skeleton, method_name):
                try:
                    parent_index = int(getattr(reference_skeleton, method_name)(index))
                    break
                except Exception:
                    parent_index = -1
        records[bone_name] = {
            "index": index,
            "parent_index": parent_index,
            "local_transform": local_transform,
            "local_transform_payload": serialize_transform_payload(local_transform) if local_transform is not None else {},
        }
    return records


def sample_animation_local_pose(animation_asset, bone_names: list[str], sample_time_seconds: float, preview_mesh_asset=None) -> dict:
    payload = {
        "success": False,
        "warnings": [],
        "errors": [],
        "sample_time_seconds": float(sample_time_seconds),
        "bone_count": len(bone_names),
        "bone_poses": {},
        "api_trace": [],
    }
    animation_library = getattr(unreal, "AnimationBlueprintLibrary", None)
    if not animation_library:
        for loader_name in ("load_module", "load_editor_module"):
            if hasattr(unreal, loader_name):
                try:
                    getattr(unreal, loader_name)("AnimationBlueprintLibrary")
                    payload["api_trace"].append(f"{loader_name}:AnimationBlueprintLibrary")
                except Exception as exc:
                    payload["api_trace"].append(f"{loader_name}:AnimationBlueprintLibrary_failed:{exc}")
        modules_class = getattr(unreal, "Modules", None)
        if modules_class and hasattr(modules_class, "load_module"):
            try:
                modules_class.load_module("AnimationBlueprintLibrary")
                payload["api_trace"].append("Modules.load_module:AnimationBlueprintLibrary")
            except Exception as exc:
                payload["api_trace"].append(f"Modules.load_module:AnimationBlueprintLibrary_failed:{exc}")
        animation_library = getattr(unreal, "AnimationBlueprintLibrary", None)
    if not animation_library:
        payload["errors"].append("animation_blueprint_library_unavailable")
        return payload
    if not animation_asset:
        payload["errors"].append("animation_asset_missing")
        return payload
    if not bone_names:
        payload["errors"].append("animation_pose_bone_list_empty")
        return payload

    result = None
    bone_name_values = [to_name(name) for name in bone_names]
    try:
        result = animation_library.get_bone_poses_for_time(animation_asset, bone_name_values, float(sample_time_seconds), False, preview_mesh_asset)
        payload["api_trace"].append("get_bone_poses_for_time:with_preview_mesh")
    except Exception as exc:
        payload["api_trace"].append(f"get_bone_poses_for_time:with_preview_mesh_failed:{exc}")
    if result is None:
        try:
            result = animation_library.get_bone_poses_for_time(animation_asset, bone_name_values, float(sample_time_seconds), False)
            payload["api_trace"].append("get_bone_poses_for_time:no_preview_mesh")
        except Exception as exc:
            payload["api_trace"].append(f"get_bone_poses_for_time:no_preview_mesh_failed:{exc}")

    transforms = []
    if isinstance(result, (list, tuple)):
        transforms = list(result)
    elif result is not None:
        transforms = [result]

    if not transforms or len(transforms) != len(bone_names):
        transforms = []
        for bone_name in bone_names:
            transform = None
            try:
                transform = animation_library.get_bone_pose_for_time(animation_asset, to_name(bone_name), float(sample_time_seconds), False)
                payload["api_trace"].append(f"get_bone_pose_for_time:{bone_name}")
            except Exception as exc:
                payload["api_trace"].append(f"get_bone_pose_for_time_failed:{bone_name}:{exc}")
            transforms.append(transform)

    if not transforms:
        payload["errors"].append("animation_pose_sampling_failed")
        return payload

    for bone_name, transform in zip(bone_names, transforms):
        if transform is None:
            continue
        payload["bone_poses"][bone_name] = {
            "transform": serialize_transform_payload(transform),
        }
    payload["success"] = bool(payload["bone_poses"])
    if not payload["success"]:
        payload["errors"].append("animation_pose_sampling_empty")
    return payload


def animation_pose_delta_against_reference(sampled_pose: dict, reference_pose_records: dict[str, dict]) -> dict:
    delta_by_bone = {}
    changed_bone_count = 0
    rotation_changed_bone_count = 0
    translation_changed_bone_count = 0
    for bone_name, sampled_record in dict(sampled_pose.get("bone_poses") or {}).items():
        sampled_transform = dict(sampled_record.get("transform") or {})
        reference_transform = dict((reference_pose_records.get(bone_name) or {}).get("local_transform_payload") or {})
        sampled_translation = vector_from_request(sampled_transform.get("translation"))
        reference_translation = vector_from_request(reference_transform.get("translation"))
        delta_vector = sampled_translation - reference_translation
        translation_delta = math.sqrt((delta_vector.x * delta_vector.x) + (delta_vector.y * delta_vector.y) + (delta_vector.z * delta_vector.z))
        sampled_rotator = dict(sampled_transform.get("rotation_rotator") or {})
        reference_rotator = dict(reference_transform.get("rotation_rotator") or {})
        rotation_delta = max(
            abs(float(sampled_rotator.get("pitch", 0.0)) - float(reference_rotator.get("pitch", 0.0))),
            abs(float(sampled_rotator.get("yaw", 0.0)) - float(reference_rotator.get("yaw", 0.0))),
            abs(float(sampled_rotator.get("roll", 0.0)) - float(reference_rotator.get("roll", 0.0))),
        )
        repr_changed = str(sampled_transform.get("repr") or "") != str(reference_transform.get("repr") or "")
        translation_changed = translation_delta >= 0.25
        rotation_changed = rotation_delta >= 1.0
        changed = bool(translation_changed or rotation_changed or repr_changed)
        changed_bone_count += int(changed)
        translation_changed_bone_count += int(translation_changed)
        rotation_changed_bone_count += int(rotation_changed)
        delta_by_bone[bone_name] = {
            "translation_delta": float(translation_delta),
            "rotation_delta_max_degrees": float(rotation_delta),
            "translation_changed": translation_changed,
            "rotation_changed": rotation_changed,
            "repr_changed": repr_changed,
            "changed": changed,
            "sampled_transform": sampled_transform,
            "reference_transform": reference_transform,
        }
    return {
        "changed_bone_count": changed_bone_count,
        "translation_changed_bone_count": translation_changed_bone_count,
        "rotation_changed_bone_count": rotation_changed_bone_count,
        "delta_by_bone": delta_by_bone,
    }


def struct_property_value(struct_value, property_name: str, default=None):
    if struct_value is None:
        return default
    try:
        return struct_value.get_editor_property(property_name)
    except Exception:
        pass
    try:
        value = getattr(struct_value, property_name)
        if callable(value):
            return value()
        return value
    except Exception:
        return default


def serialize_native_animation_pose_probe_result(probe_result) -> dict:
    return {
        "bone_name": str(struct_property_value(probe_result, "bone_name", "") or ""),
        "found": bool(struct_property_value(probe_result, "found", False)),
        "changed": bool(struct_property_value(probe_result, "changed", False)),
        "location_delta": float(struct_property_value(probe_result, "location_delta", 0.0) or 0.0),
        "rotation_angle_delta_degrees": float(struct_property_value(probe_result, "rotation_angle_delta_degrees", 0.0) or 0.0),
        "scale_delta": float(struct_property_value(probe_result, "scale_delta", 0.0) or 0.0),
    }


def serialize_native_animation_pose_evaluation(result) -> dict:
    probe_results = [serialize_native_animation_pose_probe_result(item) for item in list(struct_property_value(result, "probe_results", []) or [])]
    return {
        "available": True,
        "success": bool(struct_property_value(result, "success", False)),
        "pose_changed": bool(struct_property_value(result, "pose_changed", False)),
        "sample_time_seconds": float(struct_property_value(result, "sample_time_seconds", 0.0) or 0.0),
        "bone_count": int(struct_property_value(result, "bone_count", 0) or 0),
        "changed_bone_count": int(struct_property_value(result, "changed_bone_count", 0) or 0),
        "max_location_delta": float(struct_property_value(result, "max_location_delta", 0.0) or 0.0),
        "max_rotation_angle_delta_degrees": float(struct_property_value(result, "max_rotation_angle_delta_degrees", 0.0) or 0.0),
        "max_scale_delta": float(struct_property_value(result, "max_scale_delta", 0.0) or 0.0),
        "applied_methods": [str(item) for item in list(struct_property_value(result, "applied_methods", []) or [])],
        "warnings": [str(item) for item in list(struct_property_value(result, "warnings", []) or [])],
        "errors": [str(item) for item in list(struct_property_value(result, "errors", []) or [])],
        "probe_results": probe_results,
    }


def evaluate_animation_pose_on_component_native(component, animation_asset, sample_time_seconds: float, probe_bone_names: list[str]) -> dict:
    if not hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
        return {
            "available": False,
            "success": False,
            "pose_changed": False,
            "errors": ["pmx_runtime_blueprint_library_unavailable"],
            "warnings": [],
            "applied_methods": [],
            "probe_results": [],
            "sample_time_seconds": float(sample_time_seconds),
            "bone_count": 0,
            "changed_bone_count": 0,
            "max_location_delta": 0.0,
            "max_rotation_angle_delta_degrees": 0.0,
            "max_scale_delta": 0.0,
        }
    try:
        result = unreal.PMXEquipmentBlueprintLibrary.evaluate_animation_pose_on_component(
            component,
            animation_asset,
            float(sample_time_seconds),
            [to_name(name) for name in probe_bone_names if str(name)],
        )
        return serialize_native_animation_pose_evaluation(result)
    except Exception as exc:
        return {
            "available": True,
            "success": False,
            "pose_changed": False,
            "errors": [f"native_animation_pose_evaluation_failed:{exc}"],
            "warnings": [],
            "applied_methods": [],
            "probe_results": [],
            "sample_time_seconds": float(sample_time_seconds),
            "bone_count": 0,
            "changed_bone_count": 0,
            "max_location_delta": 0.0,
            "max_rotation_angle_delta_degrees": 0.0,
            "max_scale_delta": 0.0,
        }


def apply_animation_pose_to_component(component, animation_asset, sample_time_seconds: float) -> dict:
    warnings = []
    applied_methods = []
    success = False
    call_trace = []
    if not component or not animation_asset:
        return {
            "success": False,
            "warnings": ["component_or_animation_missing"],
            "applied_methods": [],
            "call_trace": [],
            "available_component_methods": [],
            "available_single_node_methods": [],
        }

    set_editor_property_variants(
        component,
        "pre_animation_flags",
        [
            ("pause_anims", False),
            ("no_skeleton_update", False),
            ("force_ref_pose", False),
            ("force_refpose", False),
            ("use_ref_pose_on_init_anim", False),
            ("enable_animation", True),
            ("update_animation_in_editor", True),
            ("global_anim_rate_scale", 1.0),
        ],
        call_trace,
        warnings,
        applied_methods,
    )

    visibility_enum = getattr(unreal, "VisibilityBasedAnimTickOption", None) or getattr(unreal, "EVisibilityBasedAnimTickOption", None)
    visibility_value = None
    if visibility_enum:
        for enum_name in ("ALWAYS_TICK_POSE_AND_REFRESH_BONES", "AlwaysTickPoseAndRefreshBones"):
            if hasattr(visibility_enum, enum_name):
                visibility_value = getattr(visibility_enum, enum_name)
                break
    if visibility_value is not None:
        set_editor_property_variants(
            component,
            "visibility_based_anim_tick_option",
            [("visibility_based_anim_tick_option", visibility_value)],
            call_trace,
            warnings,
            applied_methods,
        )

    call_method_variants(
        component,
        "set_update_animation_in_editor",
        ["set_update_animation_in_editor", "SetUpdateAnimationInEditor"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_enable_animation",
        ["set_enable_animation", "SetEnableAnimation"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_component_tick_enabled",
        ["set_component_tick_enabled", "SetComponentTickEnabled"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "activate",
        ["activate", "Activate"],
        [(True,)],
        call_trace,
        warnings,
        applied_methods,
    )

    if hasattr(unreal, "AnimationMode"):
        mode_set, _ = call_method_variants(
            component,
            "set_animation_mode",
            ["set_animation_mode", "SetAnimationMode"],
            [
                (unreal.AnimationMode.ANIMATION_SINGLE_NODE, True),
                (unreal.AnimationMode.ANIMATION_SINGLE_NODE,),
            ],
            call_trace,
            warnings,
            applied_methods,
        )
        success = mode_set or success

    override_applied, _ = call_method_variants(
        component,
        "override_animation_data",
        ["override_animation_data", "OverrideAnimationData"],
        [
            (animation_asset, False, False, float(sample_time_seconds), 0.0),
            (animation_asset, False, False, float(sample_time_seconds), 1.0),
        ],
        call_trace,
        warnings,
        applied_methods,
    )
    success = override_applied or success

    set_animation_applied, _ = call_method_variants(
        component,
        "set_animation",
        ["set_animation", "SetAnimation"],
        [(animation_asset,)],
        call_trace,
        warnings,
        applied_methods,
    )
    success = set_animation_applied or success

    call_method_variants(
        component,
        "stop",
        ["stop", "Stop"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_play_rate",
        ["set_play_rate", "SetPlayRate"],
        [(0.0,)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "set_position",
        ["set_position", "SetPosition"],
        [
            (float(sample_time_seconds), False),
            (float(sample_time_seconds),),
        ],
        call_trace,
        warnings,
        applied_methods,
    )

    single_node_instance = None
    _, single_node_instance = call_method_variants(
        component,
        "get_single_node_instance",
        ["get_single_node_instance", "GetSingleNodeInstance"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    if single_node_instance:
        call_method_variants(
            single_node_instance,
            "single_node_set_animation_asset",
            ["set_animation_asset", "SetAnimationAsset"],
            [(animation_asset, False, 0.0), (animation_asset, False)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_looping",
            ["set_looping", "SetLooping"],
            [(False,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_play_rate",
            ["set_play_rate", "SetPlayRate"],
            [(0.0,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_playing",
            ["set_playing", "SetPlaying"],
            [(False,)],
            call_trace,
            warnings,
            applied_methods,
        )
        call_method_variants(
            single_node_instance,
            "single_node_set_position_with_previous_time",
            ["set_position_with_previous_time", "SetPositionWithPreviousTime"],
            [(float(sample_time_seconds), 0.0, False), (float(sample_time_seconds), 0.0)],
            call_trace,
            warnings,
            applied_methods,
        )
        pose_set, _ = call_method_variants(
            single_node_instance,
            "single_node_set_position",
            ["set_position", "SetPosition"],
            [(float(sample_time_seconds), False), (float(sample_time_seconds),)],
            call_trace,
            warnings,
            applied_methods,
        )
        success = pose_set or success

    call_method_variants(
        component,
        "tick_animation",
        ["tick_animation", "TickAnimation"],
        [(float(sample_time_seconds), False), (0.0, False)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "tick_pose",
        ["tick_pose", "TickPose"],
        [(float(sample_time_seconds), False), (0.0, False)],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "refresh_bone_transforms",
        ["refresh_bone_transforms", "RefreshBoneTransforms"],
        [(None,), tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    call_method_variants(
        component,
        "update_bounds",
        ["update_bounds", "UpdateBounds"],
        [tuple()],
        call_trace,
        warnings,
        applied_methods,
    )
    for method_name in ("mark_render_transform_dirty", "mark_render_dynamic_data_dirty", "mark_render_state_dirty"):
        if hasattr(component, method_name):
            try:
                getattr(component, method_name)()
                applied_methods.append(method_name)
            except Exception:
                continue

    return {
        "success": bool(success),
        "warnings": warnings,
        "applied_methods": applied_methods,
        "call_trace": call_trace,
        "available_component_methods": interesting_member_names(
            component,
            [
                "set_animation_mode",
                "SetAnimationMode",
                "override_animation_data",
                "OverrideAnimationData",
                "set_animation",
                "SetAnimation",
                "play_animation",
                "PlayAnimation",
                "stop",
                "Stop",
                "set_position",
                "SetPosition",
                "set_play_rate",
                "SetPlayRate",
                "get_single_node_instance",
                "GetSingleNodeInstance",
                "tick_animation",
                "TickAnimation",
                "tick_pose",
                "TickPose",
                "refresh_bone_transforms",
                "RefreshBoneTransforms",
                "update_bounds",
                "UpdateBounds",
                "set_update_animation_in_editor",
                "SetUpdateAnimationInEditor",
                "set_enable_animation",
                "SetEnableAnimation",
            ],
        ),
        "available_single_node_methods": interesting_member_names(
            single_node_instance,
            [
                "set_animation_asset",
                "SetAnimationAsset",
                "set_looping",
                "SetLooping",
                "set_play_rate",
                "SetPlayRate",
                "set_playing",
                "SetPlaying",
                "set_position",
                "SetPosition",
                "set_position_with_previous_time",
                "SetPositionWithPreviousTime",
                "get_current_time",
                "GetCurrentTime",
                "get_length",
                "GetLength",
            ],
        ),
    }





