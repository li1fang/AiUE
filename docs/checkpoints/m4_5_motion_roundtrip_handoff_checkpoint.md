# M4.5 Motion Roundtrip Handoff

`M4.5` 是本轮 motion 收口节点。

它不再扩 motion 能力，也不再重新证明默认源或质量线。  
它只回答一个更协作导向的问题：

`AiUE 现在是否已经能把 motion 默认源 + 质量线结果整理成 toy-yard 真正容易导入的一份 handoff bundle。`

固定站位：

- 前置：`M3.5 = pass`
- 前置：`M4 = pass`
- 输入：现有 `M2.5 / M3.5 / M4` 报告和 package artifacts
- 输出：单个 handoff bundle + 单个 gate 风格报告

固定检查内容：

- `motion_consumer_request_v0` 仍然可读
- `motion_consumer_result_v0` 仍然可读
- 每个 package 的 import / preview / consumer artifacts 都存在
- 每个 package 的 owner 仍然是 `none`
- 最终生成单个 roundtrip handoff bundle，方便 toy-yard 导入

默认 runner：

- [run_motion_roundtrip_handoff_m4_5.ps1](/C:/AiUE/run_motion_roundtrip_handoff_m4_5.ps1)
- [run_motion_roundtrip_handoff_m4_5.py](/C:/AiUE/workflows/pmx_pipeline/run_motion_roundtrip_handoff_m4_5.py)

最新报告：

- `Saved/verification/latest_motion_roundtrip_handoff_m4_5_report.json`

最新 handoff bundle：

- `Saved/verification/.../motion_roundtrip_handoff_bundle.json`

`M4.5 = pass` 的含义是：

- motion seam 不只是内部跑绿
- 它已经具备一次干净、明确、machine-readable 的跨仓回流交接面
