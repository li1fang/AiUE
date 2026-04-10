from __future__ import annotations

from collections import defaultdict


def _normalized_binding(binding: dict | None) -> dict:
    payload = dict(binding or {})
    if not payload:
        return {}
    return {
        "slot_name": str(payload.get("slot_name") or ""),
        "item_package_id": str(payload.get("item_package_id") or ""),
        "item_kind": str(payload.get("item_kind") or ""),
        "attach_socket_name": str(payload.get("attach_socket_name") or ""),
        "asset_path": str(
            payload.get("asset_path")
            or payload.get("skeletal_mesh_asset")
            or payload.get("static_mesh_asset")
            or payload.get("niagara_system_asset")
            or ""
        ),
        "consumer_ready": bool(payload.get("consumer_ready", False)),
        "skeletal_mesh_asset": str(payload.get("skeletal_mesh_asset") or ""),
        "static_mesh_asset": str(payload.get("static_mesh_asset") or ""),
        "niagara_system_asset": str(payload.get("niagara_system_asset") or ""),
    }


def _normalized_component(component: dict | None) -> dict:
    payload = dict(component or {})
    if not payload:
        return {}
    return {
        "component_name": str(payload.get("component_name") or ""),
        "class_name": str(payload.get("class_name") or ""),
        "asset_path": str(payload.get("asset_path") or ""),
        "visible": bool(payload.get("visible", False)),
        "hidden_in_game": bool(payload.get("hidden_in_game", False)),
        "bounds": dict(payload.get("bounds") or {}),
        "attach": dict(payload.get("attach") or {}),
    }


def _normalized_attach_state(state: dict | None) -> dict:
    payload = dict(state or {})
    if not payload:
        return {}
    return {
        "slot_name": str(payload.get("slot_name") or ""),
        "requested_attach_socket_name": str(payload.get("requested_attach_socket_name") or ""),
        "resolved_attach_socket_name": str(payload.get("resolved_attach_socket_name") or ""),
        "resolved_attach_socket_exists": payload.get("resolved_attach_socket_exists"),
        "resolution_strategy": str(payload.get("resolution_strategy") or ""),
        "attach_parent_name": str(payload.get("attach_parent_name") or ""),
        "attach_parent_class": str(payload.get("attach_parent_class") or ""),
    }


def _coverage_records_from_shots(visual_check: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for shot in list(visual_check.get("shots") or []):
        image_path = str(shot.get("image_path") or "")
        shot_id = str(shot.get("shot_id") or "")
        tracked_slot_coverages = dict(shot.get("tracked_slot_coverages") or {})
        for slot_name, coverage in tracked_slot_coverages.items():
            payload = dict(coverage or {})
            grouped[str(slot_name)].append(
                {
                    "shot_id": shot_id,
                    "image_path": image_path,
                    "coverage_ratio": float(payload.get("coverage_ratio") or 0.0),
                    "screen_rect": dict(payload.get("screen_rect") or {}),
                }
            )
        weapon_coverage = float(shot.get("weapon_screen_coverage") or 0.0)
        if weapon_coverage > 0 or shot.get("weapon_visible"):
            grouped["weapon"].append(
                {
                    "shot_id": shot_id,
                    "image_path": image_path,
                    "coverage_ratio": weapon_coverage,
                    "screen_rect": {},
                }
            )
    return grouped


def build_slot_debugger_payload(report_index: dict) -> dict:
    reports_by_gate_id = dict(report_index.get("reports_by_gate_id") or {})
    p4_report = dict((reports_by_gate_id.get("multi_slot_composition_p4") or {}).get("report") or {})
    q4_report = dict((reports_by_gate_id.get("multi_slot_quality_gate_q4") or {}).get("report") or {})
    r3_report = dict((reports_by_gate_id.get("live_fx_visual_quality_r3") or {}).get("report") or {})

    p4_runtime_by_package = {
        str(item.get("package_id") or ""): dict(item) for item in list(p4_report.get("runtime_checks") or [])
    }
    p4_visual_by_package = {
        str(item.get("package_id") or ""): dict(item) for item in list(p4_report.get("visual_checks") or [])
    }
    q4_by_package = {
        str(item.get("package_id") or ""): dict(item) for item in list(q4_report.get("per_package_results") or [])
    }
    r3_by_package = {
        str(item.get("package_id") or ""): dict(item) for item in list(r3_report.get("per_package_results") or [])
    }

    package_ids = sorted(set(p4_runtime_by_package) | set(p4_visual_by_package) | set(q4_by_package) | set(r3_by_package))
    packages = []
    for package_id in package_ids:
        runtime_check = p4_runtime_by_package.get(package_id, {})
        visual_check = p4_visual_by_package.get(package_id, {})
        q4_package = q4_by_package.get(package_id, {})
        r3_package = r3_by_package.get(package_id, {})
        tracked_coverages = _coverage_records_from_shots(visual_check)
        slots = []
        for slot_name in ("weapon", "clothing", "fx"):
            binding = _normalized_binding(runtime_check.get(f"{slot_name}_binding"))
            if not binding and slot_name == "fx":
                binding = _normalized_binding(r3_package.get("fx_binding"))
            component = _normalized_component(runtime_check.get(f"{slot_name}_component"))
            if not component and slot_name == "fx":
                component = _normalized_component(r3_package.get("with_fx_component"))
            attach_state = _normalized_attach_state(runtime_check.get(f"{slot_name}_attach_state"))
            slot_conflicts = [
                dict(item)
                for item in list(runtime_check.get("slot_conflicts") or [])
                if str(item.get("slot_name") or "") == slot_name
            ]
            superseded_bindings = [
                dict(item)
                for item in list(runtime_check.get("superseded_bindings") or [])
                if str(item.get("slot_name") or "") == slot_name
            ]
            if not any([binding, component, attach_state, tracked_coverages.get(slot_name), slot_conflicts, superseded_bindings]):
                continue
            slots.append(
                {
                    "slot_name": slot_name,
                    "binding": binding,
                    "managed_component": component,
                    "attach_state": attach_state,
                    "tracked_coverages": tracked_coverages.get(slot_name, []),
                    "slot_conflicts": slot_conflicts,
                    "superseded_bindings": superseded_bindings,
                    "planned_artifacts": {
                        "image": None,
                        "mask": None,
                        "depth": None,
                    },
                }
            )
        packages.append(
            {
                "package_id": package_id,
                "sample_id": str(runtime_check.get("sample_id") or q4_package.get("sample_id") or ""),
                "host_blueprint_asset": str(runtime_check.get("host_blueprint_asset") or r3_package.get("host_blueprint_asset") or ""),
                "status": str(q4_package.get("status") or runtime_check.get("status") or "unknown"),
                "hero_shot_ids": list(q4_package.get("hero_shot_ids") or []),
                "external_candidate_sources": [],
                "slots": slots,
            }
        )

    return {
        "package_count": len(packages),
        "packages": packages,
        "external_candidate_sources": [],
    }
