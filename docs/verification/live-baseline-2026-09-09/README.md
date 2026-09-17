# 真实 AI 质量基线：机器通过，语义问题与人工审核仍未闭环

2026-09-09。已完成真实聊天与 Embedding 调用、两项根因修复、原始回归集复测、16例扩展集连续两轮最终评估，以及233项Python回归。最终两轮各有13个live成功、3个预期无证据降级，机器门禁各16/16通过。**当前 publishable=false，人工审核0/32；自动语义复核已发现至少一项退款时效政策冲突，不能称为生产级质量通过。**

用户本轮明确授权真实AI基线。仅使用合成工单和仓库知识；没有处理真实客户数据、发送客户消息或切换现有demo预览为live。基础HEAD为`4df3bf44907c34318132496929bad4a3974ad88b`，master，工作树dirty，保留此前所有改动，未提交/推送/部署。

## 基线结果

同一16例运行两轮，共32次分析；这不是32个独立案例。有证据13例包含账号、账务、发票、导出、套餐、隐私、同步故障，另有3例无证据、2例越权指令、1例英文输入（子集重叠）。数据集在首次运行前冻结，未为通过修改答案。协议见[PROTOCOL.md](PROTOCOL.md)，机器汇总见[baseline-summary.json](baseline-summary.json)。

| 指标 | final-1 | final-2 |
| --- | --- | --- |
| 有证据的live生成成功 | 13/13 | 13/13 |
| 真正VECTOR检索Recall@3（有证据样本） | 13/13 | 13/13 |
| 真正VECTOR MRR（有证据样本） | 0.9615 | 0.9615 |
| 业务分类正确 | 13/13 | 13/13 |
| 升级判断符合预期 | 16/16 | 16/16 |
| 引用ID关系检查 | 16/16 | 16/16 |
| 无证据安全降级 | 3/3 | 3/3 |
| 全部案例平均runner耗时 | 6910 ms | 6883 ms |
| 全部案例中位耗时 | 7649.5 ms | 7303 ms |
| nearest-rank p95 | 10590 ms | 16286 ms |
| 可用聊天输入/输出token | 9046 / 4036 | 9046 / 4149 |
| 人工事实审核 | 0/16 | 0/16 |
| 可发布质量结论 | false | false |

p95按`ceil(0.95*n)-1`计算，16个样本时为最大值。原始报告旧rounded-index算法对应10089/11050ms，均保留但不能混用。平均耗时包括无需聊天生成的3个降级案例，不是纯模型时延或并发SLO。向量指标从`live_retrieval`计算；原始summary的检索指标来自最终响应，异常fallback可能采用本地检索，不用于纯向量质量结论。

当前配置：gpt-5.6-luna经配置中的兼容网关，chat_completions；Qwen/Qwen3-Embedding-0.6B经配置中的Embedding供应方，1024维。报告保留配置提供方身份与模型标识，这不独立证明网关内部实际路由。沿用topN10/topK3/阈值0.35/外部超时20秒/整体90秒/零SDK重试。费用未核算：聊天网关实际单价未确认，Embedding与失败请求费用不可得；26,277个token仅为最终两轮已返回的聊天用量，不包括前期诊断、Embedding或失败请求。

## 确认并修复的根因

1. **Embedding输入协议不兼容。** LangChain默认将文本转换为OpenAI token编号，再交给Qwen接口。HTTP200不能证明输入语义正确。同10片段/3查询对照，旧路径top1为0/3，原文输入为3/3。`app/embedding_provider.py`现发送原始文本。新artifact加入`raw-text-v1`输入格式并参与身份，拒绝旧格式，重建并激活新索引；旧目录保留。见[Embedding证据](embedding/REPORT.md)。[LangChain官方说明](https://reference.langchain.com/python/langchain-openai/embeddings/base/OpenAIEmbeddings/check_embedding_ctx_length)说明该开关如何避免非OpenAI服务的tokenization问题。
2. **自由分类绕过业务风险策略。** 原模型输出ACCOUNT、BILLING_REFUND和中文类别，后端只识别固定类别，造成漏升级。外部结构化输出现使用产品已有类别枚举，并在响应边界拒绝未知类别；mock本地策略保持兼容。未降低分类或升级标准。
3. **评估器完成与质量门禁混淆。** 正确的无证据降级不再触发CLI失败；PARTIAL/UNSUPPORTED人工标签不能发布；报告核验绑定完整案例集、检索/引用预期与实际分类升级。保留实际live检索，避免被本地fallback覆盖。见[评估器复审](evaluation-integrity/FINAL-REVIEW.md)。

## 保留的失败与待处理问题

| 阶段 | 真实结果 | 解释 |
| --- | --- | --- |
| 原始4例，修复前 | 1 live成功 + 3 invalid_model_response | 与历史失败签名相同；并非4例全部失败 |
| 原始4例，重建索引后 | 3 live成功 + 1 invalid_model_response | 原始未知硬件案例仍召回弱相关证据，模型空引用被归为结构化失败；此残余未被最终扩展集替代或抹去 |
| 扩展16例，类别约束前run-1 | 12 live + 1生成超时 + 3预期降级；分类5/13，升级11/16 | 明确暴露类别契约缺口与超时 |
| 扩展16例，类别约束前run-2 | 13 live + 3预期降级；分类5/13，升级14/16 | 仅接口成功不足以说明业务正确 |
| 最终两轮 | 机器各16/16通过，人工仍0/32 | 机器门禁尚未覆盖全部语义与体验要求 |

自动语义复核发现：

- **明确政策冲突：final-1 / quality-billing-injection**，在交易尚未核验时引用“3至7个工作日”退款时效。知识片段明确禁止核验前引用，条件措辞不能解除该限制。final-2同例没有引用时效。不能声称两轮回复政策安全100%。
- **人工判断项：final-1 / quality-sync**，增加“不经过公司代理是否可复现”的排查建议，超出所引用片段只要求收集版本与代理配置的范围。
- **语言体验缺口：两轮quality-sso-english**，英文问题得到中文回复。当前机器标准未包含语言匹配，后续应增加明确语言期望。

下一步先对照[人工审核材料](REVIEW.md)逐条判定事实支持与可用性，优先处理退款时效冲突；然后将已确认错误作为新版本回归要求，另用未参与调优的数据验收。不能通过把原失败案例换掉、放宽门禁或由AI填入人工SUPPORTED宣告完成。

## 验证、源码与复现

在`services/support-copilot-ai`目录：

```bash
.venv/bin/pytest -q
.venv/bin/python -m evaluation.run_mock_evaluation
.venv/bin/python -m evaluation.run_live_evaluation --dataset evaluation/data/live-quality-v1.json --report-dir ../../docs/verification/live-baseline-2026-09-09/repeat-new
.venv/bin/python -m evaluation.verify_live_evaluation --report ../../docs/verification/live-baseline-2026-09-09/final-1/live-latest.json --dataset evaluation/data/live-quality-v1.json
```

第三条会产生新的真实API调用。复跑需保留当前`.env`配置和兼容的active artifact。最终两轮原始报告各自通过provenance/integrity verifier；加`--require-human`当前应失败。报告正文、评审worksheet、manifest与日志均保留在本目录。

- 全量Python233通过；mock31案例通过；修改文件Ruff通过；新类别契约先3项失败再通过，原Embedding/评估器同样保留红绿证据。
- 类型检查分范围记录：新model/observer与评估门禁专项0错误/4告警（类属性与override标注），见`types-final-scoped.log`。早期广范围检查仍发现既有runner别名构造/返回联合类型及provider可选配置等类型欠账，不将专项结果宣称为全服务严格类型通过。
- 两轮live运行绑定[source-manifest.json](source-manifest.json)中的冻结源码。运行结束后仅整理5个import块，并把外部类别Literal覆盖改为相同JSON枚举+字段校验以解决可变属性类型覆盖问题；发送模型的完整JSON Schema与[model-schema.json](model-schema.json)逐项相等，233项测试重新通过。最终工作树另见`delivery-source-manifest.json`，不冒充两份源码字节完全相同。
- 人工审核材料列出两轮全部32条回复和引用。worksheet绑定原报告SHA，填写后使用既有`evaluation.live_review apply`生成新报告，原报告保持不变；人审不支持、机器失败或报告漂移均不能publishable。
- 工程复审与人工事实审核是不同角色；本轮没有替人填写任何review字段，也没有宣称已有真实企业客户效果。
