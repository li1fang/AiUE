# AiUE Whitepaper

## Summary

`AiUE` exists to make Unreal automation usable by AI systems and collaborative tooling without forcing them to guess raw Unreal APIs, unsafe side effects, or machine-specific behavior.

The platform sits above Unreal's native primitives and below workflow-specific logic.

## Problem

Unreal already provides powerful automation primitives, but they are fragmented:

- Python gives direct editor access, but not a stable capability registry
- Gauntlet and Commandlets are strong batch tools, but heavier than iterative workflow automation
- Remote Control exposes surfaces, but does not define policy, guards, or workflow contracts
- Individual projects end up building one-off wrappers that are hard to share

For AI-assisted development, the missing layer is not "more raw access". The missing layer is:

- known capability state
- stable task contracts
- guarded execution
- policy-driven fallback
- reusable workflow packs

## Product Boundary

`AiUE` is:

- a capability registry
- a guarded automation CLI
- a stable schema surface
- a workflow-pack host
- a policy engine for execution mode and fallback decisions

`AiUE` is not:

- a replacement for Unreal Python
- a replacement for Gauntlet, Remote Control, Commandlets, or Interchange
- a generic destructive shell over any Unreal content tree
- a PMX-only repository

## Product Layers

- `Core`: schema, registry, policy, compatibility, stable contracts
- `Adapters`: Unreal-specific execution, guards, command catalog, mode routing
- `Workflows`: domain logic such as `PMXPipeline`
- `Labs`: experiment systems such as `Capture Lab`

This layering allows the platform to grow without forcing workflow-specific assumptions into the stable core.

## Why This Project Is Worth Open-Sourcing

`AiUE` is not just another wrapper around Unreal Python. Its value is the combination of:

- capability registry with machine-specific reliability
- guarded commands with explicit destructive boundaries
- JSON-first contracts that are easier for tools and agents to consume
- workflow packs that can evolve independently of the stable platform surface
- policy outputs that turn experiment results into operational defaults

## Open Alpha Strategy

The first public release should optimize for collaborative development, not maximum feature count.

That means:

- a frozen stable surface
- documented non-goals
- governance and contribution rules
- hard release gates
- one official workflow pack that proves the model

`PMXPipeline` is the first official pack because it already demonstrates:

- import and validation workflows
- capability probe integration
- scene sweep and capture policy loops
- regression and cross-mode validation

## Long-Term Direction

The long-term goal is for `AiUE` to host more than one workflow pack and more than one lab, proving it is a platform instead of a vertical demo.

Likely expansion directions:

- additional import or validation workflow packs
- animation and visual review labs
- broader adapter surfaces across Unreal execution environments
