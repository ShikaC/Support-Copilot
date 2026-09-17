# 真实 AI 质量基线协议

2026-09-09。用户明确授权完成真实 AI 质量基线，包括配置中的聊天/Embedding 调用；仅外发仓库合成案例和已脱敏知识。既有 demo 预览不改为 live，不发送客户消息。

## 冻结输入

- 原始回归集：evaluation/data/live-v1.json，4 例，保持原文不变。
- 扩展集：evaluation/data/live-quality-v1.json，1.0.0，16 例；13 例有证据、3 例无证据，包含 2 例指令注入和 1 例英文。扩展集在其首次模型调用前固定。
- 复用原知识 corpus（10 chunks）；不修改政策正文，不根据输出修改 gold expectation。
- 沿用配置模型 gpt-5.6-luna / chat_completions、Qwen/Qwen3-Embedding-0.6B；topN=10、topK=3、live cosine threshold=0.35、外部超时20秒、整体90秒、SDK零重试。
- 唯一已确认运行修复是 Embedding 原始文本兼容及旧索引拒绝复用。原始失败报告保留。

## 执行及指标

原始4例修复前/后对照；扩展16例连续两轮，所有运行保留，不挑选最好结果。每轮记录实际分类、人工升级、检索命中与排名、引用ID合法性、回复、trace、延迟、可用聊天token。扩展集不是盲测：SSO/发票/导出三主题用于此前Embedding诊断，应视为诊断后回归，其余主题作为扩展覆盖，不声称独立总体泛化。

机器门禁要求每例预期检索、引用、分类及升级全部符合；无证据案例必须确实 insufficient_evidence、无检索/无引用并升级人工。异常 fallback 不充当安全成功。模型失败不能由本地规则掩盖为 live 成功。机器引用合法性只检查ID关系，不证明回复每个事实得到支持。

人工审核逐例检查事实支持、越权承诺、注入抵抗和实际可用性；机器不得代填。只有每例 SUPPORTED 且机器通过才 publishable=true。报告CLI完成机器门禁与人工发布门禁分离。

成本：现有价格配置只支持聊天token估算。自定义聊天网关没有经确认的单价，不以公开OpenAI价格冒充账单；Embedding SDK未提供本轮费用记录，索引构建/失败请求也可能产生费用。保留usage，不将缺失费用写成0。

延迟为此机器顺序调用的端到端runner时长，不代表服务端并发SLO。小样本p95与命中比例仅描述本数据集。本轮不证明真实客户效果或生产稳定性。

## 诊断后冻结修复

扩展 run-1/run-2 发现自由分类绕过风险升级，外部结构化输出增加固定业务类别枚举（不修改标准答案）。最终 final-1/final-2 在同一源码快照、数据集与索引连续运行；保留全部早期运行，不合并为同一个配置的准确率。run-2 起单独记录真正 live 向量检索，与故障后本地 fallback 检索分开。schema/prompt/runtime 配置以源码 SHA256、报告 config fingerprint 和 artifact manifest 绑定。
