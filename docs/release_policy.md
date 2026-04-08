# Release Policy

## Channel

Current channel: `Alpha`

Version guidance:

- `0.x` while stable surface is still tightening
- major/minor/patch semantics apply to schema and CLI families

## Alpha with Hard Gates

A version is not release-ready unless all of these are satisfied:

- required governance and public docs exist
- `Apache-2.0` is present
- open-source bundle audit passes
- schema contract check passes
- destructive guard check passes
- workspace dry-run passes
- `smoke`, `weapon_split`, and `core_regression` have passing records

`stress` remains a milestone gate, not a per-release hard gate.

## Gate Ownership

- Core and release-gate changes require maintainer review
- Workflow and lab changes may iterate faster, but cannot bypass hard gates if they affect stable surface
