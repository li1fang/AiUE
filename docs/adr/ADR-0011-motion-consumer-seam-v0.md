# ADR-0011: toy-yard <-> AiUE Motion Consumer Seam v0

## Status

Accepted

## Context

AiUE and toy-yard have now reached a different class of motion discussion than the earlier PMX packet work.

What is already true on the producer side:

- toy-yard can publish a portable motion packet
- the packet includes machine-readable summary, registry, packet self-check, and communication signal
- the packet can be selected without consulting toy-yard SQLite
- the packet is intended to stay warehouse-neutral rather than becoming an Unreal implementation repo

What is already emerging on the consumer side:

- AiUE has started a real `import-motion-packet` consumption path
- the current implementation already has to resolve:
  - source artifact selection
  - optional `bvh -> fbx` conversion
  - target skeleton resolution
  - Unreal import behavior
  - runtime preview and retarget-facing follow-up

That means the next risk is no longer "can motion be stored and handed off."

The next risk is:

- where the producer/consumer boundary sits
- which fields are required at the seam
- which failures belong to toy-yard versus AiUE
- how runtime results should be written back in a machine-readable way

If that seam is not written down now, both sides will keep learning through implementation, but the boundary will drift.

## Decision

AiUE adopts a dedicated `motion consumer seam v0` for toy-yard handoff.

This seam is intentionally narrow.

It is not yet:

- a full motion platform API
- a stable public CLI surface
- a commitment that toy-yard owns Unreal-side execution

It is:

- a machine-readable producer-to-consumer contract
- a machine-readable consumer result contract
- an explicit ownership split
- the contract surface for the first shadow-consumer round

## Boundary

### toy-yard owns

- canonical warehouse and lineage
- portable motion packet export
- packet summary and registry
- packet self-check
- packet-side communication signal
- result-import contract on the warehouse side

### AiUE owns

- packet consumption and file adapter behavior
- optional source conversion for importable runtime use
- target skeleton and host resolution
- Unreal or Blender execution strategy
- retarget preflight, import, preview, and runtime validation
- consumer-side communication signal and result writing

## Seam Shape

The v0 seam is split into three layers.

### 1. Packet In

AiUE consumes the existing toy-yard portable packet as the producer-facing truth source.

The minimum producer evidence set is:

- `summary/motion_suite_summary.json`
- `summary/motion_clip_registry.json`
- `summary/motion_packet_check.json`
- `summary/communication_signal.json`
- `clips/*/manifest.json`

The manifest and summary remain toy-yard-owned.

AiUE v0 treats the following producer facts as required for selection:

- `export_contract_version`
- `source = "toy-yard export"`
- `package_id`
- `sample_id`
- `clip_id`
- `pack_version`
- `format_profile`
- `runtime_semantics`
- `placeholder_motion = false`
- `validation.status = pass`
- a resolvable motion artifact:
  - `motion_fbx` preferred when present
  - otherwise `motion_bvh`
- a resolvable skeleton artifact

### 2. Consumer Request

AiUE defines its own internal request contract for motion consumption.

The first request contract is documented in:

- `docs/contracts/motion_consumer_request_v0.schema.json`

The v0 request is intentionally small and operation-oriented.

Supported operations are fixed as:

- `import_motion_packet`
- `retarget_preflight`
- `animation_preview`

For the first formal shadow-consumer round:

- `import_motion_packet` is required
- `animation_preview` is recommended
- `retarget_preflight` is optional

This keeps the first seam aligned with the current shadow-consumer path instead of inventing a broader abstraction too early.

### 3. Consumer Result

AiUE writes a machine-readable result that toy-yard can later import or inspect.

The first result contract is documented in:

- `docs/contracts/motion_consumer_result_v0.schema.json`

The result must answer five questions directly:

1. which packet and clip were consumed
2. which operation AiUE ran
3. whether the result passed or failed
4. whether the failure belongs to AiUE or toy-yard
5. which generated assets and runtime evidence were produced

If a result fails, it must still remain owner-stable:

- `owner` stays one of `toy-yard | aiue | none`
- if AiUE cannot further subdivide, it still writes `owner = aiue`
- `failure_class` is required on failed results

## Communication Signal Rules

The producer and consumer both expose a machine-readable communication signal.

### Producer signal

toy-yard's signal answers:

- is the packet handoff-ready
- should AiUE contact toy-yard before trying to consume

### Consumer signal

AiUE's signal answers:

- after consumption, should the next follow-up go back to toy-yard
- or is the failure local to AiUE runtime, import, retarget, or preview

The owner decision for AiUE v0 is fixed as:

- `toy-yard`
  - packet root missing
  - manifest or packet-check missing
  - unsupported producer contract shape
  - selection-ready packet cannot be resolved from the export
- `aiue`
  - conversion failure
  - target skeleton resolution failure
  - Unreal import failure
  - retarget failure
  - preview or runtime validation failure
- `none`
  - no external follow-up needed

## Consequences

Positive:

- keeps toy-yard from drifting into Unreal-consumer implementation ownership
- gives AiUE a clear place to formalize motion consumption without widening the stable CLI surface
- makes future motion discussion evidence-first and machine-readable
- prepares a cleaner handoff for later motion source expansion

Tradeoffs:

- the seam is still narrow and Unreal-oriented on the consumer side
- raw motion quality, semantic pose QA, and richer retarget configuration are not solved by v0
- the first round still assumes a controlled skeleton/profile family

## Recommended Next Step

The next implementation node should be:

- `M0.5 Motion Shadow Packet Trial`

But the order should be:

1. align on this seam
2. run the shadow-consumer path against the seam
3. only then decide whether additional producer-side contract changes are needed

That is better than waiting for "full motion validation" before boundary alignment, because once consumer implementation grows, the cost of correcting boundary drift rises quickly.

## Follow-Up

The seam is now considered proven enough to serve as the active motion boundary for the current controlled profile.

What made that true:

- `M3.5` established default-source cutover on the AiUE side
- `M4` established a first reusable motion quality line
- `M4.5` establishes a single roundtrip handoff bundle for toy-yard result import

If later evolution is needed, future versions may still add:

- direct `motion_fbx` preference rules in the packet registry
- explicit target skeleton profile negotiation
- richer result-import payloads for warehouse ingestion
- a dedicated `consumer_ready` state derived from real AiUE consumption
- broader motion family coverage beyond the current controlled sample set
