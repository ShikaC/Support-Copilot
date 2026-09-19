# Support Copilot 下一会话交接提示词

> 2026-09-19 恢复入口：先读[本轮对抗式审查记录](../verification/adversarial-review-2026-09-18/README.md)，核对 Git、远端和 CI；修复代码边界为 `6800f13`。用户已明确授权“审查并修复问题后推送 GitHub”，不要再次索要同一推送授权。模块回归和本地安全门禁已通过，文档提交与远端结果须查实际记录。审查修复不包含第 7 节的重建任务功能。

> 当前事实以 [STATUS](../STATUS.md) 为准，详细数字以各独立报告为准。新评测工具要求执行时计划/向量摘要；09-17/09-18 旧缓存缺少它们，当前工具拒绝直接重算，不能补写事后哈希或自动重跑付费请求。
>
> 索引可以不重启热重载，且现在 reload 绝不隐式建库或付费，失败保留旧快照；语料与索引必须匹配。评估集 76 题（development 40 / holdout 36 封印）。切片参数可配，1000/800 实验没有显示显著收益。比较协议已预注册，但最后一次真实探测仍被 provider chat 端点 503 阻塞，本轮没有重新探测。
>
> **下一步（已选定）**：把索引重建任务化——让"换切片"从三条手工命令变成一次请求加轮询。分层与验收见下文第 7 节。

项目路径：`/Users/shika/Documents/Support-Copilot`。

## 1. 用户目标与当前授权

用户要可追溯的回答质量、全链路延迟、正常产出/降级/超时和持久化证据，并要作者本人能读懂、能复述、能审核自己的代码（理解优先，见 `docs/learning/TEACHING_PROTOCOL.md`）。没有内部客户数据，只用公开归档文档、Doc2Dial 人工构建对话和真实公开 issue；不得称为企业真实客服日志。

本轮已授权：对抗式审查、必要修复、回归、本地提交并推送既有 GitHub 分支。既有付费比较授权与一次性执行边界继续保留，但本轮不触发模型/Embedding 调用，不消耗 holdout；不将本轮推送授权扩大为部署、客户数据或新的大额实验授权。真实模型测量不等于人工质量审核；AI 标签、人审状态和未知费用不能虚构。

## 2. 恢复顺序

1. 完整阅读 `AGENTS.md`、`MISSION.md`、`docs/learning/TEACHING_PROTOCOL.md`、`V1_PROJECT_MAP.md`、`ONE_WEEK_INTERVIEW_SPRINT.md`、`LIVE_RAG_COMPLETION_CRITERIA.md`、`docs/optimizations/ROADMAP.md`、`docs/STATUS.md`、`docs/ROADMAP.md`、`docs/learning/READING_LOG.md`。
2. 查看 Git 状态、分支与最近提交，先确认本轮审查的文档门禁、推送和 GitHub Actions 是否完成。代码提交列表见审查记录；`315b535` 是此前热重载历史切片。禁止回退或覆盖已提交历史。
3. 若确有新改动或失败需要验证，使用以下入口；本轮已执行结果以审查记录为准，不无故重跑全部历史实验：

```bash
(cd services/support-copilot-ai && .venv/bin/python -m pytest -q)
node --test scripts/benchmark/*.test.mjs
./scripts/verify-docs.sh --static
```

`verify-docs.sh` 在 `git archive HEAD` 的临时副本里跑，**只反映已提交状态**：工作区改动未提交时它看不见，也正因此它是最强的"提交是否自洽"门禁。文档契约会把 FastAPI 装饰器与 Java controller 的实际路由和 `docs/PILOT_OPERATIONS.md` 表格逐项比对——新增端点必须同步登记，否则门禁红。

## 3. 已实现能力（都不等于生产就绪）

| 能力 | 位置 | 证据 |
| --- | --- | --- |
| 离线检索评测（含语料一致性 fail-closed） | `scripts/benchmark/retrieval-eval.mjs` | `docs/verification/retrieval-eval-2026-09-11/` |
| 检索-only 基线、全库 gold 排名、离线融合实验 | `evaluation/retrieval_only.py`、`gold_rank.py`、`hybrid_retrieval.py` | `docs/verification/retrieval-only-2026-09-17/` |
| 评估集扩容到 76 题 | `scripts/benchmark/expand-quality-inputs.mjs` | `docs/verification/retrieval-cases-expanded-2026-09-18/` |
| 切片参数化（窗口/步长/配额） | `scripts/benchmark/prepare-doc2dial.mjs` | `docs/verification/chunking-1000-800-2026-09-18/` |
| 索引版本清单（只读） | `GET /knowledge/index/versions` | `docs/verification/index-versions-2026-09-18/probe.json` |
| **索引热重载** | `POST /knowledge/index/reload`、`RetrievalState` | 同目录 `probe-reload.json` |

## 4. 检索评估必须守住的口径

development 40 题上：纯向量 gold@1 50.0% / gold@3 80.0% / MRR 0.625；等权 RRF k=60 融合 31/40、36/40、MRR 0.829（改善 5、退化 1，**McNemar p = 0.2188，未显著**）。1000/800 切片下 32/40、37/40（p = 0.1797）。

- 扩展集与冻结开发集**只能各自纵向比较**，绝对命中率不得混算。扩展题 `audit.label=PENDING`，**不产生答案性或质量结论**。
- **holdout 36 题未运行**，只能验证事先固定的方案（当前仅等权 k=60 合格）。参数扫描里最好看的 `bm25x0.5` 是在 40 题上挑出来的，**不许**用 holdout 验证它。用 holdout 是不可逆消耗，需先确认。
- **不显著就不改生产检索**。新的完整取证缓存可以零调用复现排序实验；历史缺失执行摘要的缓存只保留原报告，不用当前 CLI 重新认证。新真实调用仍按独立计划和预算决定。
- 调大 top_k 是成本决策，不是质量修复。
- 扩展集暴露了旧集看不到的问题：3 题 gold 排在 10 名之外（第 97 / 35 / 12 名），重排救不回；旧集"召回够用、只差排序"的结论只在 11 题上成立。

## 5. 切片与索引的当前状态

切片参数已可从命令行配置（`--window/--stride/--per-domain/--output/--source/--verify-against`）。**默认参数必须永远能复现冻结产物**：

```bash
node scripts/benchmark/prepare-doc2dial.mjs --verify-against docs/verification/business-benchmark-2026-09-10   # 必须 verified: true
```

- 切片身份由参数推导（`doc2dial-codepoints-{window}-{stride}-v1`）；步长大于窗口会被拒绝（会静默丢内容）；切片一变就是新基线，不得与冻结集混算。
- 评分时**必须同时传 `--corpus`**，否则 `retrieval-eval.mjs` 因 chunk_id 对不上直接报错（fail-closed，不匹配率 >10% 即失败）。
- **`chunking_version` 现在是观测字段，不再参与兼容校验**。该保护的是"索引每一行是不是它声称的那块内容"，由 `corpus_checksum` ＋逐行 chunk 对齐保证；切片版本只是标签。**不要再恢复 activate/rollback**：换切片必然换语料，"只换索引不动语料"在语义上是错的。不同语料的 artifact 仍被拒绝，这是**有意保留**的边界。
- **运维顺序不能乱**：换语料文件 → 用**新语料**建索引并移 active 指针（用运行中进程的旧 store 会被正确拒绝）→ `POST /knowledge/index/reload`。
- `evaluation/live_verifier.py` 的 chunking_version 校验**不能拿掉**：那是评测取证，不是运行时保护。换 embedding 模型仍需改配置并重启（`provider_identity` 与 `model` 仍在校验内，查询侧要用同一模型）。
- 清单里的 `modifiedAt` 是文件系统时间，不是构建证据。

## 6. 仍然阻塞与不能重复的事项

- **比较运行被 chat 端点 503 阻塞**（2026-09-17 探测：模型列表与 embedding 正常，`POST /chat/completions` 持续 503）。claim 未写入、无生成费用。恢复后**先跑** `node scripts/benchmark/provider-probe.mjs` 确认 READY，再执行 `run-isolated.mjs --id development-comparison-20260911 --execute --comparison docs/verification/development-comparison-2026-09-11/protocol.json`。每个 comparisonId 只执行一次，**不得删除、绕过或覆盖旧 claim**，失败同样保留；不覆盖 base run、不用 holdout、预算冻结、不重跑择优。
- **13 题真实诊断已完成，不是待启动任务**：不得重复运行该批、覆盖 run-1，或用删除一次性 claim 的方式补跑成功结果。run-1 只保留 ID/traceId/mode/正文 4 字段核对结论；最新 13 条才是逐字段全对象核对，两者不能混称。
- 旧验证器（isolated-runner、quality、query-context-fix 的 `verify.mjs`）绑定修复前工作树，会因后续授权改动失败。**保留原件，不改旧门禁制造通过**。
- 14 个 Java MySQL 用例需 Docker/环境变量；`verify-docs.sh --full` 未运行。真实 live 质量门禁仍 partial（人工审核 0、质量分数 null）。

## 7. 下一步：把索引重建任务化（已选定方向）

**业务问题**：现在换切片要人手敲三条命令（Node 生成语料 → Python 建索引 → 移文件并重启重载），中间任何一步顺序错就会被 409 拒绝。用户要的是"前端可调切片大小、上传数据集文档"，而这两个需求**都卡在同一段缺失的能力**上：服务端能自己生成语料与索引。没有它，前面的清单和热重载只是给人看的仪表盘。

**建议分成两个垂直切片，先做 A**：

### 切片 A：索引重建任务化（语料已在磁盘上）

目标：一次请求触发重建，轮询进度，完成后可选自动重载；不阻塞其他请求、不并发、失败保留现场。

影响范围：新端点（`POST /knowledge/index/rebuild` + `GET /knowledge/index/rebuild/{taskId}`）、`EmbeddingArtifactStore.build` 的任务包装、`app/main.py` 装配、`KnowledgeView` 之后接。**不改**校验语义、不改检索路径、不改切片逻辑。

必须做对的点（都来自本轮踩过的坑）：

- 构建是 CPU/IO 密集 + 数千次外部调用，**必须在线程里跑**（`anyio.to_thread`），不能占住事件循环。
- **单任务串行**：已有任务运行时拒绝新任务（409），不是排队。
- **绝不自动覆盖 active 指针**：构建产出一个新 artifact；激活与重载是独立的一步。本轮已经证明"只换索引不动语料"会被正当拒绝，让重建顺手激活等于制造半成品状态。
- **失败必须留下 artifact 目录与错误原因**，不静默重试、不自动清理、不吞异常。
- 默认关闭（沿用 `KNOWLEDGE_INDEX_MUTATION_ENABLED`），内部服务鉴权优先于功能开关。
- 进度要有真实含义（已完成片段数 / 总片段数），不是假百分比。
- 成本可见：估算调用次数与耗时（3015 chunks 约 50 秒），与冻结预算口径一致。

验收标准：状态机 `RUNNING → SUCCEEDED | FAILED`；并发第二个任务被拒；失败时旧 active 与旧语料完全不变；重启进程后能读出上次任务状态或明确报"任务信息已丢失"（二选一，写清楚）；真实演练一次并保存 probe 证据。

验证命令：

```bash
cd services/support-copilot-ai && .venv/bin/python -m pytest -q
# 真实演练：起服务 → POST 重建 → 轮询 → GET /knowledge/index/versions 看到新 artifact 且 active 未自动改变
```

### 切片 B：语料生成任务化（需要先做决策）

切片逻辑目前**只在 Node 里实现**，且有 `--verify-against` 逐字节复现冻结产物的自检。要在服务端生成语料，有两条路，**这是需要用户明确选择的决策点，不要猜**：

- **B1：Python 调用 Node 子进程**。优点是不复制逻辑、不会漂移；代价是运行环境必须装 Node，且要处理子进程超时/退出码/输出捕获。
- **B2：用 Python 重写切片逻辑**，并用冻结产物做**逐字节对拍**证明等价。优点是服务自包含；代价是两套实现长期共存，任何一侧改动都可能静默漂移。

在此之前还要确认：`--per-domain` 配额是**评测集**相关参数，生成语料并不需要它——重建语料与重建评测集应当分开谈，不要顺手把两者绑在一起。

### 更远的（现在不要做）

上传文档 → 解析 → 切片 → 生成语料这条链路还缺文档解析、权限、审核与失败语义，属于切片 B 之后独立的垂直切片。同时提醒：**不要**为了这条链提前引入消息队列、Redis 或 Kubernetes——当前没有量化需求支撑。

## 8. 停止条件与环境保护

- 现有端口/进程状态恢复后要重新核对；`.local/workspace/data`、旧工作台数据不得被重建流程覆盖。
- 预算冻结：`sdkSeconds 20 / pythonSeconds 90 / javaMs 105000 / clientMs 130000 / batchMs 2100000 / maxAnalyses 14 / maxServiceAttempts 2`。重建任务的 embedding 调用量要单独估算并事先说明，不得混入既有预算口径。
- 未知程序错误、账本/trace/来源漂移、认证或配额失败、连续 3 次依赖失败：停止并保存 NOT_EXECUTED，不用重试或降级掩盖。
- 既有 artifact 预检失败不自动付费重建；任何新的大额范围、客户数据、远端写入或部署需独立明确授权。
- 凭据只读既有环境变量，不打印、不提交。探测工具只记录字节数或错误文本。

## 9. 交付与简历边界

每轮交付必须写清：修改/阅读的文件与关键位置、原问题与风险、选择该修改层的理由、正常路径与至少一条失败路径、测试或手动验证（命令、Git SHA、工作树状态、结果范围）、当前限制。

**可以写进简历**：公开数据上的真实跨服务测量；独立实验隔离与调用计数；完整持久化与重启验证；从 13 条相同 query 定位检索截断并用"先失败后通过"的回归修复；在 40 题评估集上做诚实统计（报告 p 值、拒绝用 holdout 找显著）；把索引版本清单从"只能看"做成"能热切换"，并给出 1686 ms 的真实切换与 409 的失败路径。

**不能写**：修正后的收益、回答准确率、真实客户解决率、节省工时、生产容量、企业运营经历，以及把 AI 审查冒充真人 gold 或作者已理解。
