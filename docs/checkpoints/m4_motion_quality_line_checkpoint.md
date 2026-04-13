# M4 Motion Quality Line

`M4` 不再回答 “能不能跑”，而是回答：

`当前这条 motion 路径，是否已经表现出足够可信的 retarget / preview / native pose quality。`

固定站位：

- 前置：`M3.5 = pass`
- 证据来源：现有 `M2.5` package result + `animation_preview.action.json`
- 不重新拉起 Unreal

固定质量关注点：

- resolved animation compatibility 必须为真
- retarget generation 必须成功
- 关键链条覆盖至少包含：
  - `root`
  - `Spine`
  - `LeftClavicle`
  - `RightClavicle`
  - `LeftArm`
  - `RightArm`
- native pose evaluation 必须成功并且真的产生动作变化
- changed bone count 和 native location delta 不能低到近似“假动作”
- 只允许当前已知的低风险 warning：
  - `animation_blueprint_library_unavailable`

默认 runner：

- [run_motion_quality_line_m4.ps1](/C:/AiUE/run_motion_quality_line_m4.ps1)
- [run_motion_quality_line_m4.py](/C:/AiUE/workflows/pmx_pipeline/run_motion_quality_line_m4.py)

最新报告：

- `Saved/verification/latest_motion_quality_line_m4_report.json`

`M4 = pass` 的含义是：

- 当前 motion 线不仅可执行
- 它已经开始具备“可复用的平台质量证据”
