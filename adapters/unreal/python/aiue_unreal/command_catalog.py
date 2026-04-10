from __future__ import annotations

COMMANDS = {
    "probe-capabilities": {"module": "probe_capabilities", "category": "probe", "workflow_pack": "core", "destructive": False},
    "get-capability": {"module": "get_capability", "category": "probe", "workflow_pack": "core", "destructive": False},
    "list-assets": {"module": "list_assets", "category": "probe", "workflow_pack": "core", "destructive": False},
    "inspect-host": {"module": "inspect_host", "category": "probe", "workflow_pack": "pmx_pipeline", "destructive": False},
    "inspect-host-visual": {"module": "inspect_host_visual", "category": "probe", "workflow_pack": "pmx_pipeline", "destructive": False},
    "inspect-slot-runtime": {"module": "inspect_slot_runtime", "category": "probe", "workflow_pack": "pmx_pipeline", "destructive": False},
    "inspect-loadout": {"module": "inspect_loadout", "category": "probe", "workflow_pack": "pmx_pipeline", "destructive": False},
    "import-package": {"module": "import_package", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "build-equipment-registry": {"module": "build_equipment_registry", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "validate-package": {"module": "validate_package", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "run-suite": {"module": "run_suite", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "refresh-assets": {"module": "refresh_assets", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "load-level": {"module": "load_level", "category": "scene", "workflow_pack": "core", "destructive": False},
    "spawn-host": {"module": "spawn_host", "category": "scene", "workflow_pack": "pmx_pipeline", "destructive": False},
    "spawn-camera": {"module": "spawn_camera", "category": "scene", "workflow_pack": "core", "destructive": False},
    "capture-frame": {"module": "capture_frame", "category": "capture", "workflow_pack": "core", "destructive": False},
    "stage-capture": {"module": "stage_capture", "category": "capture", "workflow_pack": "pmx_pipeline", "destructive": False},
    "run-scene-sweep": {"module": "run_scene_sweep", "category": "capture", "workflow_pack": "pmx_pipeline", "destructive": False},
    "action-preview": {"module": "action_preview", "category": "capture", "workflow_pack": "pmx_pipeline", "destructive": False},
    "animation-preview": {"module": "animation_preview", "category": "capture", "workflow_pack": "pmx_pipeline", "destructive": False},
    "retarget-preflight": {"module": "retarget_preflight", "category": "probe", "workflow_pack": "pmx_pipeline", "destructive": False},
    "retarget-bootstrap": {"module": "retarget_bootstrap", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "retarget-author-chains": {"module": "retarget_author_chains", "category": "workflow", "workflow_pack": "pmx_pipeline", "destructive": False},
    "delete-generated-assets": {"module": "delete_generated_assets", "category": "maintenance", "workflow_pack": "pmx_pipeline", "destructive": True},
    "delete-suite-registry": {"module": "delete_suite_registry", "category": "maintenance", "workflow_pack": "pmx_pipeline", "destructive": True},
    "rebuild-package": {"module": "rebuild_package", "category": "maintenance", "workflow_pack": "pmx_pipeline", "destructive": True}
}


def get_command_metadata(command_id: str) -> dict:
    if command_id not in COMMANDS:
        raise KeyError(f"Unknown AiUE command: {command_id}")
    return dict(COMMANDS[command_id])
