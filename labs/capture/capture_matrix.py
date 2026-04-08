from __future__ import annotations

from itertools import product


SCENARIOS = ["idle_2s", "walk_forward_2s", "run_forward_2s", "jump_land_1cycle"]

COMPLETION_STRATEGIES = {
    "native_helper_wait": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.05,
        "quit_barrier_seconds": 2.0,
    },
    "passive_poll": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.2,
        "quit_barrier_seconds": 2.0,
    },
    "poll_until_task_done_then_grace": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.2,
        "quit_barrier_seconds": 2.0,
    },
    "pump_viewports_until_file_seen": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.1,
        "quit_barrier_seconds": 2.0,
    },
    "pump_viewports_until_file_stable": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.1,
        "quit_barrier_seconds": 2.0,
    },
    "fixed_quit_barrier_after_request": {
        "settle_timeout_seconds": 6.0,
        "file_stability_window_seconds": 0.75,
        "viewport_pump_interval_seconds": 0.2,
        "quit_barrier_seconds": 2.0,
    },
}


def generate_capture_experiments(focus: str | None = None) -> list[dict]:
    experiments = []
    if focus == "completion":
        for mode, completion_strategy in product(
            ["cmd_rendered", "editor_rendered"],
            list(COMPLETION_STRATEGIES.keys()),
        ):
            strategy_defaults = COMPLETION_STRATEGIES[completion_strategy]
            experiments.append(
                {
                    "mode": mode,
                    "level_lifecycle": "reuse_level",
                    "camera_lifecycle": "reuse_camera",
                    "scenario_scheduling": "single_scenario",
                    "scenario_order": ["run_forward_2s", "jump_land_1cycle"],
                    "capture_delay_seconds": 0.2,
                    "finalize_wait_seconds": 8,
                    "completion_strategy": completion_strategy,
                    **strategy_defaults,
                }
            )
        return experiments

    for mode, level_lifecycle, camera_lifecycle, scenario_scheduling, capture_delay_seconds, finalize_wait_seconds in product(
        ["cmd_rendered", "editor_rendered"],
        ["reuse_level", "reload_level_per_run"],
        ["reuse_camera", "respawn_camera_per_scenario"],
        ["single_scenario", "batched_scenarios"],
        [0.2, 0.5, 1.0],
        [8, 15],
    ):
        experiments.append(
            {
                "mode": mode,
                "level_lifecycle": level_lifecycle,
                "camera_lifecycle": camera_lifecycle,
                "scenario_scheduling": scenario_scheduling,
                "scenario_order": list(SCENARIOS),
                "capture_delay_seconds": capture_delay_seconds,
                "finalize_wait_seconds": finalize_wait_seconds,
                "completion_strategy": "passive_poll",
                **COMPLETION_STRATEGIES["passive_poll"],
            }
        )
    return experiments
