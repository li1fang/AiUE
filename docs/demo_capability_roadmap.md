# Demo Capability Roadmap

## Summary

AiUE now has a stable split between:

- `kernel host`
  - import
  - slot composition
  - registry/loadout generation
  - minimum visual proof
- `demo host`
  - controlled staging
  - camera organization
  - action preview
  - showcase capture

The demo line should no longer grow as scattered one-off gates.
It should advance as a named capability line:

- `E1`: evidence-first showcase demo
- `E2`: playable demo
- `E3`: richer demo orchestration

## Capability Line

### E1: Evidence-First Showcase Demo

Purpose:

- prove that the current ready bundles can be shown credibly in the `demo host`
- keep the output easy to archive, review, and consume through `T1/T2`
- avoid jumping too early into interactive UI or gameplay logic

Fixed scope:

- host: `demo`
- packages: current `2` ready bundles
- axes:
  - character
  - weapon
  - clothing
  - FX
  - one validated action-preview path

Output shape:

- `3` fixed camera shots per package
- hero-shot evidence
- before/after action frames
- gate-style JSON report
- `T1` evidence-pack visibility
- `T2` workbench readability

Current state:

- [latest_showcase_demo_e1_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_report.json)
- [latest_showcase_demo_e1_stability_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_stability_report.json)
- `status = pass`
- `required_package_count = 2`
- `passing_packages = 2`
- `captured_before_images = 6`
- `captured_after_images = 6`
- `hero_shots_passed = 2`
- `motion_pass_shots = 6`
- `E1 stability = pass`
- `stable_reruns = 2/2`
- `T2 latest consumption = pass`

Gate trigger for moving on:

- `E1` first full pass
- plus `2` consecutive stable reruns
- plus `T2` stable consumption of the latest `E1` evidence

Current judgment:

- the `E1 -> E2` entry condition is now satisfied
- `E2` can become a dedicated work item without weakening the evidence-first sequencing

### E2: Playable Demo

Purpose:

- add user-facing interaction only after the evidence-first line is stable
- turn the current showcase assets and staging into a simple controlled demo experience

Current first slice:

- [latest_playable_demo_e2_bootstrap_report.json](C:/AiUE/Saved/verification/latest_playable_demo_e2_bootstrap_report.json)
- [playable_demo_e2_session.json](C:/AiUE/Saved/demo/e2/latest/playable_demo_e2_session.json)
- `status = pass`
- `required_package_count = 2`
- `resolved_package_count = 2`
- `session_entries = 2`
- `packages_with_animation_presets = 2`
- `session_smoke_passed_packages = 2 / 2`
- `discussion_signal.reason = first_complete_playable_demo_e2_bootstrap_pass`

What this slice proves:

- the current `2` ready bundles can be normalized into a reusable playable-session manifest
- each package now carries:
  - host blueprint identity
  - slot bindings for `weapon / clothing / fx`
  - one action preset
  - at least one validated animation preset
  - hero-shot evidence links
- each session entry survives a one-shot full-stack `action-preview` smoke inside `demo host`

What this slice does **not** prove yet:

- no player-facing in-editor UI
- no runtime bundle switcher widget
- no packaged playable flow
- no claim that `E2` is feature-complete

Interpretation:

- `playable_demo_e2_bootstrap` is the first `E2` checkpoint
- it opens the path for future interactive work, but it is still evidence-backed bootstrap work rather than a finished playable demo

Current second slice:

- `T2` now auto-discovers [playable_demo_e2_session.json](C:/AiUE/Saved/demo/e2/latest/playable_demo_e2_session.json)
- `T2 --latest --dump-state-json --exit-after-load` now exposes:
  - `demo_session.status`
  - `demo_session.package_ids`
  - `selected_default_package`
  - `selected_default_action_preset`
  - `selected_default_animation_preset`
- the Windows native workbench now has a dedicated `Demo Session` view for:
  - package switching
  - action preset selection
  - animation preset selection
  - package-level session JSON inspection

What this second slice still does **not** do:

- it does not launch UE commands directly
- it does not yet provide a true playable control loop
- it is a native session explorer, not the final `E2` interaction layer

Current third slice:

- `T2 --latest --dump-state-json --exit-after-load` now also exposes `demo_request`
- `demo_request.requests.action_preview` is now shaped as a ready host-command request
- `demo_request.requests.animation_preview` is now shaped as a ready host-command request
- the Windows native workbench now has a dedicated `Demo Request` view that follows the current package and preset selection

What this third slice proves:

- the current `E2` session state can now be deterministically lowered into concrete host-command payloads
- the lowering stays read-only and local to `T2`
- the request surface is now stable enough for the next slice to decide whether to:
  - save request JSON
  - call a runner
  - or attach a future controlled launch button

What this third slice still does **not** do:

- it does not execute the generated requests
- it does not yet own a full launch lifecycle
- it is a request surface, not the final playable control loop

Current fourth slice:

- `tools/run_e2_demo_request.ps1` now provides a repo-local controlled runner for the current `E2` request surface
- the runner can:
  - resolve the current request from `--latest` or a specific manifest
  - dump the selected request JSON
  - export the request to a file
  - invoke the request through the existing host bridge
  - invoke the same path in `--dry-run` mode for controlled smoke checks
- the runner keeps the execution boundary outside the native UI while reusing the same deterministic request lowering that `T2` exposes

What this fourth slice proves:

- the `E2` request surface is now executable through a stable repo-local tooling path
- request selection is deterministic enough to support:
  - automation smoke tests
  - request export
  - future controlled launch integration
- the repo no longer has to rebuild playable-demo request payloads ad hoc once the selection has already been resolved in `T2`

What this fourth slice still does **not** do:

- it does not yet add an in-app launch button to the Windows native workbench
- it does not own session lifecycle management after the initial command invocation
- it is a controlled request runner, not the final playable demo shell

Not in scope yet:

- complex game loop
- runtime authoring UI
- replacing gate-style verification with pure interaction

Entry condition:

- `E1` has crossed its stability gate
- the current evidence surfaces already answer the core trust questions

### E3: Richer Demo Orchestration

Purpose:

- expand from single demo captures into reusable demo sequences
- support richer choreography across character, weapon, clothing, FX, and actions
- preserve evidence traceability while the demo becomes more expressive

Likely ingredients:

- staged sequence presets
- stronger shot planning
- bundle switching
- curated highlight reels

## Design Rules

- `UEIntroProject` remains the automation kernel host.
- `AiUEdemo` remains the presentation host.
- demo work does not replace the platform proof gates.
- evidence and demo should share artifacts instead of inventing separate parallel proof systems.
- `E1` answers "can we show this credibly?"
- `E2` answers "can someone play with it?"

## Near-Term Follow-Up

After the current `c -> e -> E1 -> a -> d` route:

1. stabilize `E1` with repeat passes
2. keep `playable_demo_e2_bootstrap` as the controlled `E2` entry slice
3. keep `E2 session explorer` and `E2 request surface` as the native control foundation
4. decide when the next `E2` slice should execute the generated requests rather than only expose them
5. keep the demo line connected to `Q5` evidence rather than drifting into pure presentation work
