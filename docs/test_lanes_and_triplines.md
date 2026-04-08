# Test Lanes And Triplines

## Development Lanes

- `Core`
- `Workflow`
- `Labs`
- `Reliability`
- `Repo Hygiene`
- `Data Contract`

Each change should declare one primary lane and one optional assisting lane.

## Triplines

AiUE uses triplines to stop regressions from leaking across lanes.

Default triplines:

- `smoke`
- `weapon_split`
- `core_regression`
- `cmd_rendered`
- `editor_rendered`
- open-source bundle audit
- destructive guard check
- schema backward-compat check

## Practical Rule

If a change touches stable CLI/schema/policy/guard surfaces, it must clear the platform triplines.

If a change is experimental and does not touch stable surface, it can remain advisory until promoted.
