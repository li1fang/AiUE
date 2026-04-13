# M3 Motion Default-Source Readiness

`M3` 站在 `M2.5` 之上，只回答一个更高层的问题：

`当前 toy-yard motion export，是否已经够资格成为 AiUE 的 default-source candidate。`

`M3` 仍然不是默认切换本身。它不直接修改工作流路由，只给出 candidate 级判断。

固定前置：

- `M2 readiness = pass`
- `M2 = pass`
- `M2.5 = pass`
- mixed profile 至少覆盖 `3` 个 package / `3` 个 distinct scenarios
- `communication_signal.handoff_ready = true`
- `communication_signal.problem_owner = none`

默认 runner：

- [run_motion_default_source_readiness_m3.ps1](/C:/AiUE/run_motion_default_source_readiness_m3.ps1)
- [run_motion_default_source_readiness_m3.py](/C:/AiUE/workflows/pmx_pipeline/run_motion_default_source_readiness_m3.py)

最新报告：

- `Saved/verification/latest_motion_default_source_readiness_m3_report.json`

`M3 = pass` 的含义是：

- 当前 motion export contract 已经不只是“可试跑”
- 它已经具备进入下一轮 default-source 路由讨论的证据基础

`M3 = fail` 则表示：

- 仍有 mixed-profile contract 缺口
- 或 producer signal 仍不够稳定
- 或 AiUE result-import 证据还不够完整
