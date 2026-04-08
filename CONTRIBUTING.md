# Contributing

## First Steps

1. Read [README](README.md), [Whitepaper](WHITEPAPER.md), and [Architecture](docs/aiue_architecture.md).
2. Identify the lane your change belongs to.
3. Check whether your change touches the stable surface.

## Choose the Right Entry Point

- Bug or regression: use an issue form
- New workflow-pack idea: use the workflow-pack proposal issue form
- Stable-surface design change: open a discussion or ADR first
- Workflow or lab improvement that does not change stable contracts: open a focused PR

## Stable Surface Rules

Changes touching any of these require extra care:

- `aiue probe`
- `aiue run`
- `aiue lab capture`
- `aiue policy recommend-capture`
- any schema in `schemas/`

If you change those surfaces, include:

- motivation
- compatibility impact
- migration notes
- tests or gate updates

## Pull Request Expectations

- State the primary lane
- State whether the change affects stable surface
- Call out tripline impact
- Add or update docs if behavior changes
- Keep experimental changes behind clear boundaries if they are not yet release-gated

## Before Opening a PR

- Run the local checks documented in [test_lanes_and_triplines.md](docs/test_lanes_and_triplines.md)
- Confirm the repo surface stays public-export safe
- Confirm destructive guards still behave correctly
