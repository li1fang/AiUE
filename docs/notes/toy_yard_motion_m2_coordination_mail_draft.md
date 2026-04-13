# 邮件草稿

## 主题

AiUE Motion `M2` 前置条件确认：当前 export 仍缺第二个 ready scenario，建议补一轮 motion export

## 正文

各位同学：

我们这边已经把 motion 线推进到下面几个节点：

- `M0.5 Motion Shadow Packet Trial`
- `M1 Motion Consumer Baseline`
- `M1.5 Motion Result Import Readiness`

当前这三层都已经通过，意味着在 AiUE 侧，现有受控 motion 样本已经满足：

- seam 可闭环
- 单样本可重复重跑
- `consumer_result` 可稳定回流
- ownership routing 明确
- 相关 artifact 路径可直接读取

在这个基础上，我们又补做了一步：

- `M2 Motion Fixture Diversity Readiness`

这一步不是正式执行 `M2`，而是先检查当前 toy-yard motion export 是否已经具备进入 `M2` 的输入条件。

当前结论很明确：

- `M2 readiness = fail`
- 失败原因不是 AiUE runtime
- 失败原因是：当前 export 里仍然只有 `1` 个 distinct ready `scenario_id`

当前 latest 报告里的关键结果是：

- `selection_ready_count = 2`
- 但 `distinct_scenario_ids = 1`
- 当前唯一 ready scenario 是：
  - `route-a-3s-turn-hand-ready`

也就是说，目前 export 里的两个 ready package：

- `pkg_route-a-3s-turn-hand-ready-v0-1_a1192762ba`
- `pkg_route-a-3s-turn-hand-ready-v0-2_a70fed1ad7`

本质上仍然是同一动作场景的两个版本包，它们不构成真正的 fixture diversity。

所以我们这边的判断是：

当前不应该假装进入正式 `M2`，  
而应该先请 toy-yard 补一轮 motion export，把至少 `1` 个第二场景的 ready clip 一起导出进 `aiue_motion` 视图。

我们建议优先候选是下面两个里的任意一个：

- `pkg_route-a-3s-two-hand-receive-ready-v0-2_4654f004ac`
- `pkg_route-a-3s-half-turn-present-ready-v0-2_5b37783497`

理想状态是下一轮 export 至少满足：

- `selection_ready >= 2`
- `distinct ready scenario_id >= 2`

这样我们就可以立即在 AiUE 侧进入真正的：

- `M2 Motion Fixture Diversity`

并回答更有价值的问题：

- 这条 motion consumer seam 是否只对当前单一样本成立
- 还是已经能承受第二个真实 motion scenario

如果你们同意，我们建议下一步顺序是：

1. toy-yard 补一轮 motion export
2. AiUE 重新跑 `M2 readiness`
3. readiness 转绿后，立即执行正式 `M2`

谢谢。

## 附件

- `latest_motion_fixture_diversity_readiness_m2_report.json`
  - `C:\AiUE\Saved\verification\latest_motion_fixture_diversity_readiness_m2_report.json`

- `m2_motion_fixture_diversity_readiness_checkpoint.md`
  - `C:\AiUE\docs\checkpoints\m2_motion_fixture_diversity_readiness_checkpoint.md`

- `latest_motion_consumer_baseline_m1_report.json`
  - `C:\AiUE\Saved\verification\latest_motion_consumer_baseline_m1_report.json`

- `latest_motion_result_import_readiness_m1_5_report.json`
  - `C:\AiUE\Saved\verification\latest_motion_result_import_readiness_m1_5_report.json`
