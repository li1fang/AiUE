# 邮件草稿

## 主题

AiUE motion seam v0 对齐建议：先定 consumer boundary 与 result contract，再继续 `M0.5` shadow trial

## 正文

各位同学：

我们这边基于最近一轮 `toy-yard motion packet` 真实试跑，先做了一个判断：

motion 这条线现在最需要的，不是继续在模糊边界上多跑几轮，而是先把 `toy-yard <-> AiUE` 的 consumer seam 写清楚。

原因是：

- toy-yard 侧的 packet / self-check / communication signal 已经基本成型
- AiUE 侧也已经开始出现真实的 `import-motion-packet` 消费实现
- 接下来遇到的问题会越来越集中在 consumer execution，而不是 warehouse export

如果这时候不先把 seam 钉住，后面每多跑一轮，双方对边界、失败归属、结果回流的理解都更容易漂。

所以我们的建议是：

1. 先对齐 `motion consumer seam v0`
2. 再继续 `M0.5 Motion Shadow Packet Trial`
3. shadow trial 结束后，再根据真实结果决定 producer contract 是否需要继续调整

我们这边这次整理出的 v0 判断如下。

### 边界建议

`toy-yard` 继续负责：

- canonical warehouse
- packet export
- catalog / lineage / evidence
- packet self-check
- packet-side communication signal
- result import contract

`AiUE` 负责：

- packet consumption
- 可选 `bvh -> fbx` 转换
- target skeleton / host resolution
- Unreal import / retarget / preview / runtime validation
- consumer-side communication signal
- machine-readable consumer result

### 我们建议先固定的 seam v0

producer-facing 输入仍然是现有 portable motion packet：

- `summary/motion_suite_summary.json`
- `summary/motion_clip_registry.json`
- `summary/motion_packet_check.json`
- `summary/communication_signal.json`
- `clips/*/manifest.json`

AiUE consumer v0 先只支持这 3 个 operation：

- `import_motion_packet`
- `retarget_preflight`
- `animation_preview`

并且 AiUE 侧会把消费结果写成 machine-readable result，至少明确：

- 哪个 packet 被消费了
- 执行了哪个 operation
- pass / fail
- 问题归属是 `toy-yard`、`aiue` 还是 `none`
- 产出了哪些 Unreal asset / preview evidence

### 我们对当前沟通时机的建议

我们倾向于现在就同步这份 seam v0，而不是等到“motion 全验证完”再沟通。

因为目前更大的风险不是多一个失败样本，而是双方边界在实现过程中默默漂移。

当然，这份 v0 不是要求你们立刻为了 AiUE 改很多 producer 结构。

它的目的更像是：

- 先把边界和期望结果形状钉住
- 再让下一轮 shadow trial 在同一套 contract 上暴露真实问题

如果你们认同，我们建议下一步就按这条顺序推进：

1. 双方先对齐 seam v0
2. AiUE 继续做 `M0.5` shadow consumer 试跑
3. 试跑后再判断：
   - producer contract 是否需要补字段
   - result import contract 是否需要细化
   - 是否进入更正式的 motion handoff round

谢谢。

## 附件建议

- `ADR-0011-motion-consumer-seam-v0.md`
- `motion_consumer_request_v0.schema.json`
- `motion_consumer_result_v0.schema.json`
- `motion_consumer_request_v0.example.json`
- `motion_consumer_result_v0.example.json`
