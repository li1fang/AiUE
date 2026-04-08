# AiUE Landscape + Positioning

## Position

`AiUE` is an AI-facing Unreal automation/control layer.

It is not:

- a replacement for Unreal Python
- a replacement for Gauntlet
- a replacement for Commandlets
- a replacement for Remote Control
- an unrestricted destructive shell

It is:

- a capability registry
- a guarded task runner
- a stable schema surface for tools and AI agents
- a workflow-pack host
- a policy engine for mode selection and fallback

## Why This Is Not Just Another Wrapper

Unreal already has strong primitives:

- Unreal Editor Python scripting
- Editor tests
- Functional testing
- Gauntlet
- Remote Control
- Commandlets
- Interchange import pipelines

`AiUE` adds the missing layer:

- what exists vs. what is reliable on this exact machine
- guarded commands instead of raw API guessing
- structured outputs instead of log scraping
- policy recommendations instead of static defaults
- workflow packs that can evolve without changing the core contract

## Comparison Matrix

| Tool / Surface | Strength | Gap That AiUE Covers |
| --- | --- | --- |
| Unreal Python | Fast editor automation | No stable capability registry or AI-facing command surface |
| Commandlets | Good headless batch entrypoints | Heavyweight for rapid iteration and mode comparison |
| Gauntlet | Strong scenario automation | Higher setup cost than current workflow-driven editor probes |
| Remote Control | Great external control surface | Not a workflow/policy/capability registry by itself |
| Interchange | Strong asset import abstraction | Focused on import, not end-to-end AI-safe automation |
| UnrealCV | Useful external control and image capture | Not a general guarded workflow platform for this project |
