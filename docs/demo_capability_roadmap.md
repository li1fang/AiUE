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
- `status = pass`
- `required_package_count = 2`
- `passing_packages = 2`
- `captured_before_images = 6`
- `captured_after_images = 6`
- `hero_shots_passed = 2`
- `motion_pass_shots = 6`

Gate trigger for moving on:

- `E1` first full pass
- plus `2` consecutive stable reruns
- plus `T2` stable consumption of the latest `E1` evidence

### E2: Playable Demo

Purpose:

- add user-facing interaction only after the evidence-first line is stable
- turn the current showcase assets and staging into a simple controlled demo experience

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
2. decide when `E2` should become a dedicated work item
3. keep the demo line connected to `Q5` evidence rather than drifting into pure presentation work
