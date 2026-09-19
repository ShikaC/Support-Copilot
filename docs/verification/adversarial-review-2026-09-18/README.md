# 推送前对抗式审查（2026-09-18）

状态：已实现、已完成各模块回归和本地发布安全门禁（2026-09-19）。本轮已确认问题均已修复，有界复查未发现剩余阻断项。审查没有证明绝对无 bug；结论限于下面的检查范围和明确列出的未验证项。远端推送与 CI 状态需另行核对，不能由本地通过推出。

## 首次远端 CI 与干净检出修复（2026-09-19）

首次已成功将 `093cd52b1d3de1d04959c66d001bd99b3fe2ca52` 正常推送到 `origin/master`，当时本地工作树 clean。GitHub 四条 CI 随后失败，揭示本地已有产物与 runner 工具差异；原失败记录保留：[Python](https://github.com/ShikaC/Support-Copilot/actions/runs/35417277711)、[Java](https://github.com/ShikaC/Support-Copilot/actions/runs/35417277758)、[React](https://github.com/ShikaC/Support-Copilot/actions/runs/35417277715)、[release](https://github.com/ShikaC/Support-Copilot/actions/runs/35417277717)。此前本地 PASS 不能代表这些远端运行通过。

- Python 的查询上下文测试导入了 Git 忽略的历史 `planned-inputs.json`，CI 收集失败。现在把同一份 13 条公开 development 输入逐字节保存到测试 fixture，并记录来源与 SHA-256；完整上下文与 distinct query 断言保留。干净归档还复现了两个 CLI help 测试硬编码 `.venv/bin/python` 的失败，现使用 `sys.executable`。
- Java/React 的报告契约测试读取了未入库的历史报告。改为共用 `tests/fixtures/quality-reports` 中明确标记的人工合成样本，保留正常、证据不足、超时、并发分组、不同 case 计数及未人审语义。Java 仍使用 manifest 固定摘要，另验证有效 JSON 增加一个空格后必须为 `INVALID`；没有更改生产解析器或放宽断言。真实历史报告继续留在原地。
- Release runner 缺少 `rg`，且没有明确安装扫描证据测试需要的 Python/pytest。工作流新增固定 SHA 的 Python 3.11 setup、现有 hash lock 安装及系统 ripgrep 安装。没有关闭任一检查。
- 继续在实际 GNU tar 1.35 上复现快照复制失败：`-C` 在 `-T` 之后会被忽略并退出 2。三处复制命令改为先设置目录再读取文件列表；有效载荷保持一致，GNU tar 下完整 aggregate contract 通过。

四个修复提交：`3820d25`（CI 依赖）、`ff7c079`（Python fixture/解释器）、`1c26356`（共享报告 fixture）、`1ae47ce`（GNU tar 参数顺序）。该阶段代码边界为 `1ae47cec91526ab234fe298315c0e667cd4fbb26`，之后仅更新本说明。

验证使用 `git archive 093cd52` 加各自明确改动的独立源码目录，没有复制 `.env`、服务 `.venv`、本地历史报告或既有 build。依赖使用已安装的解释器/包缓存；这些是本地干净检出证据，下一次 GitHub Linux 运行仍需单独观察：

| 检查 | 结果 | 本地日志 |
| --- | --- | --- |
| Python `verify-ci-gates.sh --mode python` | 依赖锁通过、**413 passed**、**31 条 mock 评估通过** | `python-clean-aggregate-green.log` |
| Java `./gradlew test --no-daemon` | **336 tests，0 failures/errors，14 skipped**，5 个 tasks 实际执行 | `java-ci-clean.log` |
| React `npm test` / lint / Node / build:budget | **108 passed，3 skipped**；lint 通过、Node **12 passed**、四项构建预算通过 | `frontend-ci-{unit,lint,node,build}.log` |
| React `npm run test:e2e` | **21 passed**，干净副本、真实 Chromium、本地 mock API；端口清理完成 | `frontend-ci-e2e.log` |
| GNU tar 原参数 / 新参数及完整契约 | **退出 2 → 退出 0**；payload 一致；完整 contract PASS | `gnu-tar/reproduction.log`、`gnu-tar/contract-after.log` |
| fixture 独立复查与扫描 | 6 个 fixture 均通过；Python 13 个 ID 全属 development；无凭据、客户数据、模型原文、gold 或 holdout；报告 manifest 摘要一致 | `ci-fixture-{input-review,report-review,gitleaks}.json` |

后续推送及最新四条 CI 结果以最终交付消息和该提交的 GitHub Actions 为准；不要重新运行旧付费批次修复测试输入，也不要把合成报告当成真实模型质量证据。

## 范围与基线

- 用户明确要求进行对抗式审查，修复发现的问题后推送 GitHub。
- 仓库：`Support-Copilot`；分支 `master`；审查开始时工作树 clean。
- 本地基线：`a3a296759a16b2eddf99cb62bf3a6c2ffd4587b6`。
- 已读取远端基线：`eaf264d0648244715d489c4c96a55990a023eef5`；待推送范围为 115 个提交、672 个路径。
- 审查采用工程/安全边界与规格/行为两个方向，重点检查最近的索引重载、评测来源绑定、知识权限和持久化结果重放，配合跨模块回归。没有逐行穷尽所有历史改动，不能声称绝对无 bug。

## 已复现与修复的索引问题

`app/live_vector_index.py` 的重载原先复用惰性加载：当 `build-if-missing` 开启而 active 指针丢失或损坏时，会创建 Provider、付费构建并修改 active。重载现在只加载已经准备好的 artifact；失败保留旧快照和磁盘文件。磁盘与矩阵校验在线程运行，避免占用事件循环。

`app/knowledge.py` 原先允许多个 reload 的准备阶段交错，较早请求可能较晚完成并把进程覆盖回旧快照。回归测试通过事件控制复现这一顺序；现将准备、校验、替换纳入同一重载锁，普通检索继续使用持有的快照。

`app/knowledge_source.py` 和 HTTP 边界现在将文件缺失、编码错误与格式错误作为可命名的语料读取失败返回 `409 INDEX_CORPUS_UNRELOADABLE`，响应不暴露本地路径。未知程序错误仍保留真实错误语义。

证据：新增 `tests/test_index_reload_safety.py`；初始六种场景均失败，修复后通过；并发覆盖另有先失败后通过记录。独立 Uvicorn + curl 演练包含正常 200、指针缺失/损坏 409、语料缺失 409、错误身份 401、关闭开关 403、错误身份优先于开关 401。七个场景均为零 Provider 创建、磁盘摘要不变，子进程已清理。合成向量证明协议和失败保护，不代表外部模型质量。

## 已复现与修复的评测问题

`evaluation/retrieval_only.py` 原先在完成付费查询后才发现输出文件已存在。现在比较完整准备计划，检查既有产物，并在任何 Provider 创建之前独占创建执行 claim；失败也保留 claim，阻止重复消费或并发重复执行。

`evaluation/gold_rank.py` 和 `hybrid_retrieval.py` 原先读取可变 active 指针的裸矩阵，可能将旧 query 向量、另一份语料和新索引混用。共享读取边界现在绑定执行时的计划/向量摘要，固定计划内 artifact ID，并校验语料摘要、Provider/模型/维度、切片身份、矩阵/metadata 与逐行 chunk 对齐，以及 query ID 和有限数值。评分报告另记录实际使用的案例文件摘要；案例标签可以独立修订，但不能隐藏本次用过哪份标签。

兼容限制：09-17/09-18 的历史缓存没有执行时计划和向量文件摘要，当前工具明确拒绝将它们作为重新验证的输入。旧报告保留为历史证据；不补写事后摘要来假装原始取证完整，不为通过检查自动重跑真实调用。后续重新测量必须使用新目录和独立预算。

Provider 返回 NaN、正负 Infinity 时，旧执行器还会写出错误的 `NO_EVIDENCE` 与非标准 JSON。新增有限数值检查在写成功产物前拒绝响应，并保留执行 claim。三个回归场景均先失败后通过。

## 已复现与修复的权限问题

原先无知识 scope 的用户在知识搜索中得到空列表，却能从分析历史、工单详情和列表读取已保存的 billing 证据与生成回复。`AnalysisResponseAccessPolicy` 现在按当前 active release 和 canonical corpus 校验整条分析的全部命中：chunk/document 身份、标题、章节、正文、来源必须一致，且每块证据均在调用者当前 scope 内。整条回复也可能包含未引用的检索内容，因此不能只过滤引用列表。

数据流现在为：首次生成 → 可读性检查 → 持久化；历史/详情/列表读取 → 同一策略检查 → 返回可读结果；singleflight 和幂等等待完成 → 按当前调用线程再次检查 → 返回。审核的读取、写入及缓存重放也先检查父分析，幂等等待后再次检查。Java 依赖故障 fallback 不再携带硬编码模拟知识命中；仅明确 `FALLBACK`、命名失败原因、零 hits/citations 的结果使用无知识证据分支。未知程序错误与反序列化错误不被转换为 fallback。

另一个漏洞是幂等摘要没有调用者身份与权限。`CommandRequestFactory` 现在为创建工单、分析、通过审核和驳回四类命令加入可信 actor 类型、subject 和排序去重后的 scopes。相同身份和等价 scope 集合仍可重放；不同身份或 scope 集合不能匹配原指纹。当前 release 被归档后，即使身份和 key 不变，也不能取出已失去访问依据的分析或审核缓存。

证据包括真实 SecurityFilterChain + 签名合成 JWT + H2 的四条 HTTP 回归，以及跨 context、重启、release 归档后的缓存拒绝。初始 scope 回归三条中两条失败、幂等回归十二条中八条失败；修复后通过。默认测试身份仍没有 scopes，成功路径显式授予所需权限并使用 canonical corpus，原并发、审计、审核状态和 70 KiB 持久化断言保留。独立只读复查未发现本轮变更中的具体可利用绕过。

兼容行为：

- 未知、归档或内容/来源改变的旧 chunk 无法证明可读，历史列表过滤对应分析；最新分析为空时不会退回更旧的可读结果，直接审核返回 `403`。用户角色不变也可能因 corpus 更新而遇到这一行为。没有删除旧记录或迁移数据库。
- 升级前的幂等摘要没有身份字段，原调用者使用原 key 也可能得到 `409`。先核对原业务操作是否已经成功，不能让客户端自动换 key 重做有副作用的命令。
- 每次读取都校验当前 corpus，未引入历史 ACL 或新缓存；未证明生产规模性能。这是证据访问控制，不是对任意生成正文或人工输入的语义泄密检测。

## 前端与凭据检查

前端 characterization 测试在导航后等待动态导入与 React Suspense 更新，保留原有断言和全局超时。移除等待可以复现失败，恢复后通过。另有下节的测试依赖安全升级，产品 UI 未修改。

凭据扫描初始 69 个 `generic-api-key` 命中已逐条与原提交核对：均为三个历史证据 JSON 内的文件 SHA-256。例外仅匹配这些文件路径及完整的文件路径键/64 位十六进制摘要行；默认规则继续启用。扫描历史时保留 Git 文件路径，控制测试要求同文件真实形态的密钥、不同路径及历史已删除密钥仍被检出。

## 依赖安全修复

严格扫描首先阻断了推送，未增加漏洞豁免。锁文件由原包管理器重新生成，仅升级下面的依赖组：

| 范围 | 原版本 → 修复版本 | 扫描发现 |
| --- | --- | --- |
| Python 开发依赖 | httpx2 / httpcore2 2.10.0 → 2.12.0 | 三项 HTTPX2 漏洞，涉及解压内存放大、multipart 头注入、HTTP framing 冲突 |
| Java 运行依赖 | Tomcat core/el/websocket 11.0.24 → 11.0.25 | CVE-2026-65905、CVE-2026-65182、CVE-2026-68525 |
| Node 开发依赖 | Vitest 及其七个子包 4.1.10 → 4.1.11 | GHSA-82fw-gwwq-j7x9 任意文件读取 |

上游依据：[HTTPX2 解压](https://github.com/pydantic/httpx2/security/advisories/GHSA-8xx6-hgc6-gc2m)、[multipart](https://github.com/pydantic/httpx2/security/advisories/GHSA-h4x7-gw46-3wm6)、[framing](https://github.com/pydantic/httpx2/security/advisories/GHSA-pf96-p4fj-6566)、[Tomcat 安全公告](https://tomcat.apache.org/security-11.html)、[Vitest 安全公告](https://github.com/vitest-dev/vitest/security/advisories/GHSA-82fw-gwwq-j7x9)。已知漏洞扫描通过只代表扫描时数据库中的记录，不等于不存在未知漏洞。

## 验证命令与结果

以下日志位于本机 `.local/prepush-review/`，默认命令工作目录为仓库根，表中另行注明的除外。测试执行时是初始 `a3a2967` 加本轮修改的工作树；提交按这些内容逐组保存，未把初始 SHA 描述成已经包含修复。

| 检查 | 命令 | 结果与范围 |
| --- | --- | --- |
| Python AI 完整回归 | AI 目录 `.venv/bin/python -m pytest -q` | **413 passed**；`python-final-cwd.log`，已安装修复后的开发依赖 |
| 评测定向回归 | AI 目录 `.venv/bin/python -m pytest tests/test_retrieval_only.py tests/test_offline_retrieval_evidence.py tests/test_gold_rank.py tests/test_hybrid_retrieval.py -q` | **61 passed**；`evaluation-focused-green.log` |
| Java 完整回归 | API 目录 `./gradlew test --no-daemon` | **336 tests，0 failures/errors，14 skipped**；`java-tomcat-final.log`，包括 Tomcat 补丁；实际通过 322 项 |
| 前端完整单测 | Web 目录 `npm test` | **108 passed，3 skipped**；`frontend-vitest4111-unit.log`，包括 Vitest 补丁；跳过的真实 API 契约需显式启用 |
| 前端静态/构建 | Web 目录 `npm run lint`、`npm run test:node`、`npm run build:budget` | lint 通过；Node **12 passed**；四项预算通过，见 `frontend-vitest4111-*.log` |
| 真实浏览器 | Web 目录 `npm run test:e2e` | **21 passed**，Chromium、三个视口、本地 mock API；`frontend-e2e-resume.log`。Vitest 补丁未改变生产依赖或构建产物，因此保留本次已有浏览器证据 |
| Benchmark 脚本 | `node --test scripts/benchmark/*.test.mjs` | **77 passed**；`benchmark-node.log` |
| 发布安全门禁 | `./scripts/verify-ci-gates.sh --mode release` | **PASS**；`release-final-gate.log`。Python prod 57/dev 66、Java 183、Node 234 个精确依赖记录均无已知漏洞；凭据控制测试、当时 tracked tree 与全历史 164 个提交扫描通过；workflow、迁移、安全静态与 23 项扫描证据测试通过 |
| 已提交文档 | `./scripts/verify-docs.sh --static` | **PASS，16 passed + 文档契约**；`docs-final.log`，在 clean `6485373` 的 `git archive HEAD` 上执行 |
| 文档提交后凭据复核 | `gitleaks dir . --config <repo>/.gitleaks.toml --no-banner --redact --exit-code 1`（在 HEAD archive 内），以及 `gitleaks git . --log-opts=--all --config .gitleaks.toml --no-banner --redact --exit-code 1` | **PASS，零命中**；clean `6485373`，全历史 167 个提交；`gitleaks-final-tree.log` / `gitleaks-final-history.log` |

一次从仓库根运行 AI 测试的尝试为 411 passed / 2 failed，因为两个子进程依赖 AI 项目工作目录，报模块未找到；按项目规定目录运行全量得到上述 413 passed，没有为此修改测试。运维 Python 测试首轮为 215 passed / 3 子进程超时，当时同时编译扫描工具；三项保持原样独立重跑全部通过。原失败记录保留，不将那次全量调用写成绿色。

## Git 与证据边界

修复代码、测试和锁文件最终收敛在 `6800f1388192d72211168e78cbcd98acab70d157`。在这个边界之后，本报告、STATUS、交接与运维说明仍在工作树中整理；代码与依赖没有继续修改。提交分组如下，可独立查看 diff：

| 提交 | 内容 |
| --- | --- |
| `fbf0f45` | 索引 reload 只读与快照串行替换 |
| `f48a51e` | 评测执行 claim、输入与 artifact 来源绑定、有限向量检查 |
| `cb4c44c` | HTTPX2 / HTTPCore2 安全升级 |
| `5df23df` | 凭据扫描的精确摘要例外与检测控制 |
| `358c406` | 历史分析、审核与幂等重放的知识权限 |
| `e61faae` | Tomcat 11.0.25 |
| `1aeadd3` | 前端懒加载测试等待 |
| `6800f13` | Vitest 4.1.11 |

发布门禁运行期间提交边界从 `f48a51e` 推进到 `e61faae`，因此它绑定所读取的工作树内容，不能伪称在单个 clean SHA 上完成。最终 Node/Java 锁文件分别与扫描 inventory 的 SHA-256 完全相同（`60724946fcbf793a94e595a04c4e34aa6909a3bd203793f5cb73e6e89a8d3448`、`5fabdcae27fb62b06d903c3c7523e25a92f143bb8979444fd23ba996d6dbbc1c`）。文档与凭据复核已在 clean `6485373c0326835989f8c8d24a0d475fd905781a` 通过，随后仅补记本段结果。最终 SHA、是否 clean、远端 SHA 与 Actions 结果在交付消息中另行记录，不对尚未执行的远端检查写 PASS。

## 验证范围与限制

本轮验证使用本地 mock、合成身份和公开的已落盘数据，不使用真实客户数据，不调用模型或 Embedding API，不部署。所有开始于 `a3a2967` 的结果绑定该基础提交加本轮工作树；提交后的文档门禁必须另行执行，不以历史绿色代替当前证据。

原始日志与隔离 HTTP 记录保存在本机忽略目录 `.local/prepush-review/`；本文记录可追溯结论，不把机器审查写成作者已理解、真人事实审核或生产质量结论。

本轮未运行 14 项 MySQL 环境测试、完整 Compose 部署与 `verify-docs.sh --full`；未新增 live 调用，holdout 仍封存，人审质量门禁仍 partial。不同 scopes 同时 join singleflight 的组合由返回边界的代码审查支撑，没有专门的服务级并发回归。现有 lazy chart 大于 500 kB 的构建提示保留，CSS gzip 为 8483/8500 字节，预算虽通过但余量较小。

可用于简历的新增事实必须限于最终通过的故障复现、修复和自动化回归；不能由本轮推出回答准确率、生产容量、真实客户解决率或完整发布资格。
