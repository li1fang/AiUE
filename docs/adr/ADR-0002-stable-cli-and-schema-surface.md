# ADR-0002: Stable CLI And Schema Surface

## Status

Accepted

## Decision

Freeze these public Alpha commands:

- `aiue probe`
- `aiue run`
- `aiue lab capture`
- `aiue policy recommend-capture`

Freeze these public Alpha schema families:

- `aiue_action_spec`
- `aiue_action_result`
- `aiue_capabilities`
- `aiue_probe_report`
- `aiue_capture_lab_report`
- `aiue_capture_policy`

## Why

- public collaboration needs a predictable surface
- workflow and lab iteration should not constantly break tooling

## Consequences

- breaking changes require ADR and migration notes
- workflow-specific fields may evolve under the stable envelope
