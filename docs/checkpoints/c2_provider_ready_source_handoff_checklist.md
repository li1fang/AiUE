# C2 Provider-Ready Source Handoff Checklist

## 这份清单回答什么

这份清单不回答“最终 C2 成品是否已经完成”。

它回答的是更前面的一个问题：

`这个 Houdini handoff 包，是否已经足够合格，能够让 AiUE 派生出 BodyPaint 可消费的 provider-ready source handoff？`

换句话说，这一阶段的目标是：

- `status = ready`
- `consumer_hints.ready_for_bodypaint = true`

而不是：

- 最终 runtime-ready 角色
- BodyPaint 分割完成
- AutoHoudini 次级运动烘焙完成

## 目标产物

一个合格的 handoff 包，至少应让 AiUE 最终产出：

- [latest_canonical_fusion_fixture_c2_report.json](C:/AiUE/Saved/verification/latest_canonical_fusion_fixture_c2_report.json)
- [converted_model_provider_v0_1.json](C:/AiUE/Saved/body_platform/c2/latest/converted_model_provider_v0_1.json)

并满足：

- `latest_canonical_fusion_fixture_c2_report.status = pass`
- `converted_model_provider_v0_1.status = ready`
- `converted_model_provider_v0_1.consumer_hints.ready_for_bodypaint = true`

## 包级最小必需项

下面这些项，是当前第一份 provider-ready source handoff 的最小闭环：

1. `canonical_fusion_fixture_manifest.json` 存在
2. `fixture_id` 存在且稳定
3. `body_family_id` 存在且稳定
4. `fixture_scope` 存在且属于当前允许集合
   当前允许：
   - `lower_body_core`
   - `full_body`
   - `canonical_fused_body`
5. `source_module_ids` 至少有 1 个
6. `primary_mesh_relative_path` 能解析到真实 mesh 文件
7. `exporter.tool = houdini`
8. `coordinate_system.linear_unit = cm`
9. `coordinate_system.up_axis = z`
10. `fusion_recipe_id` 存在且稳定

## 推荐目录布局

```text
<fixture_root>/
  canonical_fusion_fixture_manifest.json
  meshes/
    lower_body_core_hi.fbx
  materials/
```

如果暂时没有贴图：

- `materials/` 可以为空
- 但 manifest 里应明确写出当前材料/贴图状态

## 推荐 manifest 模板

直接参考：

- [canonical_fusion_fixture_manifest.example.json](C:/AiUE/examples/body_platform/canonical_fusion_fixture_manifest.example.json)
- [canonical_fusion_fixture_manifest.v0.schema.json](C:/AiUE/schemas/canonical_fusion_fixture_manifest.v0.schema.json)

## 自检顺序

建议先跑包级自检，再跑完整 AiUE gate。

### 第一步：包级自检

运行：

- [run_check_c2_provider_ready_source_handoff.ps1](C:/AiUE/run_check_c2_provider_ready_source_handoff.ps1)

建议示例：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\run_check_c2_provider_ready_source_handoff.ps1 `
  -WorkspaceConfig C:\AiUE\local\pipeline_workspace.local.json `
  -FixtureZip C:\Users\garro\Downloads\scan-model-hi.zip
```

通过条件：

- `status = pass`
- `provider_preview.status = ready`
- `provider_preview.consumer_hints.ready_for_bodypaint = true`

### 第二步：完整 AiUE gate

运行：

- [run_canonical_fusion_fixture_c2.ps1](C:/AiUE/run_canonical_fusion_fixture_c2.ps1)

它会继续检查更完整的 AiUE 上下文，而不只是包本身。

## 当前真实 zip 暴露过的失败类型

如果 handoff 包没有补齐，当前最常见的失败就是这些：

- `c2_manifest_missing`
- `c2_primary_mesh_missing`
- `c2_fixture_id_missing`
- `c2_body_family_missing`
- `c2_fixture_scope_missing`
- `c2_fixture_scope_invalid`
- `c2_source_module_ids_missing`
- `c2_exporter_not_houdini`
- `c2_linear_unit_invalid`
- `c2_up_axis_invalid`
- `c2_fusion_recipe_missing`

## 边界提醒

AiUE 在这个阶段负责的是：

- converted model facts
- provenance
- package identity
- package readiness

AiUE 不负责在 provider 里暴露：

- `resolved_axes`
- `regions`
- `paint_strategy`
- `manual_overrides`

这些继续属于 BodyPaint 域内语义。
