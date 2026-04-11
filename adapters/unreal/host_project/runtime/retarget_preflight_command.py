from __future__ import annotations

from .common import *
from .retarget_profile import *
from .retarget_session import (
    apply_retarget_configured_loadout,
    destroy_retarget_host,
    prepare_retarget_host_session,
)


def retarget_preflight(request: dict) -> dict:
    prepared = prepare_retarget_host_session(
        request,
        actor_label_prefix="AIUE_RetargetPreflight",
        default_location=unreal.Vector(0.0, 0.0, 120.0),
        default_rotation=make_rotator(0.0, 180.0, 0.0),
        require_animation_asset=True,
    )
    if prepared.get("status") != "pass":
        return prepared

    warnings = list(prepared.get("warnings") or [])
    level_path = prepared.get("level_path")
    host_asset_path = prepared["host_asset_path"]
    host_record = prepared.get("host_record")
    animation_asset_path = str(prepared.get("animation_asset_path") or "")
    animation_asset = prepared.get("animation_asset")
    actor_subsystem = prepared["actor_subsystem"]
    spawned_host = prepared["spawned_host"]
    blocking_reasons = []
    try:
        apply_retarget_configured_loadout(spawned_host, warnings)

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
        destroy_retarget_host(actor_subsystem, spawned_host)


__all__ = ["retarget_preflight"]
