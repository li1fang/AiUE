# toy-yard export contract 调整建议邮件草稿

主题：

AiUE PMXPipeline 真实试跑反馈：validate-package / refresh-assets 已接通，附 export contract 调整建议

正文：

各位同学：

我们这边已经完成了 AiUE 侧针对 toy-yard trial 的第一轮真实试跑，并补齐了之前缺失的两条 AiUE 宿主命令链路：

- `validate-package`
- `refresh-assets`

本轮使用的本地配置与命令如下：

- workspace config
  - `C:\AiUE\local\pipeline_workspace.toyyard.trial-cassia-solo.local.json`
  - `C:\AiUE\local\pipeline_workspace.toyyard.trial-yidhari-bundle.local.json`
- commands
  - `C:\AiUE\local\toy_yard_trials\trial-cassia-solo\run_import_package.cmd`
  - `C:\AiUE\local\toy_yard_trials\trial-cassia-solo\run_validate_package.cmd`
  - `C:\AiUE\local\toy_yard_trials\trial-yidhari-bundle\run_refresh_assets.cmd`

当前试跑结论是：

- AiUE 已经可以直接读取 toy-yard 导出的 `summary / registry / manifest`
- 本轮没有依赖 toy-yard SQLite
- 本轮也没有回退到原始 `3dgirls` 布局做 package discovery
- `refresh-assets` 已经可以真实执行并完成一轮 registry / asset refresh
- 但 `import-package` 仍然被 export contract 本身阻断

我们当前对 toy-yard export contract 的评价是：

- `勉强可用，但仍需调整`

下面分两层说明。

## 1. 必须修改的部分

这些项如果不改，AiUE 这边很难把 toy-yard export 作为真正可跑的默认 PMX source。

### A. manifest 必须改成“可迁移的导出工件路径”

当前 `trial-cassia-solo` 的 manifest 中：

- `output_fbx` 仍指向源机器绝对路径
- `source_file` 也仍指向源机器绝对路径

这会导致：

- AiUE 在当前机器找不到 `output_fbx`
- `import-package` 无法开始
- `validate-package` 只能继续报告 `ue_import_report.local.json / ue_validation_report.local.json` 缺失

建议至少保证：

- `output_fbx` 能直接解析到 toy-yard export 内真实存在的 FBX
- `textures[*].relocated_path` 能直接解析到 toy-yard export 内真实存在的纹理文件
- 当前机器消费只依赖 export 内部路径，不依赖源机器路径

### B. registry 必须补齐 runtime-ready 的 mesh 引用

当前 `refresh-assets` 虽然已经能跑通，但结果仍显示：

- `character_skeletal_mesh = ""`
- `default_weapon_skeletal_mesh = ""`
- `runtime_ready_host_blueprints = 0`

这说明 registry 目前只有 package/bundle 级关系，还没有达到 AiUE runtime 可直接消费的密度。

建议至少补齐：

- `characters[*].skeletal_mesh`
- `characters[*].skeleton`
- `characters[*].physics_asset`
- `ready_pairs[*].weapon_skeletal_mesh`

如果未来还会有 static mesh 物品，也建议同步预留：

- `ready_pairs[*].weapon_static_mesh`

### C. pair / binding 层必须显式给 slot / attach 信息

当前 bundle trial 虽然能生成 host，但 attach 仍偏弱，结果里能看到：

- `equip_slot = null`
- `preferred_attach_target = null`
- `resolved_attach_socket_name = "None"`

建议至少补齐：

- `equip_slot`
- `preferred_attach_target`
  - 推荐包含：
    - `type`
    - `name`

或者直接提供：

- `attach_socket_name`

### D. summary / registry / manifest 建议带明确 contract version

这一项虽然不是唯一 blocker，但我认为已经足够接近“必须”。

建议在以下文件中都加上明确版本字段：

- `manifest.json`
- `ue_suite_summary.json`
- `ue_equipment_registry.json`

建议字段：

- `export_contract_version`
- `exporter_version`
- `source = "toy-yard export"`

这样 AiUE 可以稳定区分历史导出与新版可迁移导出。

## 2. 为了达到更高上限，建议调整的部分

这些项不一定是当前 trial 的直接 blocker，但如果后续目标是把 toy-yard export 做成 AiUE 的默认 PMX source，它们会明显提高上限和稳定性。

### A. 在 registry / summary 层显式给 package -> artifact 映射

如果可以在 summary 或 registry 中直接给出：

- package 对应 manifest 路径
- package 对应导出 FBX 路径
- package 对应 textures 根目录

AiUE 后续做批量 import / validate / refresh 时会更稳定，也更少依赖 conversion 目录扫描。

### B. 把 source lineage 与 runtime consumption 分层

我们建议把字段分成两类：

- `source_*`
  - 只做 lineage / 溯源
- `export_artifacts.*`
  - 只做当前机器消费

这样可以同时保留 lineage 价值，又不让当前机器的导入逻辑被历史绝对路径拖住。

### C. 增加更稳定的 display / normalized 名称

当前部分路径在跨环境日志里会出现乱码样式。

建议增加一层稳定字段，例如：

- `display_name_ascii`
- `normalized_display_name`

这会让 AiUE 侧日志、质检报告、后续 evidence pack 都更可读。

### D. 为 future slot platform 预留更通用的 binding 结构

AiUE 侧已经从 weapon-only 往 generic slot platform 演进。

如果 toy-yard export 后续能更稳定地提供：

- `slot_name`
- `item_kind`
- `attach_socket_name`
- UE asset refs

那后续不只是 character + weapon，连 clothing / FX / 更广义 item 也会更容易直接接入。

### E. 建议尽早规划 motion 是否也进入 toy-yard

这个点不是当前 trial 的 blocker，但我们想提前提醒。

从 AiUE 侧的长期演进看，`motion` 其实也非常适合进入 canonical warehouse，因为后续我们会逐步需要：

- motion 发现与索引
- motion 元数据
- 角色/骨骼兼容性信息
- 动作预览、证据包与后续自动化质量线

当前 toy-yard 看起来还没有为 motion export 做明显准备，这一轮完全不要求马上补齐，但建议尽早确认：

- motion 是否计划进入 toy-yard canonical warehouse
- 如果进入，是否准备提供独立的 motion export contract / summary / index

如果这件事越晚才开始，后面 character / weapon / clothing 路径已经稳定后，再补 motion contract 的成本会更高。

## 我们建议的修复优先级

建议顺序如下：

1. 先修 manifest 的 `output_fbx / textures` 可迁移路径
2. 再补 registry 的 character / weapon mesh 引用
3. 再补 slot / attach 元数据
4. 最后补 contract version、artifact mapping、normalized naming 等增强项

## 当前试跑反馈摘要

- `trial-cassia-solo`
  - manifest 可读
  - import 失败
  - 第一处失败：`output_fbx` 无法在当前机器解析到真实导出工件
- `trial-yidhari-bundle`
  - summary / registry 可读
  - refresh-assets 已真实执行并 `pass`
  - 但 runtime-ready mesh / attach 信息仍不足

如果需要，我们也可以下一轮直接配合做一次：

- “最小可迁移 export contract” 对齐
- 或 “runtime-ready registry contract” 对齐

这样我们可以尽快进入下一个节点：

- `T2: AiUE uses toy-yard exports as the default PMX source for new runs`
