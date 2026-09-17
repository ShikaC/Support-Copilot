# 质量输入与参考标准离线审计

**已完成离线切片，人工确认与新模型测量尚未完成。** 在保留旧 run-1 和现有未提交改动的前提下，先保存评分/筛选协议，再固定新候选，完成上下文投影、参考跨度核对、逐题 AI 审计、开发/保留集合划分和离线故障验证。本轮没有模型或 Embedding 调用，没有新的业务表现分数。

基础 HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty；无提交、推送、部署或业务服务重启。工作区保护记录为 [workspace-before.json](workspace-before.json)。当前证据由 [freeze-manifest.json](freeze-manifest.json) 的数据/脚本摘要及 [verification.json](verification.json) 的命令、退出码与结果绑定，不能仅凭 HEAD 相同推定源码相同。

## 数据结果与产物

| 来源 | 候选 | DIRECT | CLARIFY | OUT_OF_KB | 排除 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Doc2Dial 人工构建对话 | 24 | 11 | 12 | 0 | 1 |
| 真实 GitHub issue 问题片段，跨产品负对照 | 4 | 0 | 0 | 3 | 1 |

上表是 **AI 审计建议的标签数量，不是回答正确数量**。Doc2Dial 纳入的 development 有 11 题（5 DIRECT、6 CLARIFY），holdout 有 12 题（6 DIRECT、6 CLARIFY）。公开 issue 负对照 development 2 题、holdout 1 题。独立机器可读摘要见 [data-summary.json](data-summary.json)；两类数据不得混为一个质量分数。

- [PROTOCOL.md](PROTOCOL.md)：抽样前保存的纳入/排除、评分分母、失败计分、预算和停止条件。
- [AMENDMENT-1.md](AMENDMENT-1.md)：审计发现 DMV 不能映射为 Virginia 后，在任何模型调用前记录的修订；原协议、原始候选和抽样顺序均保留。
- [selection.json](selection.json)：661 段 test 对话的完整筛选清单，以及此前 48 个公开 issue 候选的选择状态；没有按模型输出选题，不合格不递补。
- [candidate-inputs.json](candidate-inputs.json)：原始候选准备记录，含错误 DMV 路由，仅供追溯，禁止送模型。
- [cases.json](cases.json)：修正后的输入、发布者原标注、AI 修订理由、必要要点/补问槽位、禁止推断和逐字证据；26 个纳入候选、2 个排除项均保留。
- [inputs-development.json](inputs-development.json) / [inputs-holdout.json](inputs-holdout.json)：仅 ID 和工单 subject/description 的白名单投影。文件存在不代表允许马上运行；新 runner 与人工确认前置条件尚未满足。
- [REVIEW.md](REVIEW.md)：可直接阅读的全部 28 题输入与参考对照；[human-review-template.json](human-review-template.json) 供复制到独立文件做真人审核，当前全部 NOT_REVIEWED。
- [source-excerpts.json](source-excerpts.json)：所选完整原始对话和文档，离线参考专用；[public-source-capture.json](public-source-capture.json) 保存本次只读获取的 issue 正文和摘要。目标及未来回合没有进入输入。
- [old-input-diagnosis.json](old-input-diagnosis.json)：旧寒暄、地址修改和证件问题的具体诊断，保留旧参考和旧回复；不重新计分、不挪入新集合。

## 本轮改动为何放在评测层

旧 `prepare-doc2dial.mjs:44–55` 只取首个 user/agent 对，没有业务意图或上下文合格门禁。原 `metrics.mjs` 的词语 F1、跨度覆盖依然是代理指标，原 `summarize-business.mjs` 没有事实蕴含判定。此时改模型或用代理分数选方案，会把输入/标签错误当成系统错误。

新流程为：源归档/hash → 完整候选池与固定抽样 → 原始对话前缀 → AI 审核标签和原文必要要点 → 输入白名单投影 → 离线验证 → 待作者审阅。只增加独立 MJS 准备/核对工具和数据，不改生产 Java/Python、UI、旧指标函数、超时配置或旧 runner。

关键修复及建议的 diff 审阅顺序：

1. **机构信息不能猜。** 候选 `qa-c133078c0b8c5805ef25afedc6cb96e9-5` 问在线支付驾驶罚款；来源提及纽约，但用户没有州别。初版协议误填 Virginia 已被本轮审计纠正，现为 DMV 未知辖区 + CLARIFY，不把金标准信息泄漏给模型。
2. **末句短不等于没有业务问题。** `qa-6dc95d6948e2ade445cac0a7cca977b0-4` 末句只有 Yes，但原对话已明确 IDR 年度收入认证；保留完整前缀后可直接回答，必要要点对应 span 25。相反，旧 Hi there 没有这样的前文，不应被赋予证件办理准确率标签。
3. **参考回复不完整时修参考。** `qa-28b3c8e7d96670a365f5f41711a427c2-4` 问两项要求，发布者只问了第一项；现将疾病条件、发病时间和资格背景分别回指 span 6、8、4/10。`qa-9a1702284047fab39b63adf51be38528-4` 的申诉步骤补入原参考遗漏的时限和提交对象。这些是归档文本评估，不是当前医疗/法律建议。
4. **保留不合格题。** `qa-4db57972397af5cd2521167ba8fb5b2f-4` 的 down payment 与 discharge 语义冲突，排除而不悄悄改写；[issue #2661](https://github.com/cli/cli/issues/2661) 正文已写解决方案，同样排除。不挑替代题填满配额。

审阅重点是三分类是否合理、必要要点是否完整、补问是否有针对性及其适用条件。尤其 MyDMV 是否足以唯一识别州别、一般规则回答与个案补问的分界，需要真人确认。这里的保守 AI 分类不是最终 gold；若改标，另建版本并记录变更，不能覆盖冻结输入后继续沿用原摘要。

## 来源与独立性

Doc2Dial 使用原业务报告绑定的官方 v1.0.1 归档；原始 zip、doc/test JSON 摘要本轮再次核对。它不是企业真实客服日志，领域是公共服务，不是默认 SaaS 工单场景。保留完整历史对话，统一提供机构级实验路由；只知道目标标注的人才能补出的个人事实不进入输入。全部 488 文档仍使用旧 corpus，未做按答案切块或答案专用索引。

旧 32 题所在对话与参考文档排除；还校验去除版本后缀的文档标题、规范化全文、唯一输入及跨 split 词集合近重复（Jaccard 阈值 0.65）。阈值以上候选为 0，代码点/文本检查通过；这不能证明不存在更宽泛的语义重叠或模型预训练污染。holdout 只接受了本轮标签审计，尚未送项目模型；它不是对当前 AI 协作者完全不可见的双盲集合。

公开负对照来自 [#695](https://github.com/cli/cli/issues/695)、[#1466](https://github.com/cli/cli/issues/1466)、[#110](https://github.com/cli/cli/issues/110)；问题涉及 PowerShell 补全、fork 选择、Linux 源码构建。四个源正文摘要均与旧采集候选清单匹配；它们未在旧 20 题生成实验中使用，但此前已出现在采集池，不能称为从未看过。原文已给答案的 #2661 排除。负对照的 OUT_OF_KB 是相对 Doc2Dial corpus 的产品边界判断，不是由“没有 reference”推得；全文中一个 github 命中是法律援助网页链接，不是 GitHub CLI 使用说明。跨产品拒答比较容易，不能代表领域内无答案检测能力。

## 验证与失败路径

从项目根目录执行，均不调用外部模型：

```bash
node --test scripts/benchmark/quality-input-contract.test.mjs scripts/benchmark/metrics.test.mjs
node scripts/benchmark/verify-quality-inputs.mjs
node scripts/benchmark/verify-quality-inputs.mjs --require-human
```

实际结果：15 个测试通过、0 失败、0 跳过；离线完整性检查 exit 0；require-human exit 2，按预期拒绝将未人工确认的材料当成可发布 gold。日志和命令退出码见 [verification.json](verification.json)。没有运行全仓测试，因为本轮未改业务/界面执行路径，也没有本轮全仓通过结论。

故障验证覆盖：目标答案/标注字段混入输入、跨度坐标错位、必要要点缺证据、补问缺少具体槽位、寒暄替换业务输入、无依据标 OUT_OF_KB、将 AI 状态改成人工通过、把 HTTP/持久化/fallback 算正常 live、覆盖冻结文件。最终 builder 在自有临时目录中生成六个派生产物，与冻结产物逐字节一致；临时测试目录已清理。校验器机械拒绝的是不符合已审计契约的变化，不会自动判断任意新句子的语义可答性。

旧证据核对：三个报告摘要、原始源文件、157 份运行源码快照匹配；现存 Java JAR 与旧运行清单摘要匹配。当前运行源码差异仅为旧报告已记录的两个 Python 实验模块。旧 96 条 case/concurrency 配对完整，本轮对保留的即时历史响应做完整对象比对均匹配；重启记录只保留 ID/traceId/mode/回复正文四字段匹配结果，不能据此扩写成全部字段重启后逐项核验。旧模型结果和分数均未重写，原始实验事实继续以[旧业务报告](../business-benchmark-2026-09-10/README.md)为准。

## 剩余工作与下一切片门槛

- **待真人确认**：全部输入忠实度、DIRECT/CLARIFY/OOK 标签、修订后的要点和排除理由；本轮没有冒充作者已理解或已审阅 diff。
- **未测**：新题检索质量、回答事实支持、完成请求比例、补问质量、超时/持久化表现，以及客户解决率、节省工时和完整费用。
- **调用前必须实现**：新 runner 的实验 ID、目录、端口和数据库隔离；它不能直接复用旧固定 run-1。先验证现有完整 corpus 的 artifact 可复用，预检失败不自动发起文档 Embedding。
- **下一轮上限**：本次实际 development 为 13 个纳入题，可安排单并发、每题一次的至多 13 次分析；协议硬上限14。按 Java 最多两次服务尝试估算，至多26次 query Embedding/26次生成，实际逐次记账；SDK20s/Python90s/Java105s/客户端130s，总批次35分钟。连续3次依赖失败、身份/配额故障、hash/trace异常或未知错误即停，保留全部计划/未执行/失败行。不复跑选优；holdout 为0。此处仅记录计划，本轮不会自动进入真实测量。
- 质量页仍读取此前22题报告；本轮未接页面。下一步先完成人审和运行隔离，再做真实测量，随后才考虑接入质量页或比较检索改进。

## 简历事实边界

可以陈述：在已有公开数据业务基准上，设计并实现可追溯的评测输入审计，保留对话上下文、隔离答案标注、区分可答/补问/知识库外样本，建立独立开发与保留集合、跨度校验、冻结摘要和失败保护测试。已有跨 Java/Python live、延迟/降级和持久化实验仍可按旧报告的限定范围引用。

不能陈述：新数据已完成人工 gold、新题回答准确率已达某值、修复使模型回答质量提升、真实客户问题解决率、节省工时或生产容量。本轮完成的是让下一轮测量的输入与判定过程可审阅，而非取得了新的模型成绩。
