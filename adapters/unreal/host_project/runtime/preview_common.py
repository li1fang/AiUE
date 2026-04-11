from __future__ import annotations

from .common import *

def _apply_slot_binding_overrides(actor, request: dict) -> list[str]:
    warnings = []
    override_bindings = list(request.get("slot_binding_overrides") or [])
    if not override_bindings:
        return warnings
    if not hasattr(unreal, "PMXEquipmentBlueprintLibrary"):
        warnings.append("pmx_blueprint_library_unavailable")
        return warnings
    try:
        unreal.PMXEquipmentBlueprintLibrary.apply_slot_bindings(
            actor,
            runtime_slot_binding_entries_from_request(override_bindings),
        )
    except Exception as exc:
        warnings.append(f"apply_slot_binding_overrides_failed:{exc}")
    return warnings

