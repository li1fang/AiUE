## Motion Staged Goal And Roadmap

### Current Position

AiUE has now crossed the first meaningful motion seam threshold:

- `toy-yard -> AiUE` motion packet handoff is machine-readable and stable
- `import-motion-packet` passes on the controlled trial fixture
- `retarget-bootstrap` and `animation-preview` can execute end-to-end
- `motion_shadow_packet_trial_m0_5` currently passes with `owner = none`

Current latest proof:

- `C:\AiUE\Saved\verification\latest_motion_shadow_packet_trial_m0_5_report.json`
- latest rerun on `2026-04-13T11:44:42Z` remains `pass`
- current latest `consumer_result` now settles to:
  - `status = pass`
  - `owner = none`
  - `subject_visible = true`
  - `pose_changed = true`
  - `warnings = []`
  - `generated_assets.import_mode = source_bundle_fallback`

### Stage Goal

The next practical motion stage goal is:

`M1 Motion Consumer Baseline`

`M1` should answer one narrow but important question:

`Can AiUE reliably consume a controlled toy-yard motion packet, retarget it onto the current demo host, and produce credible preview evidence without ownership ambiguity?`

### M1 Acceptance Shape

`M1` is considered established when all of the following stay true on the controlled trial fixture:

- `motion_shadow_packet_trial_m0_5` remains `pass`
- `consumer_result.status = pass`
- `communication_signal.owner = none`
- `subject_visible = true`
- `pose_changed = true`
- retarget flow includes:
  - import
  - bootstrap
  - preview
- source authored chains cover at least:
  - `root`
  - `Spine`
  - `LeftClavicle`
  - `RightClavicle`
  - `LeftArm`
  - `RightArm`

Current status:

- `M1` is now established on the controlled fixture
- latest proof: `C:\AiUE\Saved\verification\latest_motion_consumer_baseline_m1_report.json`
- current baseline counts:
  - `iterations_requested = 3`
  - `iterations_completed = 3`
  - `iterations_passed = 3`
  - `subject_visible_passes = 3`
  - `pose_changed_passes = 3`
  - `owner_none_passes = 3`

### Roadmap

#### M1

`M1 Motion Consumer Baseline`

Scope:

- single controlled motion packet
- single controlled demo host
- evidence-first motion consume / retarget / preview path

Primary output:

- stable `motion_consumer_request_v0`
- stable `motion_consumer_result_v0`
- stable `M0.5` latest report with `owner = none`

#### M1.x

`M1.x Chain Quality Hardening`

Scope:

- improve PMX source chain planning
- reduce warning noise caused by stale or superseded diagnostics
- improve meaningful authored-chain coverage before expanding fixture count

Current focus:

- keep `M0.5` green
- keep `consumer_result` readable enough to serve as a real handoff artifact
- reduce residual warnings to the truly unresolved motion quality gaps

#### M2

`M2 Motion Fixture Diversity`

Scope:

- expand beyond the single controlled motion fixture
- validate the same consumer seam against `2-3` distinct motion packets

Primary question:

`Is the current motion consumer path real, or is it only lucky on one sample?`

#### M3

`M3 Motion Default Source Readiness`

Scope:

- only enters after `M2` is green enough
- evaluates whether toy-yard motion export is ready to move from shadow-trial status toward default-source usage

Primary question:

`Can motion packet consumption become a normal path instead of a trial path?`

#### M4

`M4 Motion Quality Line`

Scope:

- stronger motion quality evidence
- richer pose/retarget quality diagnostics
- more robust content-level motion evaluation

Primary question:

`Is the motion path not only executable, but trustworthy as a reusable platform capability?`

### Immediate Next Step

The current recommended next motion step is:

`Choose between M1.5 result-import readiness and M2 fixture diversity`

Specifically:

- use the now-stable baseline to verify toy-yard result-import expectations
- or add the second controlled packet to test whether the seam is broader than one lucky sample
- avoid widening motion semantics before either of those is real

Current recommendation:

- do `M1.5` first
- then enter `M2`

Reason:

- `M1.5` turns the current baseline into a cleaner cross-repo roundtrip surface
- `M2` should start after the first result surface is already import-ready
