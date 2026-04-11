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

Current fifth slice:

- `T2` now exposes a lightweight `demo_request_control` state alongside `demo_request`
- the Windows native workbench now provides controlled buttons for:
  - `Export Action Request`
  - `Export Animation Request`
  - `Dry Run Action Request`
  - `Dry Run Animation Request`
- `T2 --dump-state-json --exit-after-load` can now include the control result when called with:
  - `--demo-request-export`
  - `--demo-request-dry-run`
  - `--demo-request-kind action_preview|animation_preview`

What this fifth slice proves:

- the native workbench is no longer limited to session reading and request lowering
- it can now surface a controlled execution seam while keeping the scope intentionally small
- the same native tool now exposes:
  - current request intent
  - current workspace config
  - last export or dry-run result
  - request/result artifact paths
- that makes the Windows tooling layer materially more testable and easier to automate against

What this fifth slice still does **not** do:

- it still does not own a full playable session lifecycle
- it still does not provide general-purpose UE operation controls
- it is a native control surface for `export + dry-run`, not a complete playable shell

Current sixth slice:

- `T2` now extends the same native control surface from `export + dry-run` to explicit `invoke`
- the Windows native workbench now provides:
  - `Invoke Action Request`
  - `Invoke Animation Request`
- `T2 --dump-state-json --exit-after-load` can now also surface invoke results when called with:
  - `--demo-request-invoke`
  - `--demo-request-kind action_preview|animation_preview`
- `demo_request_control` now carries additional execution fields:
  - `dry_run`
  - `result_status`
  - `invocation_returncode`

What this sixth slice proves:

- the native workbench can now issue the currently selected playable-demo request through the same stateful control seam it already used for export and dry-run
- the request path remains deterministic and testable because:
  - request lowering is unchanged
  - invocation still routes through the existing repo-local runner path
  - the control result still lands in the same machine-readable state surface
- `T2` is now able to expose all three control stages:
  - request export
  - request dry-run
  - request invoke

What this sixth slice still does **not** do:

- it still does not provide full session orchestration
- it still does not support free-form host commands beyond the current `E2` request surface
- it is a cautious native invoke path, not a finished playable-demo shell

Current seventh slice:

- [latest_playable_demo_e2_credibility_report.json](C:/AiUE/Saved/verification/latest_playable_demo_e2_credibility_report.json)
- [playable_demo_e2_control_state.json](C:/AiUE/Saved/demo/e2/latest/playable_demo_e2_control_state.json)
- `status = pass`
- `resolved_package_count = 2`
- `invoke_count = 4`
- `action_motion_verified = 2`
- `animation_pose_verified = 2`
- `2` reruns after the first full pass also remained `pass`

What this seventh slice proves:

- the native control path is now credible, not merely callable
- `T2` can now:
  - select a package
  - select its action and animation presets
  - invoke both through the native control seam
  - read back machine-readable evidence into a latest control-state artifact
- the current `2` ready bundles now have proof for:
  - action motion credibility
  - animation pose credibility
  - artifact persistence
  - `T2` readback

What this seventh slice still does **not** do:

- it still treats each invoke as a separate native action
- it still does not provide session-level orchestration from a single native round control
- it is a trusted native control loop, not yet a session roundtrip

Current eighth slice:

- [latest_playable_demo_e2_session_roundtrip_report.json](C:/AiUE/Saved/verification/latest_playable_demo_e2_session_roundtrip_report.json)
- [playable_demo_e2_round_state.json](C:/AiUE/Saved/demo/e2/latest/playable_demo_e2_round_state.json)
- `T2 --latest --demo-session-round-invoke --dump-state-json --exit-after-load` now exposes:
  - `demo_round_control`
  - `demo_round_state`
- the Windows native workbench now provides:
  - `Invoke Session Round`

What this eighth slice proves:

- `T2` can now orchestrate a full session-level round across the current `2` ready bundles
- one native control action now drives:
  - `2 x action_preview`
  - `2 x animation_preview`
- the result is persisted as a round-level latest artifact rather than only per-request latest artifacts
- the session-level seam is now machine-readable enough for a dedicated `E2` gate to validate directly

What this eighth slice still does **not** do:

- it still does not provide a packaged playable shell
- it still does not own free-form live session mutation inside UE
- it is a native session roundtrip, not yet a richer playable loop

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

Current judgment after `E2A credibility` and `E2 session roundtrip`:

1. the `E2` line is no longer blocked on trust questions
2. the repo now has:
   - native selection
   - native invoke
   - native session-round orchestration
   - machine-readable latest control and round state
3. `Dynamic Balance` remains `pass` with `recommended_next_round_kind = flexible`

Recommended next route:

1. `E2C`: add a curated native demo review layer on top of the current roundtrip seam
2. keep the review output evidence-first so `T1/T2` stay the source of truth
3. only switch to `Q5C-lite` early if quality pressure rises above demo progress pressure
4. only pull governance forward if hotspot pressure escalates from `moderate` to `high`

What `E2C` should answer:

- can the current session-round control seam produce a package-focused demo review artifact that is easy for a human operator to trust and reuse
- can `T2` surface the latest per-package action and animation outcomes without needing ad-hoc log diving
- can the next playable slice stay bounded without turning into a free-form operator console

What should stay out of scope until after `E2C`:

- packaged desktop demo distribution
- generalized UE command consoles inside `T2`
- richer live session mutation without evidence persistence
- replacing quality gates with presentation-only flows
