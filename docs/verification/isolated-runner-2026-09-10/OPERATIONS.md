# 知识库、人审与超时：当前怎么操作

本说明依据2026-09-10当前源码；没有把计划中的网页入口写成已实现功能。

## 知识库增删改

目前前端不能新建、编辑或删除知识文档。KnowledgeView 的演示分支只在静态目录中搜索/筛选；真实API分支支持已授权知识检索和已有release的批准/发布/回滚。后端 CreateReleaseRequest 仅接收releaseId/version/checksum/scopes，不接收正文，创建release不是上传文档。

当前实际知识来自 Java `support-copilot.knowledge.corpus-path` 与 Python `KNOWLEDGE_PATH` 指向的同一规范JSON。修改内容还会改变corpus checksum、分块、embedding artifact、release身份；只改网页文案或JSON正文不能保证检索生效。尤其 Python 在启动时加载corpus，不能把当前发布操作描述为完整热更新。

需要开发的产品闭环是：新增/编辑文档草稿（正文/来源/适用范围）→生成独立新corpus和索引→结构及权限/引用校验→批准发布→Java与Python切换到一致版本→验证真实检索。删除优先设计成归档，旧分析引用保留历史版本。此闭环尚未实现；本轮没有改知识内容，以保持真实诊断的同一corpus基线。

## 三种“人工审核”要分开

1. **工单回复审核（已有网页操作）**：在连接真实Java的工作台选择工单→辅助分析→回复建议→阅读知识依据→原样点击“记录审核”或编辑后点击“记录审核”；不同意则“拒绝建议”并填写理由；“审核历史”查看持久化记录。安全模式需要SUPPORT_REVIEWER或SUPPORT_ADMIN。它记录客服操作，不会自动改变固定评测报告的人审数；也不代表系统已向客户发送回复。显示“演示数据·不保存审核记录”时不属于真实持久化路径。
2. **评测输入与参考确认（文件入口）**：阅读旧输入审计 `REVIEW.md` 的完整上下文、DIRECT/CLARIFY/OUT_OF_KB标签、必要要点与依据。已提供本目录 `input-review-working.json`，全部保持待审。真人填写reviewer/UTC时间，确认source_and_context_approved、required_points_approved及answerability，并将status改为APPROVED。若不同意标签/参考，不应为了通过门禁强行批准；记录reference_changes，另建数据版本。此文件绑定cases SHA，不能编辑冻结原件。当前runner仅需要13题development审核；本轮用户另行授权未人审的运行诊断，语义分数依然null。
3. **模型回答事实审核（旧22例有CLI，网页尚无入口）**：本目录 `live22-review-working.json` 是旧报告生成的空白审核表。对照旧报告每题输入、实际回复与采用证据，真人填写 `factual_support`（SUPPORTED/PARTIAL/UNSUPPORTED）、`decision_note`、`reviewer`、`reviewed_at`。它是事实支持审核，不等于完整问题解决率。填写后可在AI服务目录使用现有 `python -m evaluation.live_review apply --report <原报告> --worksheet <填写表> --output <全新报告>`，再用现有 verifier校验。不得覆盖旧live-latest或run-1。当前质量页派生报告v1明确只接入未审核历史报告，完成CLI人审后还需要扩展导入契约才能在新报告中展示；不能手改页面计数。

本轮13题真实诊断完成后的原始回答将另行生成可读材料；输入审核和输出审核各自记录，AI不代填真人结论。

## 超时如何优化

已核查旧96条trial与安全日志：18次均为生成阶段APITimeoutError/ReadTimeout，约20秒结束。单并发6、双并发0、四并发12；三组按固定先后运行，不能得出并发导致超时的因果结论。超时组证据字符数均值5219，正常组5614，也不支持“文本越长必超时”的简单解释。

SDK固定20秒且0重试；Java合法HTTP200 fallback不重试。增加Java最大重试次数不会修复这18个200 fallback。105秒Java总期限也不是这些20秒错误的触发层。供应端是否接收、执行及计费仍需要网关日志，不能由本地ReadTimeout断定。

本轮先补每次provider操作STARTED/终态/trace/安全错误分类，保持同一模型、提示词、索引和超时取得真实diagnostic基线。后续单变量比较可优先限制不必要的输出篇幅、评估有依据的上下文裁剪，分别观察正常产出、p95和回答质量；不要同时换模型/改prompt/改并发。官方[延迟优化指南](https://developers.openai.com/api/docs/guides/latency-optimization)也将输出token数量列为主要延迟因素；这只支持实验方向，不证明当前兼容网关已获得同样收益。输出token上限须核实网关兼容性及结构截断失败。

20→30秒可作为另一个明确预算实验，但延长等待不等于加速。流式输出可以改善首屏等待，结构化结果仍须完整校验后才能作为最终建议保存。暂不增加多层自动重试，不使用重跑成功结果替换失败记录。
