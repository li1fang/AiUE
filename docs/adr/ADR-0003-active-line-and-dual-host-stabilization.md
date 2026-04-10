# ADR-0003: Active Line And Dual-Host Stabilization

## Status
Accepted

## Context
AiUE has already proven the current PMX automation line is viable:

- `V1` proves kernel-host visual truth for character and weapon visibility.
- `D1` proves demo-host onboarding.
- `D8-D12` prove retargeted animation preview, stability, and cross-bundle reuse.
- `Q1-Q3` prove subject visibility, composition quality, and semantic framing quality.

The problem is no longer viability; it is maintainability. Two structural issues became persistent:

1. `C:\AiUE\adapters\unreal\host_project\aiue_unreal_command.py` accumulated most host runtime behavior in one file.
2. Active workflow scripts repeated the same gate/report scaffolding and left the retired `G2` line adjacent to active development.

## Decision
The active line is formally defined as:

`V1 -> D1 -> D12 -> Q1 -> Q2 -> Q3`

Host responsibilities are fixed as:

- `UEIntroProject` is the kernel host.
- `AiUEdemo` is the demo host.

`G2` is retired. It remains archived for historical reference but is not part of the active line.

`S1` is a stabilization phase, not a feature phase. During `S1` we:

- keep the existing command surface stable
- split host runtime implementation into functional modules
- extract shared workflow skeleton helpers
- archive retired `G2` assets outside the active path
- prove non-regression by rerunning the active checkpoints

## Consequences
Positive:

- host runtime behavior is organized by domain instead of one monolith
- active workflow scripts share a single source of truth for gate/report scaffolding
- the repo now has an explicit distinction between active line and legacy experiments

Tradeoffs:

- `S1` intentionally does not add clothing/FX/reference QA features
- some historical gates remain in the repo but are explicitly non-active
- active workflow scripts still exist as separate gates, but now share common infrastructure

## Follow-up
After `S1`, the next phase should prioritize either:

- `Q4` style quality tightening, or
- a platform-level extension that proves the system is not weapon-only

Those choices should build on the stabilized active line rather than reopening the retired `G2` track.
