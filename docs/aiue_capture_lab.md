# AiUE Capture Lab

## Purpose

`Capture Lab` exists to answer:

- which rendered mode is best for motion screenshots
- whether `jump_land_1cycle` is truly more stable or just lucky
- how camera reuse, level reuse, delay, and finalize wait affect results

## Fixed Experiment Dimensions

- `mode`: `cmd_rendered`, `editor_rendered`
- `level_lifecycle`: `reuse_level`, `reload_level_per_run`
- `camera_lifecycle`: `reuse_camera`, `respawn_camera_per_scenario`
- `scenario_scheduling`: `single_scenario`, `batched_scenarios`
- `scenario`: `idle_2s`, `walk_forward_2s`, `run_forward_2s`, `jump_land_1cycle`
- `capture_delay_seconds`: `0.2`, `0.5`, `1.0`
- `finalize_wait_seconds`: `8`, `15`
