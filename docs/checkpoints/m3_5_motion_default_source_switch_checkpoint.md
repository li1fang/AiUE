# M3.5 Motion Default-Source Switch

`M3.5` is the first narrow cutover node after `M3`.

It does not widen motion semantics.
It does one focused thing:

`turn the current toy-yard motion export from default-source candidate into an actually applied default-source route inside AiUE.`

Fixed shape:

- source report: `latest_motion_default_source_readiness_m3_report.json`
- workspace must resolve a complete `toy_yard_motion_view_root` context
- cutover validation replays one targeted package through the existing motion seam
- no raw motion discovery is allowed
- no toy-yard SQLite dependency is allowed

Default runner:

- [run_motion_default_source_switch_m3_5.ps1](/C:/AiUE/run_motion_default_source_switch_m3_5.ps1)
- [run_motion_default_source_switch_m3_5.py](/C:/AiUE/workflows/pmx_pipeline/run_motion_default_source_switch_m3_5.py)

Latest report:

- `Saved/verification/latest_motion_default_source_switch_m3_5_report.json`

`M3.5 = pass` means:

- the workspace resolves motion packets through toy-yard export as the normal source
- one targeted replay still passes with `owner = none`
- the cutover is no longer just a readiness opinion
