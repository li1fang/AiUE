# Post-E1 / Q5C-lite Platform Review

## Summary

After the `c -> e -> E1 -> a -> d` route, AiUE is no longer in the stage of proving basic viability.

It now has:

- a stable dual-host structure
- a shared Unreal runtime plugin
- generic slot composition across `weapon + clothing + fx`
- an evidence-first demo milestone (`E1`)
- layered quality work that now reaches `Q5C-lite`
- a usable tooling layer (`T1/T2`) for evidence browsing and diagnostics

This changes the central question.

The project is no longer mainly asking:

- "can this be made to work?"

It is now asking:

- "which parts are already platform-grade, and which parts still need structural hardening before scale-up?"

## Current Evidence Snapshot

Latest overall evidence state:

- latest reports present: `29`
- latest reports passing: `29`
- active line reports: `8`
- platform line reports: `10`
- historical / other reports: `11`

Latest route-relevant reports:

- [latest_visual_proof_v1_report.json](C:/AiUE/Saved/verification/latest_visual_proof_v1_report.json)
- [latest_visible_conflict_inspection_q5a_report.json](C:/AiUE/Saved/verification/latest_visible_conflict_inspection_q5a_report.json)
- [latest_volumetric_fit_spatial_evidence_q5bx_report.json](C:/AiUE/Saved/verification/latest_volumetric_fit_spatial_evidence_q5bx_report.json)
- [latest_volumetric_inspection_q5c_lite_report.json](C:/AiUE/Saved/verification/latest_volumetric_inspection_q5c_lite_report.json)
- [latest_showcase_demo_e1_report.json](C:/AiUE/Saved/verification/latest_showcase_demo_e1_report.json)

Current route-specific status:

- `Q5B.x = pass`
- `E1 = pass`
- `Q5C-lite = pass`
- `T1 latest evidence pack = refreshed`
- `T2 latest smoke = pass`
- `pytest = 25 passed`

## Capability Assessment

### 1. Dual-host architecture

Status: strong

Why:

- `UEIntroProject` is still the correct kernel host
- `AiUEdemo` is still the correct presentation host
- the split now feels structural rather than provisional

Judgment:

- keep this architecture
- do not collapse back to a single host

### 2. Shared Unreal runtime plugin

Status: strong

Why:

- slot application logic still converges into the shared runtime
- the demo and kernel lines are not drifting into separate host-local implementations
- later QA and demo work are still consuming the same runtime contract

Judgment:

- this remains the true platform center
- future feature work should keep landing here first

### 3. Generic slot platform

Status: strong

Why:

- `skeletal_mesh` and `static_mesh` are already first-class
- `weapon + clothing + fx` coexistence is proven
- slot conflict policy is explicit and evidence-backed

Judgment:

- no rewrite needed
- the platform abstraction is now good enough to support broader content axes

### 4. Demo capability line

Status: medium-strong and improving

Why:

- `E1` now exists as a real gate, not just a loose demo idea
- `E1` is connected to `T1/T2`, so the demo line is not floating outside the evidence system
- the current route makes `E2 playable demo` a gated follow-up rather than immediate scope drift

Judgment:

- this is the right sequencing
- `E1` should be stabilized, not bypassed

### 5. Quality line

Status: strong and moving in the right direction

Why:

- `Q5A` solves visible conflict proof
- `Q5B` solves first fit heuristics
- `Q5B.x` thickens the spatial evidence surface
- `Q5C-lite` starts local volumetric reasoning without claiming universal auto-fix

Judgment:

- this line is now credible
- it still needs deeper geometry evidence before any "self-healing" claims

### 6. Tooling layer

Status: strong

Why:

- `T1` is now a real evidence-pack pipeline, not just helper scripts
- `T2` is genuinely useful for local inspection and machine-readable smoke
- current latest evidence is visible through the same workbench instead of requiring manual log hunting

Judgment:

- this is one of the best current investments in the repo
- future QA work should continue to plug into this layer

## Robustness Tiers

### High robustness

- dual-host structure
- shared runtime plugin direction
- generic slot abstraction
- `P1 -> P4`
- `Q1 -> Q4`
- `R1 -> R3`
- `T1 / T2`
- `Q5A / Q5B / Q5B.x / Q5C-lite`
- `E1` as a first-pass evidence milestone

### Medium robustness

- demo action preview and retarget-related workflows
- richer spatial / volumetric logic beyond the current hair fixture
- cross-workflow maintainability as the number of gates keeps growing

### Low robustness / visible technical debt

- oversized runtime helper modules
- oversized workflow runner scripts
- lingering historical lines still present as reports
- long-term legacy compatibility surface that is intentionally deferred

## The Real Current Risks

### 1. Runtime code concentration moved, but did not disappear

The `inspection.py` split was worth it.
That was a real improvement.

Current runtime file sizes now make the next risk obvious:

- [retarget.py](C:/AiUE/adapters/unreal/host_project/runtime/retarget.py): `2871` lines
- [common.py](C:/AiUE/adapters/unreal/host_project/runtime/common.py): `2237` lines
- [capture.py](C:/AiUE/adapters/unreal/host_project/runtime/capture.py): `1196` lines
- [inspection.py](C:/AiUE/adapters/unreal/host_project/runtime/inspection.py): `16` lines

Judgment:

- the old inspection monolith is no longer the problem
- the next structural hotspot is now `retarget.py`, then `common.py`

### 2. Workflow growth is becoming a governance problem

Several active workflow scripts are already large enough to behave like mini-subsystems:

- [run_editor_gate_g1.py](C:/AiUE/workflows/pmx_pipeline/run_editor_gate_g1.py): `677`
- [run_live_fx_visual_quality_r3.py](C:/AiUE/workflows/pmx_pipeline/run_live_fx_visual_quality_r3.py): `650`
- [run_multi_slot_composition_p4.py](C:/AiUE/workflows/pmx_pipeline/run_multi_slot_composition_p4.py): `618`
- [run_demo_gate_d1.py](C:/AiUE/workflows/pmx_pipeline/run_demo_gate_d1.py): `566`
- [run_showcase_demo_e1.py](C:/AiUE/workflows/pmx_pipeline/run_showcase_demo_e1.py): `527`

Judgment:

- this is not yet a rewrite signal
- it is a clear governance signal
- future work should prefer extracting more shared workflow helpers before adding many more gate-specific branches

### 3. `Q5C-lite` is promising, but still narrow

Right now the quality story is honest and useful.
That is good.

But `Q5C-lite` is still:

- body vs clothing
- one narrow fixture family
- deterministic local-fit reasoning, not universal geometric truth

Judgment:

- keep calling it `Q5C-lite`
- do not oversell it as full content auto-QA yet

## Should Anything Be Rewritten?

Current answer: no large-scale rewrite is justified.

Why:

- the architecture direction is now coherent
- the major uncertainty is no longer concept viability
- the current limitations are mostly maintainability and depth-of-evidence issues, not evidence that the whole approach is wrong

What *is* justified:

- targeted governance hardening
- more shared workflow skeletons
- selective deeper tooling for spatial evidence

## Libraries And Tools: What Is Worth Adding

### Worth considering next

#### 1. `psutil` for tooling/process diagnostics

Why:

- helpful for future `T2` soak and stability diagnostics
- useful if the workbench grows a richer health view
- low risk and tool-only

Judgment:

- good candidate for a later `T1.x / T2.x`

#### 2. `trimesh` or a similar offline geometry library

Why:

- useful for richer `Q5C.x` geometry reasoning
- could help with local mesh-derived envelopes, cluster reasoning, and offline spatial experiments
- belongs on the tooling side, not inside UE runtime logic

Judgment:

- promising for future volumetric work
- should be introduced only when a concrete `Q5C.x` experiment needs it

#### 3. stronger process-check tooling

Existing tooling scripts are already good:

- [check_repo_surface.py](C:/AiUE/tools/check_repo_surface.py)
- [check_schema_contracts.py](C:/AiUE/tools/check_schema_contracts.py)
- [check_tripline_reports.py](C:/AiUE/tools/check_tripline_reports.py)

Judgment:

- extending this family is worthwhile
- especially for release/checkpoint hygiene and report-surface drift detection

### Not worth adding right now

#### 1. heavier CV stacks for the sake of novelty

Examples:

- YOLO pose
- full diffusion-side motion tooling
- deep reference-image QA

Why not yet:

- the current bottleneck is not "we have too little ML"
- the current bottleneck is platform governance plus deeper deterministic evidence

#### 2. bigger UI framework changes

Why not yet:

- `T2` is already serving its purpose
- the current need is better data and diagnostics, not a fancier frontend stack

#### 3. database/service infrastructure

Why not yet:

- evidence is still file/report centered
- introducing a service tier now would add operational weight without solving the current bottleneck

## Recommendation

The project is feasible.
More than that: it is now plausibly platformizable.

The right next mindset is not:

- "start over"

It is:

- "protect the gains, harden the biggest hotspots, and only add depth where evidence quality clearly improves"

The most pragmatic next priorities are:

1. stabilize `E1` toward its `E2` entry threshold
2. choose whether the next governance pass targets `retarget.py` or shared workflow skeletons first
3. only then deepen `Q5C` from `lite` toward richer spatial / volumetric evidence

## Bottom Line

Current judgment:

- the project is working
- the architecture direction is correct
- the main risks are maintainability and evidence depth, not fundamental feasibility
- there is no reason to push the whole thing over and start again
