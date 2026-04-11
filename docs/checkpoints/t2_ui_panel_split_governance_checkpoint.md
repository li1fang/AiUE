# T2 UI Panel Split Governance Checkpoint

## Summary

这一轮是一次定点治理 checkpoint，目标不是新增能力，而是给 `T2` workbench 的主窗口降压。

固定切口：

- 把 `ui.py` 从“大一统窗口脚本”拆回 `window orchestrator`
- 抽出可持续增长的 panel 模块：
  - `ui_sections.py`
  - `ui_demo.py`
- 保持 `WorkbenchWindow` 的外部接口、对象名和测试行为不变

## Why Now

`Dynamic Balance` 已经把 `tools/t2/python/aiue_t2/ui.py` 识别成连续多轮被触碰的热点。

如果继续把：

- report/details
- image/metrics
- slot debugger
- demo session
- demo request

都叠在一个主窗口类里，那么后续 `E2 / T2.1 / Q5` 相关演进还会不断挤回同一个文件。

这轮先把窗口主类退回到：

- 入口装配
- 状态切换
- 选择事件
- 调度各 panel 渲染

## Structural Outcome

拆分后结构变成：

- `ui.py`
  - `WorkbenchWindow`
  - 顶层工具栏、状态装配、事件调度
- `ui_sections.py`
  - `SummaryCard`
  - `DetailsPanel`
  - `ImagesPanel`
  - `SlotDebuggerPanel`
- `ui_demo.py`
  - `DemoRequestControlState`
  - `DemoSessionPanel`
  - `DemoRequestPanel`

治理结果：

- `ui.py` 从约 `1017` 行下降到约 `623` 行
- 对外仍然保持：
  - `aiue_t2.ui.WorkbenchWindow`
  - 现有 object names
  - 现有测试访问路径

## Verification

本轮至少完成：

- `powershell -NoProfile -ExecutionPolicy Bypass -File C:\AiUE\tools\run_t2_workbench_tests.ps1 -SkipPrepareLatestPack -SkipSoak`
- `C:\AiUE\.venv-tooling\Scripts\python.exe -m pytest tests\t2\test_ui.py -q`

预期结果：

- T2 结构测试继续通过
- `WorkbenchWindow` 现有测试访问字段不回归
- demo session / demo request / governance balance 仍可在窗口中读取

## Follow-Up

这一轮只做 `T2 ui.py` 降压，不主动拆 `state.py`。

下一轮如果继续治理，优先级建议是：

1. 观察 `Dynamic Balance` 是否仍把 `ui.py` 或新 panel 文件列为连续热点
2. 如果 `ui` 热点缓解，再评估是否进入 `state.py` 的定点拆分
3. 如果热点缓解且主线保持绿，再回到内容推进
