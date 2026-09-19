# Support Copilot 下一会话交接提示词

> 2026-09-19 恢复入口：先读[语料生成任务 B1](../verification/corpus-build-tasks-2026-09-19/README.md)，核对 Git、文档门禁与最新 CI。索引重建 A 在 `444bbde` 已推送且四条 CI 通过。用户随后要求“继续”，B1 沿用 Python 调 Node 的推荐方案，已实现候选语料构建；实际验证、审查修复和限制见 B1 报告，不用旧提交的绿色替代新提交证据。

> 当前事实以 [STATUS](../STATUS.md) 为准，详细数字以各独立报告为准。新评测工具要求执行时计划/向量摘要；09-17/09-18 旧缓存缺少它们，当前工具拒绝直接重算，不能补写事后哈希或自动重跑付费请求。
>
> 索引可以不重启热重载，且现在 reload 绝不隐式建库或付费，失败保留旧快照；语料与索引必须匹配。评估集 76 题（development 40 / holdout 36 封印）。切片参数可配，1000/800 实验没有显示显著收益。比较协议已预注册，但最后一次真实探测仍被 provider chat 端点 503 阻塞，本轮没有重新探测。
>
> **下一步**：先核对 B1 的最终交付与 diff，再设计“选择成功候选语料 → 对它构建索引”的显式交接。不要重复实现 A/B1，也不要把候选生成或本机替身验收当成已授权付费建库。Java/前端入口与上传解析尚未实现。

项目路径：`/Users/shika/Documents/Support-Copilot`。

## 1. 用户目标与当前授权

用户要可追溯的回答质量、全链路延迟、正常产出/降级/超时和持久化证据，并要作者本人能读懂、能复述、能审核自己的代码（理解优先，见 `docs/learning/TEACHING_PROTOCOL.md`）。没有内部客户数据，只用公开归档文档、Doc2Dial 人工构建对话和真实公开 issue；不得称为企业真实客服日志。

本轮已授权：继续实现推荐的语料生成 B1，并沿用推送已审查代码的授权，完成回归、提交和推送。B1 只做文档候选生成，不触发真实模型调用或消耗 holdout；不将授权扩大为部署、客户数据或新的付费实验。既有付费比较的一次性执行边界继续保留。真实模型测量不等于人工质量审核；AI 标签、人审状态和未知费用不能虚构。

## 2. 恢复顺序

1. 完整阅读 `AGENTS.md`、`MISSION.md`、`docs/learning/TEACHING_PROTOCOL.md`、`V1_PROJECT_MAP.md`、`ONE_WEEK_INTERVIEW_SPRINT.md`、`LIVE_RAG_COMPLETION_CRITERIA.md`、`docs/optimizations/ROADMAP.md`、`docs/STATUS.md`、`docs/ROADMAP.md`、`docs/learning/READING_LOG.md`。
2. 查看 Git 状态、分支与最近提交，先确认 B1 的文档门禁、提交和 GitHub Actions；本轮审查结果见独立报告。`444bbde` 是 B1 基线，`315b535` 是此前热重载历史切片，禁止回退或覆盖历史。
3. 若确有新改动或失败需要验证，使用以下入口；本轮已执行结果以重建切片记录为准，不无故重跑全部历史实验：

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

## 7. A 与 B1 已实现，下一切片是候选语料交接

**业务问题**：目标仍是前端可调切片、后续上传文档。A 把“现有磁盘语料 → 构建索引”变成请求加轮询；B1 把“配置文档 → 候选语料”任务化。两者尚未接成候选选择与切换流程，不能把当前后端能力描述为完整上传或一键换切片。

按两个垂直切片推进，A 的实现与证据已独立记录：

### 切片 A：索引重建任务化（语料已在磁盘上）

已实现并完成本地验收：202 + Location、持久化任务查询、线程构建、同 artifact root 的 API 文件锁、真实批次进度、显式调用次数上限、重启可读及中断失败恢复。成功只生成或复用已验证 artifact，绝不自动激活或 reload。接口、文件、命令、故障证据和准确限制统一见[切片 A 报告](../verification/index-rebuild-tasks-2026-09-19/README.md)。

该验收使用真实本机 HTTP 和合成 Embedding 服务，没有真实供应方调用；尚无可信耗时预测，接口明确返回 null，不延用历史“3015 chunks 约 50 秒”作为承诺。下一轮不得自动发起付费演练、恢复旧任务或清理失败候选目录。

### 切片 B1：语料生成任务化（已选方案并实现）

沿用 Python 调 Node，复用唯一的切片模块，避免两套实现漂移。已经分离文档切片与评测配额：B1 不接 `perDomain`、对话或评估集。接口、参数上限、失败码、父进程死亡修复、逐字节对拍和真实 HTTP 证据统一见 [B1 报告](../verification/corpus-build-tasks-2026-09-19/README.md)。本地源码需要 Node，现有 Docker 镜像尚未集成该运行时。

下一步先完成本切片 diff 阅读，再明确候选语料的选择与索引构建契约：只能选择已成功、摘要匹配的候选；保持现有语料/索引身份保护；切换失败保留旧快照；以合成数据和本地替身完成验收。未明确切换操作前不自动修改 knowledge_path、active 指针或运行付费建库。

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
