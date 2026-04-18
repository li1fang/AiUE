主题

Re: AiUE 已实现 Level1 import-only consumer，建议按真实结果收紧下一轮 seam

正文

各位同学，

感谢你们前一轮把 `Level1` review packet 和 compact request/result schema 发过来。我们这边已经按当前 seam 做完了第一轮真实实现和真实烟测，先同步结论：

1. AiUE 认可这条 seam 的方向
2. AiUE 已经实现并跑通一条 **import-only consumer**
3. 当前这条 seam 已经从“讨论接口”进入“真实可运行边界”

这轮真实执行使用的是：

- workspace:
  - `C:\AiUE\local\pipeline_workspace.toyyard.motion.trial-turn-hand-ready.local.json`
- request:
  - `C:\Projects\toy-yard\05_publish\aiue_motion\autohoudini-level1-toyyard-houdini-smoke\workspace_views\aiue_level1_consumer_request.json`

最新通过报告：

- `C:\AiUE\Saved\verification\latest_autohoudini_level1_import_only_consumer_ah1_report.json`

镜像 external result：

- `C:\AiUE\Saved\verification\autohoudini_level1_import_only_consumer_ah1_20260418T132454Z\autohoudini_aiue_level1_consumer_result_v0.json`

本轮真实结果是：

- `status = pass`
- `resolved_import_mode = curve_float_asset_set`
- `channel_count = 4`
- `imported_asset_count = 4`
- curve 资产已真实落到：
  - `/Game/AutoHoudini/Curves/pkg_ah_level1_toyyard_houdini_smoke_20260418t042424z/CF_*`

也就是说，AiUE 这边现在已经可以：

- 读取你们的 Level1 sidecar request
- 读取 `ue_manifest + curve_csv`
- 校验 channel/time 结构
- 在 Unreal 中导入 `CurveFloat` 资产集合
- 写出一份 AiUE-native report
- 再镜像一份你们当前 compact result schema

这轮我们没有把 preview 一起做掉。这个是刻意的边界选择，不是遗漏。

当前我们建议把下一步讨论收紧在两件事情上。

第一，建议不要把 launcher identity 写死在 external result schema 里。

当前 schema 把下面两项写死成常量：

- `execution_shell.owner_system = autohoudini`
- `execution_shell.tool = run_aiue_level1_handoff.py`

这在 AiUE 尚未真实实现时还说得过去，但现在 AiUE 已经拥有真实 consumer implementation，再继续写死会造成语义漂移。

更准确的状态应该是：

- request 仍然可以由 `autoHoudini` 发布
- 但实际 consumer execution 已经由 AiUE 承担

所以我们建议：

- `owner_system` 不要再写死
- `tool` 不要再写死某个 launcher 文件名
- launcher/transport 信息如果要保留，建议降成 metadata，而不是 execution truth

第二，建议把 preview 相关路径视为 hint，而不是 portable hard contract。

当前 request 里的：

- `target_host_blueprint_asset_path`
- `target_skeleton_asset_path`
- `preview_level_path`

在本轮实现里都只被保留到 request snapshot，没有参与 import-only 逻辑。

我们认为这才是当前正确的边界。

如果后续要进入 preview，比较稳的做法是：

1. 继续允许这些字段作为 optional hint
2. 同时开始设计更稳定的 fixture 标识，例如：
   - `preview_fixture_id`
   - `target_skeleton_profile_id`
   - `target_host_fixture_id`

这样就不会把 sample path 意外升级成跨环境硬合同。

同时也明确一下，我们当前不建议 AiUE 去吸收下面这些责任：

- Linux remote execution
- SSH/SCP
- `fxhoudinimcp`
- `run_aiue_level1_handoff.py` 的 launcher ownership

这些都不属于当前 Level1 import-only seam 的必要部分。

我们更建议的下一步顺序是：

1. 先按这轮真实结果，把 compact result schema 收紧一轮
2. 把 preview 路径从 hard contract 降成 hint，或升级成 fixture id 方向
3. 然后再进入 `AH1.5 / AH2`
   - import + preview
   - fixture 对齐
   - preview result 验证

总的来说，我们对这条 seam 的评价是积极的。

这轮最重要的结果不是“又讨论了一轮接口”，而是：

- AiUE 已经把这条 Level1 seam 做成了真实可运行的 consumer
- 这条线现在已经足够支撑下一轮 preview 设计
- 同时边界仍然是清晰的，没有把 remote execution 层卷进 AiUE

如果你们认同，我们下一轮就可以直接围绕：

- result schema 收紧
- preview fixture seam

这两件事继续推进。
