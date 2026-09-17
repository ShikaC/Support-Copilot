# AI 质量修复与真实验证 — 2026-09-10

状态：代码修复已实现并验证，真实 AI 整体门禁仍为 blocked/partial。最终冻结版本的扩展两轮各 20/22 机器正确，原始最终轮 3/4；剩余失败均为连接或读取超时，所有报告 publishable=false。完整结果见 [RESULTS.md](RESULTS.md)。人工事实审核由真实审核者填写，Agent 不代填 `SUPPORTED`。

## 修复范围和原因

本轮处理前一轮真实基线暴露的回复政策、证据不足和评估缺口，并修正知识依据面板的候选计数语义。没有替换模型、引入第二套 RAG 或修改知识 corpus。用户已授权真实模型与 Embedding 调用；数据全部为合成工单。

| 原问题 | 修改层与行为 | 关键代码 |
|---|---|---|
| 检索有弱相关候选，模型无法回答却被判成非法格式 | SDK schema 必须返回 `evidence_sufficient`；合法拒答进入 `insufficient_evidence`，保留实际模型用量和未采用候选；错误引用仍是真实失败 | `app/models.py`、`app/openai_provider.py`、`app/workflow.py` |
| 证据为空时沿用演示话术，可能给出无依据的套餐人数等事实 | live 无证据与外部故障路径使用中英文谨慎回复；未知程序错误继续抛出 | `app/response_language.py`、`app/workflow.py` |
| 核验前引用退款时效、暗示已执行退款或删除 | 来源内容 SHA-256 绑定的版本化回复规则；没有可信后台审批状态，不把客户自述转为批准事实；保留模型 warnings 并标记规则生效 | `app/grounded_reply_policy.py`、`app/data/response_policies.json` |
| 普通退款咨询被错误套入重复交易核验 | 真实 round-1 暴露后，重复扣款规则增加主题条件；不能只按 BILLING 和候选存在套用 | 同上，政策 `2026-09-10.2` |
| SYNC 排障追加绕过代理或假设 Windows | 错误码主题与知识原文共同匹配，只请求客户端版本、系统版本、代理配置 | 同上 |
| 英文工单回复中文，正文可能覆盖语言 | 语言字段贯穿 dataset→ticket→provider；限制中英文语言标签，并作为可信系统指令传入；生成语言仍由实测验收 | `app/models.py`、`app/openai_provider.py`、`evaluation/live_runner.py` |
| 机器通过但漏检指定违规话术和语言错误 | 增加有界模式与字符语言检查；验证器按回复原文重算，不能伪造结果字段通过；人工发布门禁保持独立 | [评估器证据](evaluator/README.md) |
| 脏工作树下仅记录 Git SHA 无法识别运行行为变化 | app Python、政策 JSON 与知识 JSON 纳入运行时摘要和配置指纹；源码及测试另有归档 | `evaluation/live_provenance.py`、`source-manifest.json`、`source-snapshot.zip` |
| 一般 SDK/API 错误日志无法定位 | 在原有失败事件增加固定 SDK/传输类别与受限 HTTP 状态码，不记录异常正文、header、body 或凭据 | `app/observability.py`、`app/workflow.py` |
| 前端把未采用候选计作知识依据 | 仅计算 usedAsEvidence=true；零采纳证据时仍显示人工复核提示，同时保留候选与未采用状态 | Web `AnalysisColumn.tsx`、`EvidencePanel.tsx`；[界面证据](ui/README.md) |
| p95 算法不清晰 | 新报告明确 nearest-rank；旧报告按其原始算法解释，不篡改历史 | `evaluation/live_summary.py`、`evaluation/live_review.py` |

正常链路：授权检索 → 结构化模型判断证据充分性 → 校验原始引用 → 来源及主题绑定规则 → 风险决策 → 人工审核建议。先校验引用再约束正文，避免规则掩盖模型的越界、重复或缺失引用。

失败链路：模型拒答或来源变更 → 通用谨慎回复、无引用、转人工，候选保留但 `used_as_evidence=false`。可命名外部错误 → 保留原失败原因的安全降级；不能成为机器门禁成功。未知程序错误 → 继续抛出。

## 完整实测记录

- `original/`：政策 `.1` 下原始 4 例，3 live + 1 正确无证据降级；机器门禁通过，人工未审核。
- `round-1/`：政策 `.1` 下 22 例，14 live、4 预期无证据降级、4 外部错误降级。1 次生成响应超时，3 次一般 SDK/API 错误；当时未记录底层 SDK/传输类型，不能断言后者是连接、限流或服务端故障。机器门禁失败，原始退出码 1。所有回复通过指定语言和违规模式检查，但逐条自动检查仍发现普通退款被套用重复扣款流程，因而修改 `.2` 主题条件。保留失败证据，不覆盖、不剔除。

原始及新数据集内容没有因失败而删减或放宽。round-1 使用数据集 2.0.0，其完整快照保存在 `round-1/dataset.json`；随后 2.1.0 仅为退款案例增加“不假设重复交易”的更严格断言。`live-quality-v2.json` 含 22 条：保留前版 16 条，并明确语言、指定话术约束，新增 6 条条件和对抗输入。新变体不能视作独立真实客户样本。

- `round-2/`、`round-3/`：政策 `.2` 下各 17 live + 4 正确无证据降级 + 1 `invalid_model_response`。同一 `quality-refund` 重复失败，不能归为已证实的供应端网络波动。round-2 与 round-3 之间仅将安全日志中的嵌套 if 合并以通过 Ruff；分别保留运行时快照。

受控诊断 `refund-wire-diagnostic.json` 捕获了合成模型结果：HTTP 200，回复正确引用退款核验政策，但同时返回 `evidence_sufficient=false` 和非空 `citation_indexes=[1,2]`。这是字段语义歧义引发的结构矛盾，原校验按设计拒绝。随后修改字段描述与系统提示，明确“知识能支持安全的限制说明或核验步骤”也属于有据回答；客户审批状态未知不等于知识缺失。保留禁止假设后台审批和拒绝矛盾结构的规则。`refund-wire-diagnostic-fixed.json` 记录修复后的针对性复测；这些诊断调用单独计数，不混入完整基线。

## 可复现命令

在仓库 `services/support-copilot-ai` 目录运行；真实调用需要已有的有效环境配置，不在证据中保存凭据。

```bash
.venv/bin/pytest -q
.venv/bin/python -m evaluation.run_mock_evaluation
.venv/bin/python evaluation/run_live_evaluation.py --dataset evaluation/data/live-v1.json --report-dir ../../docs/verification/ai-quality-fixes-2026-09-10/original-final
.venv/bin/python evaluation/run_live_evaluation.py --dataset evaluation/data/live-quality-v2.json --report-dir ../../docs/verification/ai-quality-fixes-2026-09-10/final-1
.venv/bin/python evaluation/run_live_evaluation.py --dataset evaluation/data/live-quality-v2.json --report-dir ../../docs/verification/ai-quality-fixes-2026-09-10/final-2
.venv/bin/python evaluation/verify_live_evaluation.py --report ../../docs/verification/ai-quality-fixes-2026-09-10/final-2/live-latest.json --dataset evaluation/data/live-quality-v2.json
```

命令中的目录对应本轮固定证据；后续复测应使用新目录，避免覆盖 `live-latest.json`。验证器的 `live-evaluation-valid=true` 表示报告与当前上下文一致，不等于人工审核通过或生产可发布。需要另看机器门禁、`publishable` 与 `--require-human`。

## 本地验证

- 最终 Python 全套：`.venv/bin/pytest -q` → **288 passed**，见 `pytest-final.log`。
- mock 固定集：`.venv/bin/python -m evaluation.run_mock_evaluation` → **31/31 passed**，见 `mock-result.json`。此结果仅证明 mock 回归。
- 本轮修改的 AI 运行时与评估模块 Ruff 通过；所查运行时 basedpyright **0 errors / 2 warnings**，两处 warning 为显式 `assert_never` 穷尽分支，未屏蔽检查；评估器 8 个修改模块为 0 errors / 0 warnings。
- 安全故障诊断 12 项验证通过，包含固定类型、429/503、原因链循环以及敏感 canary 不泄露；完整 Python 288 已包含新增诊断案例。
- Web 全单测 **88 passed / 3 skipped**（原有 live 集成开关）；包括新增 3 态渲染回归。TypeScript、Vite build 和修改组件/测试的 lint 通过。真实 Chromium 9 个场景（375/768/1280 × 三态）无横向溢出或 page error，两个独立只读视觉审核均 PASS/HIGH、无阻塞；证据见 `ui/README.md`。
- 最终三份报告由 `verify_live_evaluation.py` 验证 provenance/汇总/原文重算均通过；`--require-human` 正确失败为 `human-review-incomplete`。这不将机器失败改为通过。
- `git diff --check` 通过。源码文件 manifest 与归档绑定当前内容；配置中已有凭据值扫描未发现出现在本轮证据内，不把此扫描宣称为通用 DLP。
- 原预览进程已停止，已重新通过 `./scripts/dev-workspace.sh` 启动 18173/18080/18000；API 与 AI 健康，保留现有文件 H2。预览仍是 mock，不把网页展示当作 live 基线。

## 证据边界

基础 Git HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty；本轮没有提交、推送或部署。AI 当前源码证据由运行时 hash 和独立文件 manifest 绑定，UI 单独保留截图及测试证据，不冒充干净提交。前一轮 UI、Java、Pilot 改动保留，其历史测试不能代表本轮重新验证过。

原始向量候选放在 `live_retrieval`；最终采纳片段放在 `retrieved_chunk_ids`。未知硬件仍可能被向量检索召回弱相关片段，正确拒答不等于消除了弱相关召回。规则仅约束列明的已绑定来源和主题，不能证明任意问题不存在幻觉。

正常 live 回答中部分正文由确定性规则约束；报告 warnings 明示这一事实。最终系统质量不等于模型未经约束的原始生成质量。中英文检测只是字符检查，禁用模式只是指定回归模式，两者不能替代完整语义与事实审核。当前仅支持中英文语言标签，不支持的语言会校验失败。

实际费用缺少已确认网关单价，保留 `cost=null`；有返回的模型 token 如实记录，不能填零费用。小型合成 corpus、两次运行和低并发不能证明生产稳定性、真实客户效果或容量。人工审核保持 `NOT_REVIEWED`，不得把 Agent 的源码审查或逐条自动复核填作人工质量结论。

可以写入项目经历：实现可审计的真实模型/向量检索评估、来源绑定回复规则、显式证据不足处理、机器与人工双门禁，并附本目录限定数据结果。不能写成企业生产使用、全部回复事实正确、已具备真实审批/退款/删除执行能力，或生产发布通过。
