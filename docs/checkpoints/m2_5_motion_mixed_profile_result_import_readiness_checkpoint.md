# M2.5 Motion Mixed-Profile Result Import Readiness

`M2.5` 的职责是把 `M2` 的“fixture diversity 已跑绿”进一步收束成一个更窄、更明确的问题：

`当前 mixed-profile motion export，是否已经具备稳定的 result-import / roundtrip 证据面。`

这一层不重新发起 Unreal 执行，不重跑 motion consumer。它只读取现有 `M2` / `M0.5` 报告，并检查：

- 当前 mixed profile 至少覆盖 `3` 个 package
- 顶层 `sample_ids / scenario_ids` 已明确存在
- 单值 `sample_id / scenario_id` 在 mixed profile 下保持空值
- 每个 package 的 consumer result 继续为 `pass`
- 每个 package 的 `owner = none`
- 每个 package 都保留完整的 import / preview / result-import artifact

默认 runner：

- [run_motion_mixed_profile_result_import_readiness_m2_5.ps1](/C:/AiUE/run_motion_mixed_profile_result_import_readiness_m2_5.ps1)
- [run_motion_mixed_profile_result_import_readiness_m2_5.py](/C:/AiUE/workflows/pmx_pipeline/run_motion_mixed_profile_result_import_readiness_m2_5.py)

最新报告：

- `Saved/verification/latest_motion_mixed_profile_result_import_readiness_m2_5_report.json`

`M2.5` 通过不代表 motion 已经正式切换为默认源。它只证明：

- 当前 mixed-profile export 足够稳定
- 当前 AiUE result 证据足够完整
- 下一步已经可以进入 default-source candidate readiness 判断
