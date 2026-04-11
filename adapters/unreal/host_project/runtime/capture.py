from __future__ import annotations

from .capture_stage import *
from .capture_visual import *
from .capture_frame_command import capture_frame
from .capture_scene_sweep import run_scene_sweep


__all__ = [
    "load_level",
    "spawn_host",
    "inspect_stage_anchors",
    "ensure_stage_anchors",
    "capture_frame",
    "capture_frame_for_actor_object",
    "build_visual_proof_shots",
    "explicit_shot_plans_from_request",
    "filtered_visual_shots",
    "capture_visual_shot",
    "run_scene_sweep",
]
