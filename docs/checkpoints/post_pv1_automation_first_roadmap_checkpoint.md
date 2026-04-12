# Post-PV1 Automation-First Roadmap Checkpoint

## Why This Checkpoint Exists

The repo just reached a useful but slightly awkward state:

- `M1` is green
- `E2B` is green
- `PV1` is wired through `T1/T2`, but still pending a real human signoff

That creates a common failure mode:

- mistaking a playable demo for the main source of truth
- or waiting on manual signoff before continuing automation-first work

This checkpoint exists to lock the next route before that ambiguity grows back.

## Current Read

Current repo truth is:

- automation path is healthy
- presentation path is credible enough to demonstrate
- governance is still honestly reporting one missing human-signoff blind spot
- broader diversity is the next material automation gap

## Route Locked Here

The next route is:

1. `DV2`
2. `E2C`
3. `A1`

`PV1` stays in parallel as a governance signoff track.

## Why This Order

`DV2` comes first because the next real weakness is not "can we make the demo look nicer".
It is "how narrow is the current automated proof surface".

`E2C` comes second because polish becomes more honest after diversity evidence grows.

`A1` comes third because future motion-generation or candidate-provider work should attach to a broader, better-measured platform instead of becoming the next source of hidden uncertainty.

## Non-Goals

This checkpoint does **not** claim:

- `PV1` is already passed
- playable demo can replace automated verification
- current two-bundle coverage is enough for long-term confidence

## Artifacts

- [ADR-0008-post-pv1-automation-first-roadmap.md](/C:/AiUE/docs/adr/ADR-0008-post-pv1-automation-first-roadmap.md)
- [post_pv1_automation_first_route_v1.json](/C:/AiUE/docs/governance/post_pv1_automation_first_route_v1.json)
