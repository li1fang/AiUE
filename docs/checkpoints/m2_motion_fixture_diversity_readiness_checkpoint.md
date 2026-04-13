# M2 Motion Fixture Diversity Readiness Checkpoint

## Summary

`M2` should be the first point where motion stops depending on a single lucky fixture.

But that only makes sense when the current toy-yard motion export actually contains more than one distinct ready scenario.

This checkpoint exists to make that prerequisite explicit and machine-readable.

## What It Checks

The readiness gate reads the current toy-yard motion export and checks:

- how many `selection_ready` clips exist
- how many distinct `scenario_id` values exist among those clips
- how the ready packages are grouped by scenario

## Why This Matters

Two versions of the same clip are not real fixture diversity.

They are useful for producer evolution and durable packet comparison, but they do not answer the `M2` question:

`Can the AiUE motion consumer seam survive more than one actual motion scenario?`

## Current Rule

`M2` should only start when the export contains at least:

- `2` selection-ready clips
- `2` distinct ready `scenario_id` values

## Current Interpretation

If this readiness checkpoint fails, that is not an AiUE runtime failure.

It means:

- the current export is still too narrow for meaningful `M2`
- the next useful move is coordination with toy-yard to export at least one more validated ready scenario

That keeps `M2` honest instead of pretending diversity from repeated versions of the same motion.
