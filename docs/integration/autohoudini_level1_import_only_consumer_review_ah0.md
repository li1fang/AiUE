# AutoHoudini Level1 Import-Only Consumer Review `AH0`

## 结论

AiUE 已认可 `autoHoudini Level1` 这条 seam，并已在本地实现并跑通一条 **AiUE 自有的 import-only consumer**。

当前状态可以概括为：

- `AH1` 已通过
- AiUE 可以直接读取 `autoHoudini` 的 Level1 sidecar request
- AiUE 可以在 `demo host` 中把 Level1 curve bundle 导入为 `CurveFloat` 资产集合
- AiUE 会同时写出：
  - 一份 AiUE-native verification report
  - 一份 mirrored external result

本轮不包含 preview。preview fixture 对齐与 import+preview 闭环留到 `AH1.5 / AH2`。

## 本轮已实现内容

AiUE 本轮新增内部命令：

- `import-level1-curve-bundle`

固定边界：

- 只消费 `autohoudini_aiue_level1_consumer_request_v0`
- 只支持：
  - `operation = import_level1_curve_bundle`
  - `unreal_import_mode = curve_float_asset_set`
- 只负责：
  - 读取 `ue_manifest`
  - 读取 `curve_csv`
  - 校验 channel 与 `time_s`
  - 逐 channel 导入 `CurveFloat`
- 不负责：
  - remote execution
  - Linux launcher
  - SSH/SCP
  - preview host / level / skeleton 对齐

## 真实通过证据

本轮真实通过使用：

- workspace:
  - `C:\AiUE\local\pipeline_workspace.toyyard.motion.trial-turn-hand-ready.local.json`
- request:
  - `C:\Projects\toy-yard\05_publish\aiue_motion\autohoudini-level1-toyyard-houdini-smoke\workspace_views\aiue_level1_consumer_request.json`

最新通过报告：

- `C:\AiUE\Saved\verification\latest_autohoudini_level1_import_only_consumer_ah1_report.json`

本轮外部镜像结果：

- `C:\AiUE\Saved\verification\autohoudini_level1_import_only_consumer_ah1_20260418T132454Z\autohoudini_aiue_level1_consumer_result_v0.json`

本轮导入结果摘要：

- `status = pass`
- `host_key = demo`
- `resolved_import_mode = curve_float_asset_set`
- `row_count = 10`
- `channel_count = 4`
- `imported_asset_count = 4`

实际导入落点：

- `/Game/AutoHoudini/Curves/pkg_ah_level1_toyyard_houdini_smoke_20260418t042424z/CF_*`

## 对 autoHoudini 的评审结论

AiUE 认可当前 seam 方向，但建议 `autoHoudini` 下一步优先收紧两件事。

### 必须调整 1：不要把 launcher identity 写死进 external result schema

当前 external result schema 把下面两项写死为常量：

- `execution_shell.owner_system = autohoudini`
- `execution_shell.tool = run_aiue_level1_handoff.py`

这在 `planned_not_implemented` 阶段还勉强成立，但在 AiUE 已经拥有真实 consumer implementation 之后，会造成语义漂移。

原因很简单：

- 现在真正执行 Unreal import 的是 AiUE
- `autoHoudini` 不应再被 schema 强制声明为 execution owner
- `run_aiue_level1_handoff.py` 也不应被当成跨环境硬合同

建议调整方向：

- `execution_shell.owner_system` 改为枚举或自由字段
  - 至少允许：`aiue | autohoudini`
- `execution_shell.tool` 改为描述当前触发器，而不是写死某个 launcher 文件名
- 如果仍想保留 launcher 信息，建议把它降为：
  - `transport_tool`
  - 或 `handoff_launcher`

### 必须调整 2：preview 相关路径不应作为 portable hard contract

当前 request 里这些字段是可接受的：

- `target_host_blueprint_asset_path`
- `target_skeleton_asset_path`
- `preview_level_path`

但在 `AH1` 阶段，它们只能被视为：

- hint
- sample-scoped context
- future preview fixture seed

它们不应被当作跨环境、跨项目、跨机器的 portable hard contract。

建议调整方向二选一：

1. 保持它们为 optional hint，并在 schema/文档里明确：
   - import-only consumer 不依赖这些字段成功
2. 后续进入 preview 时，把它们升级为稳定 fixture 标识，例如：
   - `preview_fixture_id`
   - `target_skeleton_profile_id`
   - `target_host_fixture_id`

AiUE 更偏向第二种，因为它更适合长期多环境协作。

## 当前不建议 autoHoudini 推进到 AiUE 内部的内容

本轮不建议 `autoHoudini` 继续把下面这些内容推入 AiUE 责任域：

- Linux remote execution
- `fxhoudinimcp`
- `run_aiue_level1_handoff.py` ownership
- SSH/SCP transport
- preview orchestration

这些都不属于当前 import-only seam 的必要部分。

## 推荐下一步

推荐下一步顺序如下：

1. `autoHoudini` 接受本轮两条 seam 调整建议
2. 保持当前 request/result 的 compact 方向
3. 与 AiUE 对齐 `preview fixture id` 的未来合同，而不是继续堆 sample path
4. 再进入 `AH1.5 / AH2`
   - import + preview
   - fixture 对齐
   - preview result 验证

## 简短评价

这轮最重要的价值，不是“又多了一条临时试跑脚本”，而是：

- AiUE 已经把 `autoHoudini Level1` 变成了一条真实可运行的 consumer seam
- 这条 seam 现在已经足够支撑下一轮 preview 讨论
- 同时边界仍然清晰，没有把 `autoHoudini` 的 remote execution 层吸进 AiUE
