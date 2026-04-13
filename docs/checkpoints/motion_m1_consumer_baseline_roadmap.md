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

Current status:

- `M2` is now green on the curated `trial-motion-m2-diversity` profile
- latest proof: `C:\AiUE\Saved\verification\latest_motion_fixture_diversity_m2_report.json`
- current counts:
  - `package_count = 3`
  - `package_passes = 3`
  - `distinct_scenarios_executed = 3`

#### M2.5

`M2.5 Mixed-Profile Result Import Readiness`

Scope:

- stands on top of `M2`
- does not rerun Unreal
- checks whether mixed-profile package results are complete enough for cross-repo result import and roundtrip handling

Primary question:

`Do the current mixed-profile motion results carry enough stable evidence to roundtrip cleanly?`

Current status:

- `M2.5` is now established on the curated `trial-motion-m2-diversity` profile
- latest proof: `C:\AiUE\Saved\verification\latest_motion_mixed_profile_result_import_readiness_m2_5_report.json`
- current counts:
  - `package_count = 3`
  - `import_ready_packages = 3`
  - `distinct_scenarios = 3`
  - `distinct_samples = 3`

#### M3

`M3 Motion Default Source Readiness`

Scope:

- only enters after `M2.5` is green enough
- evaluates whether toy-yard motion export is ready to move from shadow-trial status toward default-source usage

Primary question:

`Can motion packet consumption become a normal path instead of a trial path?`

Current status:

- `M3` is now green on the curated diversity profile
- latest proof: `C:\AiUE\Saved\verification\latest_motion_default_source_readiness_m3_report.json`
- current candidate snapshot:
  - `default_source_candidate = true`
  - `package_count = 3`
  - `distinct_samples = 3`
  - `distinct_scenarios = 3`
  - `handoff_ready = true`
  - `problem_owner = none`

#### M3.5

`M3.5 Motion Default Source Switch`

Scope:

- stands on top of `M3`
- applies the motion default-source route as a real AiUE cutover node
- replays one targeted package through the normalized toy-yard motion path

Primary question:

`Is motion default-source status now applied in practice, not only accepted in readiness reports?`

Current status:

- `M3.5` is now green on the curated diversity profile
- latest proof: `C:\AiUE\Saved\verification\latest_motion_default_source_switch_m3_5_report.json`
- current cutover snapshot:
  - `default_source_applied = true`
  - `selected_package_id = pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7`
  - `owner = none`
  - `subject_visible = true`
  - `pose_changed = true`

#### M4

`M4 Motion Quality Line`

Scope:

- stronger motion quality evidence
- richer pose/retarget quality diagnostics
- more robust content-level motion evaluation

Primary question:

`Is the motion path not only executable, but trustworthy as a reusable platform capability?`

Current status:

- `M4` is now green on the curated diversity profile
- latest proof: `C:\AiUE\Saved\verification\latest_motion_quality_line_m4_report.json`
- current quality counts:
  - `package_count = 3`
  - `quality_passes = 3`
  - `retarget_successes = 3`
  - `native_pose_changed_passes = 3`
  - `unexpected_warning_packages = 0`

### Immediate Next Step

The current recommended next motion step is:

`Use the new M3.5 and M4 green states to decide whether to normalize default routing further or widen motion quality scope.`

Current recommendation:

- keep the current `M0.5` single-fixture scope lock as historical baseline only
- treat `M2 -> M2.5 -> M3 -> M3.5 -> M4` as the real new evidence ladder
- open the next discussion around:
  - motion default-source routing policy
  - richer multi-packet quality evidence
  - whether the next step should widen motion fixture diversity or deepen motion quality thresholds
