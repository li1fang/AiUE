# Schema Handbook

## Stable Families

AiUE currently treats these schemas as stable Alpha contracts:

- `aiue_action_spec`
- `aiue_action_result`
- `aiue_capabilities`
- `aiue_probe_report`
- `aiue_capture_lab_report`
- `aiue_capture_policy`

## Envelope Fields

Every public JSON report should carry:

- `schema_version`
- `tool_name`
- `workflow_pack`
- `generated_at_utc`
- `compatibility`

## Version Semantics

- major: breaking wire-shape change
- minor: backward-compatible field addition
- patch: documentation or non-structural correction

## Compatibility Rules

- document legacy fields explicitly
- prefer additive changes during Alpha
- breaking changes require ADR and migration notes

## Workflow Contracts

Workflow packs may add domain payloads, but they should not remove or redefine the stable envelope.
