# Support Copilot 当前状态

> 更新时间：2026-09-18
> 状态分类：当前工作区事实（已提交，工作树 clean）

## 最新：评估集扩容到 76 题，融合实验在 40 题上重测（2026-09-18）

针对「11 道可评估题无法验证任何检索改动」这一卡点，把 development 从 11 道扩到 40 道，并在新集上重跑融合实验。仅消耗 40 次 embedding 调用、0 次生成调用，未推送。

### 1. 扩展集：同规则、同语料、零重叠

`docs/verification/retrieval-cases-expanded-2026-09-18/` 冻结 **76 题**（development 40 / holdout 36），每 domain 由 6 题扩到 25 题。

- 生成脚本 `scripts/benchmark/expand-quality-inputs.mjs`（11 项测试）：与 `quality-input-audit-2026-09-10` **同一份归档、同一套筛选规则、同一套输入渲染**，只把每 domain 配额从 6 提高到 25。
- **规则自检**：用原配额 6 重跑必须精确复现现有 24 个 Doc2Dial 候选（id 与渲染后的 `input` 逐字一致），不通过即失败。渲染也沿用「DMV 不猜辖区」的修订。
- 与旧集**零文档重叠**：旧实验用过的 32 个对话与对应文档全部排除。
- **语料与 artifact 完全复用**（488 文档 / 1564 片段 / artifact `2ecf19dd…`），扩容不需要重建索引，只花新题 query 的 embedding。
- 可用上限：dmv 51、ssa 77、studentaid 50、va 95（manifest 记录）。
- 未审计：`audit.label=PENDING`，因此只用于**相对比较**，不产出答案性或质量结论。

### 2. 新集基线（development 40 题，纯向量）

| 指标 | 扩展集 40 题 | 旧集 11 题 |
| --- | ---: | ---: |
| gold@1 | 50.0%（20/40） | 54.5% |
| gold@3 | **80.0%（32/40）** | 72.7% |
| MRR | 0.625 | 0.636 |
| 空结果 | 0 | 0 |

两集指标接近，说明同分布，扩展集可用。全库排名（`gold-rank.json`）：recall@3 32/40、recall@6 36/40、**recall@10 37/40**。

### 3. 新集暴露了旧集看不到的召回失败

旧集 11 题的 gold 全部落在前 6 名，因此当时的结论是「召回够用、只差排序」。40 题里有 **3 题 gold 在 10 名之外**（`qa-4fee4f11…` 第 97 名 0.5529、`qa-016cf084…` 第 35 名、`qa-5a743ace…` 第 12 名），另有多道排在 4–8 名。**排序与召回两个问题同时存在**：排名靠后的题无法靠重排救回。

限制：扩展题未审计，无法区分「检索真失败」与「gold 标注本身不匹配」，这是未审计集的代价。

### 4. 融合实验重测：效应更强，但仍不显著

零调用、复用同一批缓存向量：

| 配置 | gold@1 | gold@3 | MRR |
| --- | ---: | ---: | ---: |
| vector-only（基线） | 20/40 | 32/40 | 0.625 |
| bm25-only | 20/40 | 30/40 | 0.608 |
| **rrf-equal k=60（主对比）** | **31/40** | **36/40** | **0.829** |
| rrf-bm25x0.5 k=60 | 32/40 | 37/40 | 0.854 |
| rrf-bm25x2 k=60 | 28/40 | 35/40 | 0.783 |

主对比 vs 纯向量：**改善 5 题、退化 1 题**，不一致题数首次达到 6（样本量足以支撑结论），McNemar 精确检验 **p = 0.2188**——方向一致、比 11 题时（2 升 1 降 / p = 1.0）更强，**但仍未跨过显著门槛**。

两个必须记住的点：

1. 11 题时「所有参数结果相同」是小样本假象；40 题上参数确实有别（`bm25x0.5` 最好、`bm25x2` 最差）。
2. 因此**不能选 `bm25x0.5`**：它是在这 40 题上挑出来的。只有上一轮先行固定的主对比（等权 k=60）有资格被独立验证。

### 5. holdout 仍然封存

holdout 36 题**未运行**。它是一次性资源，只能验证事先固定的方案（当前只有等权 k=60 满足）。用 holdout 验证 `bm25x0.5` 之类的扫描结果属于调参后再验证，会污染唯一干净的数据集；要走这一步需要先确认这是**不可逆消耗**。

### 6. 下一步

1. 决定是否用 holdout 验证已固定的等权融合方案。
2. 改进机制：简单 RRF 无法抑制单边错误（1 题退化在所有参数下都存在），这比继续堆题目更有价值。
3. 40 题上仍有 3 题排在 10 名之外，属切片/query 构造问题，重排救不回。

### 7. 切片参数化完成：切片粒度不是瓶颈（同日后续）

把切片参数从硬编码改成命令行可配，并用它做了第一个真正的单变量实验。消耗：3015 次文档 embedding（建独立索引）+ 40 次 query embedding，0 次生成调用。

- **参数化**：`scripts/benchmark/prepare-doc2dial.mjs` 新增 `--window/--stride/--per-domain/--output/--verify-against`（12 项测试）；`build_benchmark_index.py` 改为从 corpus 目录的 `chunking.json` 读切片身份，缺文件 fail-closed，`index-build.json` 记录相对路径（7 项测试）。
- **自检**：默认参数配 `--verify-against` 必须逐字段复现冻结产物（`corpus.json`/`chunk-map.json`/`cases.json`/`protocol.json`，除 `frozen_at`）——已通过，所以旧证据与旧 artifact 继续有效。
- **切片身份由参数唯一决定**：`doc2dial-codepoints-{window}-{stride}-v1`，默认值正好等于历史值 `…-2000-1600-v1`；步长大于窗口直接拒绝（会静默丢内容）。
- **隔离**：新 artifact 建在 `.local/chunking-variants/1000-800/artifacts`，active artifact 仍是 `2ecf19dd…`，生产检索配置未动。
- **实验结果**（同一批 40 题）：片段数 1564 → **3015**（约翻倍，建索引 49.6 秒），**gold@3 不变（32/40）**、gold@1 20→22、MRR 0.625→0.667，逐题 8 好 7 坏（净 +1，p≈1.0）。**更细的切片没有带来可测量的质量收益**。
- **关键细节**：1000/800 让平均 gold 片段数从 3.25 升到 6.40（命中机会几乎翻倍），但 gold@3 一点没变——说明瓶颈是排序而不是“文档切得太粗”。
- **融合在两个切片下都提升**（2000/1600：32→36；1000/800：32→37），说明融合不依赖切片粒度；但两者都未显著（p=0.2188 / 0.1797），仍不改生产。
- **附带修复**：本轮真实犯过一次“评分时用错语料”，报出 `gold@1 0/40` 这种假结论。`retrieval-eval.mjs` 现在会统计候选 chunk_id 与语料的匹配率，**不匹配超过 10% 直接报错**，并在 summary 输出 `corpusMismatchRate`（12 项测试）。

证据：`docs/verification/chunking-1000-800-2026-09-18/`（语料 4.8MB 未入库，可由命令重建）。

### 8. 索引版本清单与热重载：切片可以在不重启的的情况下切换

新增两个端点（都需内部服务鉴权）：

- `GET /knowledge/index/versions`：只读列出 artifact root 下的所有版本、active/previous、每个版本的切片身份与行数、进程实际加载的语料身份。
- `POST /knowledge/index/reload`：重载语料与向量索引，默认关闭（`KNOWLEDGE_INDEX_MUTATION_ENABLED`）。

**关键架构决策：`chunking_version` 从校验字段降级为观测字段。**

- 起因：第一版写端点（activate/rollback）测试全绿，但在真实的两套切片上一跑就失败（`artifact-incompatible`）。根因是 `_require_compatible` 校验的字段与 `_artifact_id` 是同一组——两个能互相切换的 artifact 根本不存在。
- 修正后的认识：该保护的是“索引每一行是不是它声称的那块内容”，这由 `corpus_checksum` + 逐行 `(chunk_id, content_checksum)` 对齐保证；`chunking_version` 只是描述“这份语料怎么切的”的**标签**。而且**换切片必然换语料**，所以“只换索引不动语料”的 activate 在语义上本就是错的。
- 改动：`_require_compatible` 不再比对 chunking_version；`_artifact_id` 在校验落盘 artifact 时改用 **manifest 自己声明的值**重算 id；新增 `RetrievalState(corpus, live_index)` 快照，检索只取一次引用，`reload_index()` 先构建新快照、成功后原子替换。
- **未改动**：`evaluation/live_verifier.py` 仍要求 artifact 的 chunking_version 与记录一致——那是评测取证，不是运行时保护。

**真实证据**（`probe-reload.json`，真实 3.8MB/4.8MB 语料与真实 artifact）：启动 1564 chunks；无变化 reload 200；**只换语料不换索引 409 且进程仍是 1564 chunks**；换齐后 reload **200、1686ms、变 3015 chunks**。

运维顺序（不能乱）：换语料文件 → 用**新语料**建索引并移 active 指针（用运行中进程的旧 store 会被正确拒绝）→ `POST /knowledge/index/reload`。

测试：`tests/test_index_versions.py` 16 项（含“同语料不同标签可切”“**不同语料仍被拒**”“只换一半 409 且旧快照不变”“重载后 search 命中新语料正文”）。全量 Python 375 项。

证据：`docs/verification/index-versions-2026-09-18/`。**前端与 Java 接入尚未开始**：重建任务化、转发与面板是下一片。

## 前一阶段：比较协议预注册、门禁回归修复与离线检索评测（2026-09-11）

同一轮完成三件事：预注册修正后的 development 比较方案，修复固化提交在文档门禁上暴露的回归，并建立零费用的离线检索评测。均未执行付费调用、未推送。

### 1. 修正后 development 比较已预注册

`docs/verification/development-comparison-2026-09-11/` 冻结了 query 修复后的第一次真实 development 复测方案，**尚未执行任何付费调用**。这一片切片解决的问题：旧 13 题诊断已占用一次性 development claim，同一数据集不能直接重跑，也不允许删除或绕过 claim。

- 机制：`scripts/benchmark/run-isolated.mjs` 新增 `--comparison <protocol.json>` 模式，复用原隔离运行器；在付费调用前逐项校验协议版本、run ID、冻结 cases SHA、holdout=0、humanInputReview=PENDING、qualityScore=null、预算完全一致、旧 claim SHA-256、旧 run manifest、预期源码哈希，并保证每个 comparisonId 只运行一次。
- 绑定：旧 claim SHA-256 `8476732b…`、base run `development-live-diagnostic-20260910`、cases SHA `7e789893…`、预期源码 `workflow.py` / `grounded_reply_policy.py` / `response_language.py`。
- 单一变量：仅 `_build_query` 由正文前 180 字符改为完整已校验标题与正文；模型、聊天协议、提示词、知识 corpus、向量 artifact 与超时预算冻结。
- 离线验证：`node --test scripts/benchmark/comparison-protocol.test.mjs` 8 项契约测试通过；`node scripts/benchmark/isolated-runner.test.mjs` 11 项继续通过；预检 `preflight-development-comparison-20260911` 为 `PREPARED_NO_CALLS`、0 次 provider 操作、`evidenceKind=PREPARATION_UNREVIEWED`，确认 live / `chat_completions` / 1564×1024 artifact。
- 执行状态：**阻塞**（2026-09-17）。配置与源码绑定全部通过（三处源码哈希与协议一致），但执行前探测发现 chat 端点持续返回 HTTP 503，而模型列表与 embedding 端点正常。立即执行会让 13 题生成全部失败并消耗一次性 claim，因此未执行；claim 未写入、无生成费用。证据与恢复步骤见 `docs/verification/development-comparison-2026-09-11/EXECUTION-BLOCKED.md`。
- 下一步：用 `node scripts/benchmark/provider-probe.mjs` 确认 READY 后再执行 `--execute --comparison`；执行后不得覆盖 base run。质量分数仍为 `null`，需真人输入确认与回答事实审核。

### 2. 固化暴露并修复的门禁回归

这些失败在固化前不会出现，因为验证器只检查 Git 追踪的文件，而受影响的文档与账本当时未被追踪。

| 回归 | 根因 | 修复（提交） |
| --- | --- | --- |
| `verify-docs.sh` 的 tracked-copy 树不一致 | `.gitignore` 新增 `.omo/` 后，两个历史 task-10 账本仍被追踪，fixture 重建时被忽略 | 从索引移除两个文件，磁盘内容保留（`147fb36`）|
| 335 处文档链接失败 | 固化把含本机绝对路径与 `:line` 后缀的证据文档纳入追踪 | 改为仓库相对链接，行号保留在链接文本（`896446a`）|
| `QualityReportsController` 缺少类级映射 | 完整路径写在方法上，契约要求每个 controller 一个类级 `@RequestMapping` 与字面 base path | 改为类级映射 + `@GetMapping`，对外 URL 不变（`29a17ca`）|
| tracked-only 检出中 404 处链接目标缺失 | 文档链接到有意不入库的本地派生产物（trials、corpus、workspace 快照）| 验证器允许被 `.gitignore` 排除的目标缺失，指向已发布文件的缺失链接、错误锚点、绝对路径与逃逸路径仍失败（`fa9979d`）|

修复后证据：`./scripts/verify-docs.sh --static` 通过（tracked-copy 树一致、16 项文档契约测试、静态契约）；Java `./gradlew test` 318 tests / 0 failures / 14 skipped；AI `pytest -q` 324 passed；benchmark Node 契约测试 19 passed。未运行 `verify-docs.sh --full`（需要重新安装依赖并启动本地服务，与本次改动无关），因此不声称端到端 smoke 通过。

### 3. 离线检索评测与修复前基线

在它之前，“检索好不好”只能通过生成模型的成败回推，无法区分“没检索到”“检索到但排序靠后”“检索到但模型没用”。现在可离线、零调用、可复现地回答。

- 工具：`scripts/benchmark/retrieval-eval.mjs`，只读 `<runDir>/results.json`、评估集与语料，输出 gold@1/@3/@10、MRR、按领域汇总、逐题明细，以及 query 与候选的重复度诊断；配套 10 项契约测试通过。
- 口径：gold 文档取自 `cases.json` 的 `source.document_id`，通过语料 `source_uri` 的 anchor 匹配到 `corpus.json` 的 `document_id`；同一文档被切成多个片段时命中任一片段即算命中。
- 修复前基线（目录 `docs/verification/retrieval-eval-2026-09-11/`）：26 题计划 / 13 题已执行 / 11 题可评估；gold@1、@3、@10 均为 0，MRR 0.000；13 题共用 1 条 query、返回 1 组相同候选。结论与独立 Python 复核一致。
- 限制：11 题样本量小，只能用于同一语料、同一评估集下的相对比较；gold 命中不代表片段包含答案，也不代表模型正确使用；本工具不替代真人回答审核。
- 用途：比较协议执行后对新的运行目录重跑本工具并 `--baseline` 指向旧报告，即得到完整对照；后续检索改动先在离线评测上比较，再决定是否花真实调用。

### 4. 检索-only 基线：修复后真实召回 72.7%

旧运行的 0% 召回无法区分“query 构造错”“检索算法差”“切片不合适”。新增 `evaluation/retrieval_only.py`后可以只花 embedding 就把这三者分开：它不修改任何生产检索代码，逐步复现 `LiveVectorIndex.search` 的判定（范围过滤 → 余弦 → 阈值 → top_n → 类别重排 → top_k），并由 8 项测试（`tests/test_retrieval_only.py`）用同一份输入断言两条路径给出完全相同的候选与分数。

证据目录 `docs/verification/retrieval-only-2026-09-17/`（13 题、13 次 embedding 调用、**0 次生成调用**、未使用 chat 端点、不消耗 comparison claim）：

| 指标 | 旧运行（query 被截断） | 检索-only |
| --- | ---: | ---: |
| gold@1 | — | 54.5%（6/11） |
| gold@3 | 0.0%（0/11） | **72.7%（8/11）** |
| MRR | 0.000 | **0.636** |
| 去重 query / 候选集合 | 1 / 1 | 13 / 13 |
| 空结果题数 | — | 0 |

按领域：dmv 3/3、studentaid 2/2、ssa 2/3、va 1/3。`va` 是最弱切片。结论：**检索本身没坏，旧运行的 0% 来自 query 截断**。

限制：这是检索指标，不含生成、fallback、引用与人工审核；gold 是文档级匹配，chunk 级统计会低估；语料是归档文档，不是真实客服知识库；development 13 题作者已见过输出，holdout 仍未使用。`query-vectors.json`（341KB）不入库，可在同一批向量上零调用复现排序与阈值实验。

**排序诊断（零调用）**：新增 `evaluation/gold_rank.py`（9 项测试）用缓存向量与 artifact 矩阵算 gold 的全库排名（见 `docs/verification/retrieval-only-2026-09-17/GOLD-RANK-DIAGNOSIS.md`）。3 道未命中题排第 4、6、6 名，全库 recall@6 = 11/11；即**召回已经够用，瓶颈在排序精度与 top_k 截断**。因此下一步优先级是重排与融合，而不是换 embedding；`top_k` 调大是成本决策，不得记作质量改进。

**融合实验（零调用）**：新增 `evaluation/hybrid_retrieval.py`（13 项测试），在同一批题目上比较纯向量与 BM25 的 RRF 融合，见 `docs/verification/retrieval-only-2026-09-17/HYBRID-ANALYSIS.md`。结果：gold@3 8/11 → 9/11、gold@1 6/11 → 9/11、MRR 0.636 → 0.818，但改善 2 题的同时退化 1 题，McNemar 精确检验 **p = 1.0**。因此**不得声称融合已验证有效，也不得据此改生产检索**；参数（RRF k、BM25 权重）在这批题上不影响命中结果，逐题核对确认并非参数未生效。已确认的机制：简单 RRF 无法抑制单边错误（一题向量排第 2、BM25 排第 81，融合后掉到第 15，且全部参数下都存在）；`bm25-only` 的 gold@1（8/11）高于纯向量（6/11），提示当前 query 的字面词重叠在起很大作用。**当前最高优先级是先扩大评估集**，否则每条检索改动都会重复得到“不显著”。

### 5. Provider 前置检查与执行阻塞

新增 `scripts/benchmark/provider-probe.mjs`（8 项契约测试）：只做 3 次最小探测（模型列表、极短补全、极短嵌入），不输出密钥，给出 `READY`/`BLOCKED`、端点 sha256 与检查时间。它用于在执行一次性付费运行之前判断端点是否真实可用——`claim` 一经写入不可重跑，不能靠配置完整度代替真实探测。

2026-09-17 实测：`GET /models` 200（17 个模型中包含目标 `gpt-5.6-luna`）、`POST /embeddings` 200、`POST /chat/completions` **503**；12 分钟轮询 12 次仍为 503，另一次连接错误。因此比较运行未执行，未写入 claim，未产生生成费用。

## 前一阶段：提交前工作树已固化（2026-09-11）

此前 342 个待提交路径（94 个修改 + 未跟踪目录下的源码、测试、文档与截图）已按主题提交到 `master`，工作树 clean，本地领先 `origin/master` 但**未推送**。固化提交范围为 `68b3aa0`..`b9215a6`，提交边界：

| 提交 | 主题 | 文件数 |
| --- | --- | --- |
| `68b3aa0` | chore(git): 忽略本地运行产物与大型证据派生物 | 2 |
| `2e4a0ad` | feat(workspace): 企业工单工作台与运行加固 | 154 |
| `ca9cb6e` | feat(quality): 质量报告中心 | 25 |
| `31b65ae` | feat(ai): 证据约束回复、语言边界与完整检索上下文 | 74 |
| `3c8e478` | chore(pilot): 容器与运维加固 | 17 |
| `c923d0e` | docs: 状态、路线与证据记录 | 70 |
| `b9215a6` | docs: 记录本次提交边界 | 2 |

本表记录 2026-09-11 固化时点；此后如果只在本文档上追加修订，HEAD 会随文档更新前进，但提交边界事实不变，以 `git log` 为准。

HEAD 上重跑验证：AI 服务 `pytest -q` 324 passed；Java `./gradlew test` 318 tests / 14 个 MySQL 容器用例跳过 / 0 failures；Web `npm test` 108 passed / 3 skipped；前端 `lint` 与生产 `build` 通过。

限制：提交按主题固化而非逐个 hunk 拆分，`apps/support-copilot-web/src/services/api.ts`、`App.tsx` 与 `QualityView` 之间存在跨提交交叉依赖，中间提交单独 checkout 不保证可编译，只有 HEAD 经过上述验证。MySQL 实库、浏览器 E2E、Compose operations gate 和修正后的真实 live 复测未在本次固化中重跑。`.gitignore` 现在忽略 `.local/`、`.omo/` 与 `docs/verification` 下的 JSON、截图、`run-*/corpus` 等派生产物，这些文件保留在磁盘但未入库。

以下各节是本次固化前的历史记录，其中"HEAD 仍为 `4df3bf4`、dirty、未提交"等描述只对当时的工作树成立。

## 前一阶段：检索上下文截断已修复，离线回归通过

已按用户指令修改`AnalysisWorkflow._build_query`：完整保留已通过TicketInput长度校验的标题与正文，去掉正文前180字符截断。唯一生产代码改动见[本轮diff与交付](verification/query-context-fix-2026-09-10/README.md)。19项新增回归修改前17失败/2通过、修改后19通过；AI模块完整324项通过。13条冻结真实输入经离线HTTP工作流产生13条不同query，历史上下文与当前请求均保留；超过4000字符正文仍返回422。测试响应不计入真实业务结果。

本轮无新模型/Embedding调用，无部署或工作台重启。尚未测得修复后的检索命中、回答质量、延迟或费用改善，旧13题真实诊断与run-1原样保留。完整输入上限为240字符标题/4000字符正文；查询加分隔最多4241个Python code point，外发Embedding仍经过原脱敏边界。输入更长可能影响成本、延迟及相关性，须独立真实development复测验证。

当时 HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`，master、dirty、未提交；该状态已于 2026-09-11 固化为 `68b3aa0`..`b9215a6`。修复前后源码、冻结材料及本轮明确改动边界由新交付验证；旧验证器绑定旧工作树，现会因授权源码/文档改变失败，原件保留。下一步在本轮diff审阅后预注册修正后的development比较，不删除claim或覆盖旧批次。人工参考/输出审核仍待完成，质量分数仍为空。

## 前一阶段：13题真实诊断完成，确认检索输入截断缺陷

用户明确授权“先做真实诊断，不计算人工质量分数”。已实现独立运行编号/端口/文件H2/JAR、源码和artifact快照、provider操作账本、一次性执行与失败停止保护，并完成固定13题development、并发1的真实Java→Python→Embedding/生成→Java保存/读回；即时及Java重启后完整对象核对均通过。真实调用、结果、延迟与证据以[本轮交付](verification/isolated-runner-2026-09-10/README.md)和[独立run](verification/quality-runs/development-live-diagnostic-20260910/RESULTS.md)为准。没有使用演示工单或mock模型，未重跑旧run-1，holdout未调用。

**本轮正常live产出为0，所有13题最终为证据不足降级。** 实际13条检索query与候选列表完全相同：生产query构造只使用正文前180字符，新输入统一说明占满该前缀，业务上下文未进入检索。详见[运行定位](verification/quality-runs/development-live-diagnostic-20260910/DIAGNOSIS.md)。生成模型仍收到完整工单正文；本轮结果保留为真实故障诊断，不能作为正常业务检索后的质量或代表性性能基线。尚未修改此生产逻辑或测量修正收益。

人工输入确认/输出审核仍未完成，准确率、解决率、节省工时与费用未知。质量页仍显示此前22/96冻结报告，本轮13题未接入页面；知识库正文网页增删改和评测人审网页入口仍未实现，当前真实操作说明见[OPERATIONS](verification/isolated-runner-2026-09-10/OPERATIONS.md)。

HEAD仍为`4df3bf44907c34318132496929bad4a3974ad88b`，master、dirty、未提交/推送/部署。当前交付包含独立运行源码hash及全部旧文件保护核对，不以相同HEAD替代工作树证据。下一优先切片是检索query上下文保留的离线回归与最小修复；复测要另立development实验，不覆盖本轮、不冒充holdout、不能直接重跑旧runner凑成功。

## 前一阶段：质量证据页与报告校验

用户已授权直接推进产品优化。已实现独立的报告导出、受保护的 `/api/quality-reports` 和质量证据页：并列读取冻结的合成回归与公开文档业务基准，明确区分正常 live、证据不足、超时和错误，显示人工审核未完成、真实分母、并发耗时及全部非正常产出案例。旧 live 指标的 Hit@K/引用覆盖误标已修正；新报告出错时不会显示旧 mock 作为替代。详细修改、验证、失败记录和启动配置以 [本轮交付](verification/product-quality-center-2026-09-10/README.md) 为准。

本轮没有新模型或 Embedding 调用，没有新增人工审核或回答准确率结果。旧 run-1 与输入审计保留；旧审计的整工作区不变门禁现在会因已授权的产品源码改动失败，未修改它来制造通过。本轮使用新的明确修改范围校验并逐项验证旧冻结文件哈希。HEAD 仍为 `4df3bf44907c34318132496929bad4a3974ad88b`，master、dirty、未提交/推送/部署。下一步仍是独立实验运行器与人工确认后的 development 测量；质量页接入已完成，不能据此宣称模型质量提高。

## 前一阶段：质量输入与参考标准离线审计

已完成本轮离线切片，详细事实以 [质量输入审计报告](verification/quality-input-audit-2026-09-10/README.md) 为准。先保存筛选/评分协议，再固定未参加旧模型实验的候选，保留上下文、来源与排除清单，修订模糊参考并生成开发/保留集合。审计捕获并纠正了 DMV 机构路由的无依据州别假设；初版协议和候选原件保留追溯。全部标签仍为 AI 建议，人工确认 0，新模型/Embedding 调用 0，回答准确率、客户解决率、节省工时均未测。

定向离线测试与来源/跨度/泄漏/重复/冻结保护通过，人工门禁按预期阻断；当前 HEAD 仍为 `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty，无提交/推送/部署。旧基准摘要、157 份运行快照与原始记录再次核对，旧 run-1 和业务源码未改。下一步是作者审阅本轮输入与参考 diff、真人确认标签，然后实现独立运行编号/目录/数据库/端口后安排有上限的 development 测量；holdout 在比较方案冻结前不用于调参。质量页尚未接入新材料。

## 前一阶段：业务链路性能与公开参考对照

用户明确需要回答质量及处理耗时/稳定性。已完成 [业务基准](verification/business-benchmark-2026-09-10/README.md)：从官方 Doc2Dial 人工构建的对话测试数据固定抽样 32 题，使用全部 488 份文档、1564 个真实向量分块，在隔离 Java/Python/H2 实例按 1/2/4 并发运行 96 次分析。96/96 结果即时读回及 Java 重启后读回匹配；正常 live 共 64 次，证据不足 14 次，生成读取超时 18 次。单并发质量主组指定参考文档命中 19/32、跨度覆盖均值 49.86%；这不是事实正确率或客户问题解决率。数据含寒暄/歧义和 fuzzy 标注，因此尚不能作为业务质量验收集。详细数字只维护于报告和 summary.json。

本轮使用生产工作流及专用检索记录入口，模型与超时预算沿用既有配置；只切换隔离基准的知识库，不改变原工作台。基础 HEAD 仍为 4df3bf4、dirty，无提交/推送/部署。后续先修质量集业务意图/上下文筛选，再核查检索遗漏与生成超时，不将吞吐、词语 F1 或 HTTP 200 数量当作已解决业务问题。

## 当前结论：2026-09-10 AI 质量修复

用户已选择公开产品文档与真实公开问题。[20 题公开数据实验](verification/public-rag-experiment-2026-09-10/README.md) 已实际执行：BM25 与真实向量检索各 20 次生成，另有 5 次 AI 候选证据对照；共 37 次结构合格返回、8 次读取超时，失败全部保留。逐题原始输出、证据与运行源码均已冻结。向量上下文 60 个位置中 7 个为纯导航，初审也发现超出证据的推断；没有将运行成功率包装成准确率。人工审核仍为 0，公开题已用于开发诊断，不能当作独立盲测。原始来源见 [试标注材料](verification/public-rag-pilot-2026-09-10/README.md)；此前“模型调用 0”仅描述采集阶段。当前实验复用 Python provider，但使用隔离检索，未覆盖 Java/最终回复规则，未替换工作台知识库或下方 22 例合成回归报告。下一步以冻结问题修复纯导航分块，再用独立参考证据评审回答蕴含，不继续逐题教学阻挡实验。

已实现并验证：来源与主题绑定的退款/隐私/同步回复约束；证据充分性与受限回复的明确契约；无证据及外部错误的谨慎降级；中英文输入与回复评估；原始候选与最终证据区分；安全超时/连接诊断；数据集违规模式与语言门禁、运行时源码指纹、明确 p95 算法。前端知识依据只计算实际采用片段，未采用候选保留可查。

**真实 AI 整体门禁仍为 blocked/partial。** 最终冻结源码的 22 例两轮分别为 16 live + 4 正确拒答 + 2 超时、17 live + 3 正确拒答 + 2 超时，各 20/22 机器正确。原始最终 4 例为 3 live + 1 超时。最终轮未再出现此前的退款结构矛盾，但连接/读取超时仍存在；人工审核尚未完成，publishable=false。不能把修复前一次原始 4/4 或安全兜底写成当前完整通过。

本轮详细事实与所有失败只保留在 [AI 质量修复报告](verification/ai-quality-fixes-2026-09-10/README.md) 和 [完整运行结果](verification/ai-quality-fixes-2026-09-10/RESULTS.md)。Python 288 项、mock 31 案例通过；Web 88 项通过/3 项原有显式跳过，构建通过。费用缺少实际网关单价，仍未核算。候选召回成功、指定语言/话术检查不等于全部事实正确或供应端稳定。

HEAD 仍为 `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty；本轮无提交、推送或部署。当前源码由报告 runtime hash 与快照绑定；未修改凭据、模型、知识 corpus 或超时/重试预算。

用户随后明确要求工作台使用真实模型。当前 `http://127.0.0.1:18173/` 已以 live 模式启动，保留持久化 H2；浏览器新建合成工单并发起的一次分析已返回 `live/SUCCEEDED`、`gpt-5.6-luna`、VECTOR 检索与有效知识引用，保存到分析历史。启动器默认仍为 mock，重启使用真实模型时必须显式传入 `AI_MODE=live`。验证证据见 [工作台 live 切换记录](verification/live-workbench-2026-09-10/README.md)。这次单工单成功不改变上方整体质量门禁结论。

质量页此前仍独立读取默认 mock 报告，现已通过 `EVALUATION_REPORT_PATH` 指向 final-2 的真实 22 例报告；API 与浏览器均显示 live、模型名和未通过门禁。两个配置相互独立，完整重启命令见根 README。此次没有重新调用模型、修改原始评估结果或完成人工审核。详情与剩余指标展示限制见 [质量页配置验证](verification/live-quality-page-2026-09-10/README.md)。以下内容为历史阶段，不能覆盖上述当前结论。

## 前一阶段：2026-09-09 真实 AI 基线

用户已明确授权并执行真实模型与 Embedding 评估。修复Qwen输入协议与模型自由分类两项根因，冻结16个合成案例连续两轮各16/16机器通过（13个live成功、3个预期无证据降级）。Python当前233项通过，mock31案例通过。**人工事实审核仍为0/32，publishable=false；自动语义复核已发现一处核验前引用退款时效的政策冲突，正式质量门禁尚未通过。**

本轮唯一详细来源为[真实AI基线报告](verification/live-baseline-2026-09-09/README.md)，含原始失败、最终报告、真实向量指标、源码快照和[人工审核材料](verification/live-baseline-2026-09-09/REVIEW.md)。费用因实际网关单价未确认而保留不可用，不记为0。本地demo预览未切换为live；新的raw-text-v1向量索引已构建激活，旧索引保留。

基础HEAD仍为`4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty，未提交/推送/部署。下面企业工作台验收是本次AI改动前的阶段证据；其AI201项与旧源码摘要不能覆盖当前233项及新模型/Embedding实现。

## 前一阶段：2026-09-09 企业工作台与运行加固

基础 HEAD 仍为 `4df3bf44907c34318132496929bad4a3974ad88b`，分支 `master`，工作树有未提交改动。用户已明确授权直接重构；本轮按实际实现、回归和恢复演练推进。原有 Pilot 与基础设施修改保留。

已实现并验证：创建/领取/编辑/备注/分析/审核/解决/关闭闭环；全量 SLA/优先级排序、负责人筛选和匹配总数；全量快捷查找、真实工单活动历史；实际 SLA 截止时间、UTC 创建/解决趋势与分析耗时；文件 H2 持久化、SHA-256 备份恢复与 H2 互斥文件锁。Java 273 项零跳过通过（其中 MySQL 14 项），Web 85 项通过/3 项显式契约测试跳过，浏览器 E2E 21 项通过，AI 201 项及 mock 固定基线 31 案例通过。20 个界面组合无 axe 违规、页面溢出或运行错误。

当前唯一详细验收来源为 [企业工作台验收记录](enterprise-workspace/VERIFICATION.md)，其中包含命令、当前源码摘要、浏览器和恢复证据，以及独立复审结论。本地入口 `./scripts/dev-workspace.sh` 默认使用真实 Java/Python 服务、确定性 mock AI 和重启保留的文件 H2。未提交、未推送、未上线；没有重新调用 live 模型或宣称真实生产质量。

下方 09-06 内容是历史快照，其“核心链路未改”“MySQL 跳过”等描述不能覆盖本轮事实。生产 SSO、多租户、真实客户发送、live 人工质量基线、镜像发布和容量验收仍是独立限制。

## 09-06 状态快照（历史）

当前分支为 `master`，HEAD 为 `4df3bf44907c34318132496929bad4a3974ad88b`。工作树不干净，未提交改动集中在 Pilot、Docker、Compose、备份恢复、容器测试、协作规则和本交接文档；核心分析链路文件没有出现在未提交列表中。

本轮先完成了理解恢复：作者已经复述一次分析请求的版本保护、无知识证据降级、Python 服务不可用降级和版本冲突响应；随后启动 Docker Desktop，并在当前 dirty 工作树上完成问题一的 MySQL focused 测试和真实 HTTP 手工验证。其后工作树又加入了 Pilot、镜像和恢复流程的测试与修复，不能把历史阶段的“只改测试”描述当作当前工作树总览。

2026-09-06 的对抗式审查发现的三个阻断问题已修复并重新验证：AI Alpine 镜像的 `setpriv` pin 更新为仓库实际可用的 `2.42.3-r1`；`pilot-restore.sh` 将 manifest 中校验过的 MySQL 镜像和调用方提供的 OIDC 镜像传入每次 Compose 调用；显式启用的四个 MySQL Testcontainers 测试类不再使用 `disabledWithoutDocker=true`，Docker 不可用时会失败而不是静默跳过。当前仍是 dirty 工作树，未创建提交。

## 已有代码证据

以下是当前源码中存在的能力。代码存在不等于本轮已运行验证：

- React 在 `useTicketWorkflow.ts` 中记录选中的工单、正在分析的工单 ID，并调用 `POST /api/tickets/{id}/analyze`。
- Java 由 `TicketController` 接收请求，经 `AnalysisCommandService` 的幂等包装进入 `AnalysisService`。
- Java 读取完整工单，保存 `sourceTicketVersion` 和 `traceId`，通过 `AiServiceClient` 携带工单、traceId 和内部服务身份调用 Python。
- Python 的 `/analyze` 经过请求校验、内部服务身份校验和处理截止时间后进入 `AnalysisWorkflow`，返回结构化分析结果。
- Java 在 AI 返回后重新读取工单并检查版本；版本一致时在短事务中保存分析、更新工单并写入审计事件。
- 无证据、已命名的外部 AI 依赖故障和结构化响应故障拥有明确的 fallback 或错误语义；未知程序错误不应被伪装成 fallback。
- React 使用运行时响应 Schema，成功后刷新服务端工单，版本冲突时读取最新工单。

## 历史验证证据

这些结果来自其他明确 SHA，不能自动证明当前脏工作树：

- `59903a1e5fad74cf2b792263f735dafe36b8066c`：一次脱敏合成工单的真实 Embedding、向量检索、结构化生成、引用和 Java 持久化成功。
- `be9ac60`、`b856019` 和 `bfb7eee6adae0556399e56457eeed19a158c1d39`：固定 live 数据集仍出现 1 次成功、3 次 `invalid_model_response` fallback；人工审核为 `0/4`，`publishable=false`。
- Task 15 记录了 MySQL parity、部分 Compose 运行、认证边界和重启持久化证据；当前最终加固后的完整 operations gate 没有同源完整成功记录。

## 当前工作区改动

以本轮 `git status --short` 为准，未提交文件涉及：

- `AGENTS.md`、`docs/learning/NEXT_SESSION_HANDOFF_PROMPT.md`。
- `infra/README.md`、`infra/compose.pilot.yml`、`infra/images/`。
- `scripts/pilot-backup.sh`、`scripts/pilot-restore.sh`、`scripts/verify-pilot-operations.sh` 及其测试。
- `services/support-copilot-ai/Dockerfile`。
- `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/config/MySqlProfileIntegrationTests.java`：新增真实 MySQL 下的 HTTP 创建、重启、读取回归测试。
- Pilot Compose、AI、MySQL 和 OIDC 镜像契约测试。
- `.gitignore`：忽略 Python 测试生成的 `__pycache__` 和字节码文件，避免证据工作树混入生成物。

这些改动保留在工作树中，尚未在本轮提交或覆盖。

## blocked/partial

- Task 10 固定 live 评估仍为 `blocked/partial`，结构化输出失败和人工 review 缺口未关闭。
- 当前 Pilot operations gate 受共享宿主磁盘耗尽阻塞；解除条件和停止条件见 `docs/optimizations/ROADMAP.md` 与 `infra/README.md`。
- 严格镜像扫描仍有 HIGH/CRITICAL 结果，不能写成镜像发布或生产安全通过。
- 真实用户 OIDC 登录、token refresh、多租户、分布式幂等、高可用和生产容量仍未完成。
- OpenRAG 的具体项目、版本、部署方式、许可证和职责尚未确认，因此不进入主线。

## 本轮验证边界

2026-09-06 的修复和复审验证，均绑定 HEAD `4df3bf44907c34318132496929bad4a3974ad88b`；工作树仍 dirty，因此这些不是可发布提交证据：

```text
services/support-copilot-ai/.venv/bin/pytest -q \
  tests/test_pilot_compose_contract.py tests/test_pilot_container_images.py \
  tests/test_pilot_ai_image_contract.py tests/test_pilot_mysql_image_contract.py \
  tests/test_pilot_oidc_image_contract.py scripts/tests/test_pilot_backup_restore.py \
  scripts/tests/test_pilot_operations.py                    125 passed
python3 -m compileall -q scripts tests                         passed
bash -n scripts/pilot-backup.sh scripts/pilot-restore.sh \
  scripts/verify-pilot-operations.sh scripts/verify-mysql-persistence.sh passed
docker compose -f infra/compose.pilot.yml config --quiet       passed
SUPPORT_COPILOT_RUN_MYSQL_TESTS=true ./gradlew test \
  --no-daemon --rerun-tasks                                    BUILD SUCCESSFUL
Java JUnit XML summary                                        229 tests, 0 skipped, 0 failures, 0 errors
AI image real amd64 build + configured mock /health             passed, status=up, mode=mock
AI runtime identity                                            user=10001:10001
```

这些证据证明本轮三处修复在当前工作树上可运行；不证明 fresh-volume backup/restore、跨版本回滚或严格镜像安全扫描已完成。独立复审还指出：`SUPPORT_COPILOT_OIDC_IMAGE` 是调用方输入，当前直接 restore 路径只检查非空，未像 MySQL manifest 一样绑定镜像身份；集成 verifier 会在调用前绑定 immutable image ID。该差异保留为 Pilot 运维门禁的后续风险，不把本轮修复扩大为完整发布验收。

残余 MySQL runtime blocker 已定位为验收环境争用，而不是产品或测试断言失败：多个审查任务并发启动 Testcontainers 时出现过 MySQL `ConnectException`，同一轮的单类重跑和当前串行执行均通过。当前 SHA 下使用单一 Gradle 进程、`--max-workers=1`、不与其他 Testcontainers 任务并发的 focused 命令连续执行两次，每次均为 `BUILD SUCCESSFUL`，四个类合计 `11 tests, 0 skipped, 0 failures, 0 errors`。后续 MySQL gate 必须按该串行边界执行；不能把并发审查产生的连接失败归因给业务代码，也不能把 bare `BUILD SUCCESSFUL` 当作测试证据，必须读取 JUnit XML 计数。

2026-09-05 的 Docker 与问题一验证：

```text
Docker Desktop 4.89.0 / Engine 29.7.2 / Compose v5.5.0 / linux-arm64
docker run --rm hello-world                         passed
SUPPORT_COPILOT_RUN_MYSQL_TESTS=true ./gradlew test \
  --tests '*MySqlProfileIntegrationTests.migratedPilotSchemaStartsWithoutDemoTickets' \
  --tests '*MySqlProfileIntegrationTests.largeAnalysisAndReviewPayloadsRoundTripExactlyAfterRestart' \
  --tests '*MySqlProfileIntegrationTests.httpTicketCreateAndReadUseMySqlAfterApplicationRestart' \
  --no-daemon --rerun-tasks                           3 passed, 0 failed, 0 skipped
```

问题一 focused 命令输出为 `3 passed, 0 failed, 0 skipped`；随后问题二 focused 命令输出为 `3 passed, 0 failed, 0 skipped`。新增问题二测试后，完整 API 模块测试集也通过，汇总为 `229 tests, 0 skipped, 0 failures, 0 errors`。当前最后一次完整运行留下的 MySQL 类 JUnit 报告位于 `services/support-copilot-api/build/test-results/test/TEST-com.cyagent.supportcopilot.config.MySqlProfileIntegrationTests.xml`，其中 `tests="6" skipped="0" failures="0" errors="0"`。这些结果证明当前 SHA 下真实 MySQL 8.4.11 容器、Flyway 初始化、首次迁移、第二次迁移 no-op、checksum 篡改拒绝启动、pilot Spring context、空库行为、HTTP 工单创建/读取、应用重启后的工单读取、分析/审核大 payload 读写通过。

另有一次未保留临时环境的网络级手工验证：API 使用真实 Tomcat 端口和 signed synthetic test JWT，`curl` 创建返回 `201`，读取返回 `200`；停止并重启 API 后，用同一数据库读取同一工单仍返回 `200`。首次启动应用 Flyway 执行 v1-v5，重启时报告 schema v5 已是最新且无需迁移。

问题二的当前验收范围是 Flyway 数据库行为，不是业务 API 改动：`migrationChecksumIsStableAndSecondMigrateIsANoOp` 在同一真实 MySQL 数据库上执行两次 `migrate()`，比较两次的版本、checksum、success 和 history 行；`tamperedMigrationHistoryPreventsPilotStartup` 验证篡改已应用 checksum 后应用拒绝启动。问题二 focused 输出为 `3 passed, 0 failed, 0 skipped`。

问题三的 focused 输出为 `1 passed, 0 failed, 0 skipped`：`missingKnowledgeActivePointerColumnPreventsPilotStartup` 在真实 MySQL 中删除 `knowledge_active_release.release_id`，关闭 Flyway 后启动 pilot context，根因为 `SchemaManagementException`。`application-pilot.properties` 仍保持 `spring.jpa.hibernate.ddl-auto=validate`，没有改为 `update`、`create` 或 `create-drop`。

执行过的只读命令包括：

```text
git status --short
git branch --show-current
git log -8 --oneline --decorate
git rev-parse HEAD
```

结果绑定到 HEAD `4df3bf44907c34318132496929bad4a3974ad88b` 和 dirty 工作树。MySQL focused 结果绑定到同一 SHA，但测试报告位于未提交的 build 输出中；该证据证明本次两个指定场景通过，不证明当前工作树完整测试、完整容器 gate 或 live API 通过。
