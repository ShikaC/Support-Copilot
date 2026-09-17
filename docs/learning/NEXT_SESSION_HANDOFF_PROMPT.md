# Support Copilot 下一会话交接提示词

> 更新：2026-09-11，提交前工作树已固化为 6 个提交之后。恢复入口；当前事实以[STATUS](../STATUS.md)为准，详细数字以独立报告为准。

项目路径：`/Users/shika/Documents/Support-Copilot`。

## 用户目标与当前授权

用户要真实、可追溯的回答质量、全链路延迟、正常产出/降级/超时和持久化证据。没有内部客户数据，使用公开归档文档、Doc2Dial人工构建对话和真实公开issue；不得称为企业真实客服日志。用户要求后续业务验证使用真实调用，不使用演示业务数据；确定性fixture只供明确的单元/集成测试，不能充当业务成果。

用户已授权直接优化产品和既有范围内模型/Embedding调用；最新明确回答为“先做真实诊断，不计算人工质量分数”。这项授权已经执行，**固定13题单次诊断已完成，不是待启动任务**。不能重复运行该批、覆盖run-1或删除一次性claim补跑成功结果。真实模型测量不等于人工质量审核；AI标签、人审状态和未知费用不能虚构。

## 恢复顺序

1. 完整阅读本文件，以及 `AGENTS.md`、`MISSION.md`、`docs/learning/TEACHING_PROTOCOL.md`、`V1_PROJECT_MAP.md`、`ONE_WEEK_INTERVIEW_SPRINT.md`、`LIVE_RAG_COMPLETION_CRITERIA.md`、`docs/optimizations/ROADMAP.md`。历史任务不自动成为活跃待办；不用重复教学题阻挡已授权实作。
2. 读 `docs/STATUS.md`、`docs/ROADMAP.md`、`docs/learning/READING_LOG.md`。
3. 先读[query修复交付](../verification/query-context-fix-2026-09-10/README.md)及`change.patch`、`verification.json`；再读上一阶段[诊断交付](../verification/isolated-runner-2026-09-10/README.md)、[实际结果](../verification/quality-runs/development-live-diagnostic-20260910/RESULTS.md)、[检索截断诊断](../verification/quality-runs/development-live-diagnostic-20260910/DIAGNOSIS.md)、`query-diagnosis.json`、run的`manifest.json`及`source-hashes.json`。
4. 再读[旧业务基准](../verification/business-benchmark-2026-09-10/README.md)、[输入审计](../verification/quality-input-audit-2026-09-10/README.md)、`PROTOCOL.md`、`AMENDMENT-1.md`、`freeze-manifest.json`。旧初版candidate中的DMV州别推断已明确废弃，不能送模型；实际输入白名单保留此前全部上下文，不含gold/目标agent回复/AI标签。
5. 查看Git状态、分支和最近提交。2026-09-11 已把提交前工作树固化为 6 个提交：master、HEAD `c923d0e`、工作树 clean、本地领先 `origin/master` 未推送，详细边界见 `docs/STATUS.md` 顶部。仍然禁止回退或覆盖已提交历史；历史报告中的 source hash 仍绑定提交前工作树，不能因为 HEAD 变化就宣称旧证据在当前源码上复现。
6. **第一条验证命令**：根目录运行 `node docs/verification/query-context-fix-2026-09-10/verify.mjs`。该验证保护本轮前工作树、旧结果和本轮授权源码/文档边界。上一阶段isolated-runner及quality验证器绑定修复前工作树，现在会因本轮授权源码/文档改变失败；保留原件，不改旧门禁。旧`verify-quality-inputs.mjs`的上一阶段整工作树门禁已因已授权产品变更过期，保留原件，不修改门禁制造通过。

## 已完成与已确认缺陷

本轮独立运行器已实现并经过AI代码审查（不是真人质量审核）：独占实验目录/端口/文件H2/JAR、源码和配置快照、复用既有向量artifact禁止文档Embedding、provider操作STARTED/终态/trace账本、预算与停止保护、即时及Java重启完整对象读回。

实际13题全执行，query Embedding13、generation13、文档Embedding0；最终13个insufficient_evidence，正常live0、超时0。全部即时与重启完整对象比对匹配。具体耗时与token只维护独立summary。HTTP200、SDK操作完成、完整保存均不能算正常AI回答成功。

**下一步的关键问题已经由真实数据定位：** `services/support-copilot-ai/app/workflow.py:258-260`只拼subject和正文前180字符。新输入开头的统一说明占满180字符，实际13条query和3个候选chunk列表完全相同，机构/业务问题没有进入检索。生成模型仍收到完整工单正文；不能把它说成模型没收到问题。随后用户要求修复，已去掉该180字符截断，保留受240/4000长度约束的完整标题/正文。19项新增离线回归与AI模块324项通过，13个输入形成13条不同query。没有修正后的真实模型复测；不能称“质量优化已奏效”。当前13题结果是有效故障诊断，不是正常业务检索后的质量或通用性能基线。

输入的DIRECT/CLARIFY/OUT_OF_KB标签都是AI建议。13题的全部实际回复和采用/未采用片段已保存；`output-review-working.json`全为NOT_REVIEWED。人工确认、准确率、问题解决率、节省工时、费用仍未知。本轮未保存供应商原始HTTP响应或中间ModelDraft，不能进一步猜测模型内部原因。

## 第一切片与后续顺序

1. 当前query修复已完成；优先核对本轮diff与离线证据，不重复实现。只修改`workflow.py`的query构造，现有脱敏、权限、长度校验和失败语义不改。完整输入会增加Embedding输入，相关性、延迟、费用需要后续实测；不因离线query不同就宣称召回改善。
2. 下一可执行切片是在本轮diff审阅后，预注册修正后的development比较：独立实验ID、源码/预算/全部计划、失败与未执行行。此13题已经见过输出，只能称development复测；holdout仍未使用。旧runner一次性claim不能删除或绕过，必须显式设计比较协议；没有新的付费数据时保持质量结论未测。
3. 真人逐题审核输入与模型输出。工作表和当前操作入口见[OPERATIONS](../verification/isolated-runner-2026-09-10/OPERATIONS.md)。准确率不能由指定文档命中、跨度覆盖或词语F1代替。
4. 后续才接入新run的质量页导入契约、提供评测人审网页闭环、开发知识正文草稿/索引/发布一致性闭环。现有知识页没有正文增删改；release元数据创建不等于上传正文。工单“记录审核”保存的是单条回复处理，不能自动改变固定评测报告。
5. 超时改进以真实观察为依据。旧96题18个生成读取超时发生约20秒，SDK0重试、Java200fallback不重试；三组先后运行，不能因果归因于并发。优先评估输出长度/有效上下文；单独延长deadline只是多等待，不等于加速。无网关日志时不猜服务端根因，不用多层重试掩盖失败。

## 停止条件与环境保护

最新独立run为`development-live-diagnostic-20260910`，运行数据在`.local/quality-runs/`，结果在`docs/verification/quality-runs/`。本轮Java18280/Python18200均已停止；下一会话仍须核对实际端口状态。原工作台18173/18080/18000和`.local/workspace/data`未重启或改数据。

本轮Java使用loopback demo安全profile以访问本地匿名API，但fixture显式关闭、实际GET验证空数据库，Python为live；没有演示工单或mock生成。这不是生产身份认证验收。用户当前18174/18081质量预览仍显示旧22/96真实冻结报告，其其他业务demo页面不能拿来当本轮真实数据；新13题尚未接入质量页。

SDK20s/Python90s/Java105s/客户端130s、35分钟批次、单并发、每类26/总52操作硬上限、SDK和客户端0重试、Java最多2次。未知程序错误、账本/trace/来源漂移、认证/配额或连续3次依赖失败必须停止并保存NOT_EXECUTED。既有artifact预检失败不自动付费重建；任何新大额范围、客户数据、远端写入或部署需独立明确授权。凭据只读既有环境，不打印或提交。

旧run-1冻结96条即时响应本轮之前已做全对象比对；**旧重启只保留ID/traceId/mode/正文4字段核对结论**。最新13条才是保存完整重启响应并逐字段全对象核对，两者不能混称。

## 交付与简历边界

每轮交付文件/准确位置、原问题/改动层、正常及失败路径、真实命令/退出码、HEAD/dirty/运行hash、保留的失败、人工状态和剩余限制。6 个固化提交之后的未提交改动应从 `c923d0e` 起重新计数，不把已提交内容再描述为工作区改动。

简历可以陈述公开数据真实跨服务测量、独立实验隔离与调用计数、完整持久化重启验证，以及从13条同query定位检索截断、用先失败后通过的回归修复上下文丢失。不能写修正收益、回答准确率、真实客户解决率、节省工时、生产容量或企业运营经历。恢复后不要以AI审查冒充真人gold或作者已理解。
