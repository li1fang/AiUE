from __future__ import annotations

from .common import *

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


