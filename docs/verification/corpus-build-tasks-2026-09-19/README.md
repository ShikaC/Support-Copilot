# 语料生成任务切片 B1

## 结论与范围

已实现：Python 内部 API 调用仓库唯一的 Node 切片实现，从预配置 Doc2Dial 文档 JSON 生成候选语料，持久化接受记录、结果摘要和失败状态。默认关闭写入。业务目标是为后续调整切片参数提供可查询的构建步骤；本切片不接上传、前端、索引激活或部署。

决策：沿用 B1（Python 调 Node），不维护第二套 Python 切片算法。用户在上一轮建议 B1 后要求“继续”；原交接的待决策状态由此更新。旧 benchmark 中的文档切片和对话题目选择已分开：语料任务不接收 `perDomain`，不读取对话或生成评估集。冻结资料和 holdout 没有修改，也没有调用任何模型供应商。

已验证的行为、最终 Git 边界和审查结论见下文。作者尚未记录本切片 diff 的人工审核或新复述，不作可发布、生产质量或作者已理解的结论。

## 一条数据流

原来服务只能对磁盘上已有的语料建索引；切片逻辑位于 Node 评测脚本里，如果在 Python 重写就需要长期维护等价性。现在共享 `knowledge-tools/doc2dial-corpus.mjs`，旧评测入口和新 `knowledge-tools/build-corpus.mjs` 都调用同一个函数。

1. `POST /knowledge/corpus/build` 先执行内部鉴权，再检查独立写开关。请求仅包含源文件字节的 SHA-256 `expectedSourceChecksum`、`window`、`stride`；整数必须满足 `1 <= stride <= window <= 8000`，未知字段和布尔值拒绝。
2. `CorpusBuildManager._prepare` 获取当前 build root 的非阻塞文件锁，读取配置文件一次，限制为 64 MiB，并核对字节摘要。调用者不能提供路径或任意命令。源内容在接受后保留为不可变 bytes；后来换文件不改变这个任务。
3. 原子保存 RUNNING 后返回 202 和 Location，任务交由 lifespan 的 AnyIO task group 管理。工作线程执行固定 Node 脚本，并通过 pass_fds 将同一 flock 描述符传给 Node；Python 异常退出后 Node 仍持锁。stdin 传原始 bytes，无 shell，环境只含 LANG；不继承凭据、NODE_OPTIONS 或其他运行选项。
4. Node 主线程保留独立超时计时器，切片在同进程 worker thread 执行，即使同步解析阻塞也能退出整个 Node（退出码 124）。Node 按 Unicode code point 切片，生成 `candidate/corpus.json`、`chunk-map.json`、`chunking.json`、`manifest.json`。最多 20000 个片段、累计正文 32 MiB、每个 JSON 文件 64 MiB，Node heap 上限 512 MiB。构建超时默认 60 秒，可配置上限 120 秒；这是 Node 执行期限，源读取、磁盘刷写和系统调度不包含在内，heap 上限也不等于整个进程 RSS 上限。
5. Python 用现有 `KnowledgeCorpus` 校验 corpus 的内容摘要与结构，再核对 manifest 的输入摘要、语料语义/文件摘要、片段数与切片参数。文件 fsync 后将 candidate 改名为 result，最后原子保存 SUCCEEDED。查询端返回实际耗时，预估时间保持 null。

例如文档 `A😀BCDE` 使用 window=4、stride=3，输出两段 `A😀BC` 与 `CDE`。API 保存这两段的候选文件；当前知识文件、active 索引指针与检索快照均不发生切换。

关键代码：`services/support-copilot-ai/app/main.py` 的两个 corpus 路由、`app/corpus_build.py` 的接受/执行/终态逻辑、`app/corpus_build_process.py` 的子进程边界、`app/corpus_build_storage.py` 的锁和原子记录、`knowledge-tools/doc2dial-corpus.mjs` 的共享生成函数。以上路径相对 AI 服务目录（main.py 除外）。

## 失败语义与运维边界

| 触发 | 可观察结果 |
| --- | --- |
| 没有内部身份 | POST/GET 都 401 |
| 写开关关闭 | POST 403；历史 GET 仍可用 |
| 摘要不匹配、正在构建 | 409，不接受新任务 |
| 非法参数 | 422，不启动 Node |
| 缺 Node/固定脚本/源配置 | 503，不创建 RUNNING |
| 无效文档 JSON / Node 非零退出 | 已接受任务 FAILED，`CORPUS_PROCESS_FAILED`，保留 candidate |
| 超出 Node 执行期限 | 杀死并等待 Node 退出，FAILED / `CORPUS_BUILD_TIMEOUT` |
| 无主 RUNNING 被查询或新任务接纳时发现 | FAILED / `CORPUS_BUILD_INTERRUPTED`，不自动恢复 |
| 任务文件损坏 | 503，不能伪装 SUCCEEDED |
| 未知 Python 程序错误 | FAILED / `CORPUS_INTERNAL_ERROR`，日志只保留类型和 trace，不进入 fallback |

本机 Unix 文件锁只协调使用同一 root 的任务 API；不协调手工 CLI、其他主机或独立配置的 root。失败候选/历史任务没有自动清理、取消、续跑和重试 API。任务接受时的源文件快照保留在内存，磁盘状态保存其摘要，并非源文件归档。

磁盘本身故障时不能保证终态可持久化；会记录固定 storage 错误。result 改名后、终态保存前若崩溃，可能留下 result 与中断状态，需人工检查，不能因目录存在认定任务成功。manifest 与 corpus 被验证；附属 chunk-map/chunking 由固定受信脚本生成，本切片未提供任意生成器插件或外部候选导入接口。

运行时配置见 AI 服务的 `.env.example`。本地源码运行须安装 Node（CI 显式使用 Node 24）。**当前 AI Docker 镜像没有 Node 和 knowledge-tools，B1 在该镜像中尚不可用**；默认关闭不会影响现有工单分析，显式启用后预检会返回配置错误。镜像集成应作为后续部署切片验收。

## 本轮证据

基线为 `444bbdea06209d29e45f3dc28f4af1e63553b833`（切片 A 的最终已推送提交）；以下本地验证运行在其后的 B1 **未提交工作树**，不能引用 A 的 CI 作为 B1 证据。提交 SHA 与远端 Actions 以本轮最终交付为准，不为记录自身 SHA 反复追加文档提交。

| 验证 | 命令与结果 | 能证明与不能证明 |
| --- | --- | --- |
| 先失败后通过 | Node 新接口缺失/API 404 的日志在 `.local/corpus-build-node-red.log`、`.local/corpus-build-api-red.log`；随后针对性测试通过 | 证明测试先暴露缺失能力；不证明质量指标 |
| 共享切片兼容性 | `node --test scripts/benchmark/*.test.mjs`：80 passed | 包括旧 benchmark 与新 CLI 拒绝非法输入、拒绝覆盖、输出上限 |
| 冻结数据复现 | `node scripts/benchmark/prepare-doc2dial.mjs --verify-against docs/verification/business-benchmark-2026-09-10`：verified true | 旧评测入口仍复现 1564 片段、32 题；未改变题目 |
| 独立 CLI 字节对拍 | 下方命令；corpus 与 chunk-map 的 `cmp` 都返回 0 | 证明当前归档数据和默认参数的文件完全等价；不是所有输入的数学证明 |
| 真实本机 HTTP | `services/support-copilot-ai/.venv/bin/python -m pytest -q services/support-copilot-ai/tests/test_corpus_build_http.py --junitxml=.local/corpus-build-http.xml -o junit_family=legacy`：1 passed | 真实 Uvicorn + Node、202、成功、无效输入失败、重启关闭写入后读回；没有外部模型 |

独立 CLI 对拍在新建 `.local/corpus-build-equivalence.ToiQHN` 中运行，未覆盖冻结目录：

```bash
node services/support-copilot-ai/knowledge-tools/build-corpus.mjs 2000 1600 .local/corpus-build-equivalence.ToiQHN < .local/business-benchmark-source/doc2dial_doc.json
cmp .local/corpus-build-equivalence.ToiQHN/corpus.json docs/verification/business-benchmark-2026-09-10/corpus.json
cmp .local/corpus-build-equivalence.ToiQHN/chunk-map.json docs/verification/business-benchmark-2026-09-10/chunk-map.json
```

源文件 46216432 bytes，488 篇文档、1564 片段。语料语义摘要为 `9c1e91d5fff7f1b9f2b2a48efe71275b01035eac88b8ea693df1215b0e307b27`；corpus 文件摘要 `e9c1795210db5a339d33cec6ef048074f93a4ba3e292de6c8aabd53ff5458dcb`；chunk-map 文件摘要 `704116cb9b075adf8173be87abfdbfa507e205a58617441e594f6d4e7d527e62`。原日志保存在 `.local/corpus-build-byte-comparison.log`。实际 HTTP 响应从 pytest JUnit 属性导出到同目录 `probe.json`，不手填成功结果。

最终本地回归：`./scripts/verify-ci-gates.sh --mode python` 通过，468 项 Python 测试与 31 项 mock 评估通过（`.local/corpus-build-python-final.log`）。`actionlint .github/workflows/python-ai-ci.yml` 与 `./scripts/tests/verify-ci-gates-contract.sh` 通过。新 Python 模块/测试的 no-excuse 检查无违规；basedpyright 从服务目录运行时 0 errors，保留 1 条穷尽 match 的 unreachable 分支警告，未用 ignore 隐藏，也不把它描述为零警告。

对抗审查的 Standards 与 Spec 两轴各发现 1 项，指向同一个父进程死亡缺陷：Python SIGKILL 后 Node 继续写入，但锁已释放，父进程的 timeout 也失效。`test_corpus_build_parent_death.py` 先失败（`.local/corpus-build-parent-death-red.log`），继承锁加 Node 自身期限后通过（`.local/corpus-build-parent-death-green.log`）。真实故障注入使用实际入口的临时副本，在 worker 中插入同步阻塞；杀死 Python 后锁保持，Node 到期退出后旧状态恢复为 INTERRUPTED。失败不发布 result。正常 HTTP 与全量回归在修复后重新执行。

两个审查代理的首次修复复查因服务 429 未完成，不能记为 PASS；最终提交的独立复查与运行审计在本地任务证据账本记录，远端 CI 以最终交付为准。未进行人工 review，不宣称绝对无 bug。

## 下一切片与简历口径

先阅读 B1 diff 和本说明。下一步只设计并实现“明确选择已成功候选语料 → 对它建索引”的交接，先确认语料/索引配对、显式切换、失败保留旧快照的验收，再扩展 Java/前端；上传解析仍是后续独立切片。不得把 B1 的成功当作自动激活或已授权付费建库。

可用于简历的事实是：复用唯一切片实现，提供有边界的跨进程候选构建任务，验证正常、并发、超时和重启失败语义，并以冻结公开数据做兼容性对拍。不能声称提升回答质量、生产吞吐、真实客户效果、完成 Docker 部署或作者已人工审查。


补充复查：`5d16ea4` 的独立 code/QA lane 发现 Node 的符号链接启动器被 `Path.resolve()` 改成其目标程序，导致 mise 按错误名称分发。改为绝对路径但不追踪符号链接，保留启动器身份；新增便携启动器回归先失败后通过（`.local/corpus-build-shim-red.log` / `-green.log`），不继承环境凭据。

证据范围校正：80 项 Node 测试通过是在包含本地历史评测文件的作者工作区执行。干净检出的全量 Node 测试为 66 passed / 4 failed，失败来自未入库的旧 `quality-input-audit` cases / freeze-manifest 等 fixture；基线 `444bbde` 同样未跟踪这些文件，并非 B1 删除。本切片相关的共享切片与 corpus 测试在干净检出中 15 passed。保留历史失败，不补造评测输入，也不将全量干净检出描述为通过。
