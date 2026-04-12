# toy-yard Export Contract 调整清单

更新时间：2026-04-12

## 本轮试跑结论

AiUE 已完成这两项接线：

- `validate-package` 已接入 AiUE host bridge / Unreal host runtime
- `refresh-assets` 已接入 AiUE host bridge / Unreal host runtime

基于以下 trial packet 试跑：

- `C:\Projects\toy-yard\_reports\aiue_t1_trial_packet.md`
- `C:\AiUE\local\pipeline_workspace.toyyard.trial-cassia-solo.local.json`
- `C:\AiUE\local\pipeline_workspace.toyyard.trial-yidhari-bundle.local.json`

当前真实状态：

- `trial-cassia-solo`
  - `summary / manifest` 可直接从 toy-yard export 解析
  - `import-package` 仍失败
  - 第一处失败是 manifest 内 `output_fbx` 无法在当前机器解析到真实导出工件
  - `validate-package` 不再是 unsupported，现已正确报告 `ue_import_report.local.json / ue_validation_report.local.json` 缺失
- `trial-yidhari-bundle`
  - `summary / registry` 可直接从 toy-yard export 解析
  - `refresh-assets` 已真实执行并 `pass`
  - AiUE 能基于 toy-yard 的 `summary + registry` 创建 pair/loadout/component/host 资产
  - 但当前 registry 仍缺少 runtime-ready 所需的 mesh / attach 细节，因此结果仍是“资产刷新可跑通，但 runtime 可消费度不足”

这说明：

- toy-yard export 已经足够支撑 `summary / registry / manifest` 发现与读取
- AiUE 不需要回退 toy-yard SQLite
- AiUE 不需要回退原始 `3dgirls` 目录做包发现
- 但 toy-yard export contract 还不够“自包含 + runtime-ready”

## 必改项

### 1. Manifest 必须改成可迁移、自包含的 artifact 路径

当前 `trial-cassia-solo` 的 manifest 里：

- `output_fbx` 仍指向源机器绝对路径
  - 例如：`C:\Users\fang\Documents\3dgirls\_fbx_out_fastloop\...`
- `source_file` 也仍指向源机器绝对路径
  - 例如：`C:\Users\fang\Documents\3dgirls\mingchao\...`

这会直接导致：

- AiUE 在当前机器找不到 `output_fbx`
- `import-package` 无法开始
- 后续 `validate-package` 也只能报告 import/validation report 缺失

建议固定为：

- `output_fbx` 指向 export root 内真实落盘的 FBX
  - 可接受形式：
    - export-root 相对路径
    - export-root 内绝对路径
- `textures[*].relocated_path` 同样必须指向 export root 内真实存在的文件
- `source_file` 可以保留为溯源证据，但不应再被当前机器上的导入流程依赖
- 建议新增更明确的字段：
  - `export_artifacts.output_fbx`
  - `export_artifacts.textures[*].path`
  - `export_root_relative_path`

最低要求是：

- 只凭 toy-yard export 目录本身，AiUE 就能定位 FBX 和纹理，不依赖源机器路径

### 2. Registry 必须补齐 runtime-ready 的 mesh 引用

当前 `refresh-assets` 已经能消费：

- `summary\ue_suite_summary.json`
- `summary\ue_equipment_registry.json`

但生成出来的 loadout / host 仍显示：

- `character_skeletal_mesh = ""`
- `default_weapon_skeletal_mesh = ""`
- `weapon_mesh_paths = []`
- `runtime_ready_host_blueprints = 0`
- `loadout_missing_character_or_slot_binding_mesh`

这说明 registry 目前只有 package/bundle 级关系，还缺少 runtime 真正要消费的 UE 资产引用。

建议补齐这些字段：

- `characters[*].skeletal_mesh`
- `characters[*].skeleton`
- `characters[*].physics_asset`
- `ready_pairs[*].weapon_skeletal_mesh`
- 如果未来支持 static mesh，也建议预留：
  - `ready_pairs[*].weapon_static_mesh`

最低要求是：

- character entry 能告诉 AiUE “主角色 mesh 是谁”
- ready pair 能告诉 AiUE “默认武器 mesh 是谁”

### 3. Registry 应显式给出 slot / attach 元数据

当前 `refresh-assets` 虽然自动补出了默认 `weapon` slot，但 attach 证据仍然偏弱：

- `equip_slot = null`
- `preferred_attach_target = null`
- runtime 结果里 `resolved_attach_socket_name = "None"`

建议 toy-yard export 在 pair 或 binding 层显式提供：

- `equip_slot`
  - 当前 weapon bundle 固定可给 `weapon`
- `preferred_attach_target`
  - 建议至少包含：
    - `type`
    - `name`
- 或直接提供：
  - `attach_socket_name`

最低要求是：

- 不让 AiUE 在 bundle trial 里只能靠 `WeaponSocket` 默认猜测

### 4. Export contract 需要明确版本号

建议在以下文件中都增加明确版本字段：

- `manifest.json`
- `ue_suite_summary.json`
- `ue_equipment_registry.json`

建议字段：

- `export_contract_version`
- `exporter_version`
- `source = "toy-yard export"`

这样 AiUE 侧可以更稳定地区分：

- 历史 trial export
- 新版可迁移 export
- 未来 runtime-ready export

## 建议项

### 5. Registry 补一层 package -> exported artifact 映射

如果 toy-yard 能在 summary/registry 层直接给出：

- package 对应 manifest 路径
- package 对应导出 FBX 路径
- package 对应 textures 根目录

那 AiUE 在后续做批量 import / refresh / validate 时会更稳，不需要再次扫 conversion 目录。

### 6. 保留 source lineage，但不要让它参与当前机器解析

当前 export 的 lineage 已经很有价值，但建议分层：

- `source_*` 字段：只做溯源
- `export_artifacts.*` 字段：只做当前机器消费

这样可以同时满足：

- lineage 可追踪
- export 可搬运
- AiUE 可直接消费

### 7. 统一文本编码与显示字段

当前部分源文件路径在当前环境输出时出现乱码样式。

这不一定是 contract blocker，但建议额外补一个稳定字段：

- `display_name_ascii`
- 或 `normalized_display_name`

这样跨环境日志更容易读。

### 8. 提前规划 motion 资产是否进入 toy-yard canonical warehouse

这不是本轮 PMX trial 的直接 blocker，但值得现在就提醒。

从 AiUE 侧看，`motion` 也是一种非常适合仓库化的资产类型，因为后续我们会越来越需要：

- 动作发现
- 动作元数据
- 动作与角色/骨骼兼容性
- 动作预览与证据回放

当前 toy-yard export 还没有为 motion 做明显准备，这轮完全可以不强推，但建议尽早回答两个问题：

- toy-yard 是否准备把 motion 也纳入 canonical warehouse
- 如果纳入，是否会提供一套独立的 motion export contract 和 summary/index

这项目前不是必须修改，但属于“越早定边界越省后账”的事项。

## 当前对 toy-yard export contract 的评价

当前评价：`勉强可用，但仍需调整`

原因：

- 读取层已经可用
- `refresh-assets` 已经跑通
- 但 `import-package` 仍被非迁移式 artifact 路径阻断
- `registry` 还未达到 runtime-ready 所需的信息密度

## 建议的修复优先级

1. 先修 manifest 的 `output_fbx / textures` 可迁移路径
2. 再补 registry 的 `character / weapon` mesh 引用
3. 再补 `equip_slot / attach target`
4. 最后补 `contract version / artifact mapping / display name` 这些增强字段

## 本轮 AiUE 侧试跑反馈摘要

- 使用 workspace config：
  - `C:\AiUE\local\pipeline_workspace.toyyard.trial-cassia-solo.local.json`
  - `C:\AiUE\local\pipeline_workspace.toyyard.trial-yidhari-bundle.local.json`
- 执行命令：
  - `run_import_package.cmd`
  - `run_validate_package.cmd`
  - `run_refresh_assets.cmd`
- 首个失败点：
  - `trial-cassia-solo` 的 manifest `output_fbx` 不可迁移
- 是否回退 toy-yard SQLite：
  - 否
- 是否回退原始 `3dgirls` 做包发现：
  - 否
