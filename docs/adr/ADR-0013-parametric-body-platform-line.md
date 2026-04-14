# ADR-0013: Parametric Body Platform Line

## Status

Accepted

## Context

AiUE already has working proof across:

- validation and quality gates
- evidence-first and native demo lines
- governance and tooling surfaces
- toy-yard motion default-source and roundtrip handoff

What the repo still lacks is a coherent next platform line that can absorb high-value modular body work without collapsing back into:

- ad hoc DCC experiments
- runtime-first overreach
- demo-driven validation drift
- consumer contracts that are wider than the current evidence surface

The new body problem is also structurally different from the older PMX and motion lanes.

The available assets are not consumer-friendly game-ready modular kits.
They are high-value source modules with difficult seams, narrow domain assumptions, and a much higher upside if the pipeline is constrained correctly.

## Decision

AiUE adopts a dedicated `Body Platform Line`.

This line becomes the next primary platform lane.

The first stage is intentionally narrow:

- domain: sexy anime-styled girl family
- first supported axes:
  - `head`
  - `bust`
  - `leg_length / height`
- fixed core:
  - `core_torso_arm`
- `hair` is an attached compatibility axis, not part of the first body contract core

### Stack

The line uses:

- `Houdini` for offline fusion, soft-tissue data generation, and repeatable recipes
- `UE / AiUE` for runtime consumption, visualization, QA, and evidence
- `Blender` only as an auxiliary tool, not as the primary body-authoring contract
- `AccuRig` only as bootstrap or exploration, not as the long-term truth source

### Delivery Shape

AiUE does **not** treat raw scanned body fragments as runtime-consumable modules.

The first production route is:

1. inventory the source morphology
2. define a narrow parametric body contract
3. fuse a canonical full-body fixture offline
4. prove rig transfer on the fused body family
5. prove runtime body consumption in the existing AiUE host and quality stack

### Roadmap

The body line is fixed as:

- `C0`: modular morphology inventory
- `C1`: parametric body contract
- `C2`: canonical fusion fixture
- `C3`: skeletal transfer proof
- `C4`: runtime body assembly proof

Soft-tissue work is deferred until `C4` first pass.

Its layered route is fixed as:

- `H0`: inertial base layer
- `H1`: pose traction layer
- `H2`: collision / constraint layer
- `H3`: runtime surrogate

## Consequences

Positive:

- gives the repo a new platform line without destabilizing the existing validation and demo lines
- prevents runtime-first modular-body work from outrunning offline fusion and rig truth
- keeps playable demo work presentation-first rather than letting it become the new proof authority
- lets motion remain green and useful without blocking the new body-platform line

Tradeoffs:

- body work is now explicitly narrow-domain rather than general humanoid
- the first body milestone is inventory and contract work, not a flashy runtime swapper
- the repo will rely on Houdini for the highest-value body-authoring layer

## Follow-Up

The immediate next implementation slice is:

- `C0 Modular Morphology Inventory`

`C0` must:

- inventory real source modules into machine-readable evidence
- identify candidate fixture families
- choose a canonical family for the first constrained body contract
- wire the result into `T1/T2` as a first `body_platform_line` report
