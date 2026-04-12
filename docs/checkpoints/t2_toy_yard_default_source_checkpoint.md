# T2 toy-yard Default Source Checkpoint

## Summary

This checkpoint records the first AiUE-side implementation slice after `T1.6` closed green.

The route decision is now fixed:

- `toy-yard export` becomes the default PMX source for new runs
- the first rollout stays narrow and evidence-first
- legacy local conversion and auto-UE outputs remain as fallback paths, not as the preferred route

## What This Slice Implements

This slice does not introduce a new content gate.

It implements the first repo-side default-source foundation:

- formal toy-yard view helper functions in `workflows/pmx_pipeline/toy_yard_view.py`
- shared resolution helpers for:
  - equipment report
  - suite summary
  - equipment registry
  - manifest index discovery
- `G1` and `D1` updated to consume the helper layer instead of open-coding toy-yard path guesses
- workspace example updated to show `paths.toy_yard_pmx_view_root`

## Why This Matters

Before this checkpoint, the toy-yard path existed, but it still behaved more like an integration side-lane.

After this checkpoint:

- toy-yard export root is a first-class workspace input
- PMX gate resolution prefers toy-yard summary/registry/report artifacts when configured
- the default-source route is no longer just a trial habit; it is expressed in repo structure and docs

## Scope Boundary

This checkpoint does **not**:

- add a new stable CLI surface
- remove old fallback paths
- switch motion into the same rollout
- claim that all historical PMX workflows must be rerouted immediately

## Verification

The helper layer is covered by targeted T1 tests:

- toy-yard view resolution prefers export-root summary/registry/report artifacts
- toy-yard export-shaped manifest indexing works
- manifest indexing ignores malformed manifest JSON instead of crashing the route

## Next Step

The next practical step after this checkpoint is a real new-run confirmation:

- run a fresh PMX workflow with toy-yard export as the default source
- verify that raw `3dgirls` package discovery is not required for that run
- then treat `T2` as the new normal route rather than as a shadow integration lane
