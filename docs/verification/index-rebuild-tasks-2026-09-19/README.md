# 索引重建任务化：切片 A（2026-09-19）

状态：已实现、已完成本地回归和独立有界复查。基线为 `1de4a77f2c78c01eb78d9c09aa4db9e361131e95`；该基线已推送，四条 GitHub CI 均通过。下面的新行为由基线加本切片工作区验证，不能归给旧 SHA。最终提交、已提交文档门禁及远端 CI 另以本轮交付消息和 Actions 核对。

## 业务问题与边界

已有 `EmbeddingArtifactStore.build()` 能构建、验证、原子发布索引，但只能由手工 CLI 调用。直接把它放进 HTTP handler 会让长时间构建占用请求生命周期，同步矩阵处理和磁盘写入还可能阻塞事件循环；多个服务进程也不能仅靠对象内锁避免重复调用。

这一切片仅将配置路径上的现成语料构建为一个可查询的后台任务。Node 语料生成、上传解析、前端按钮、Java 代理、自动激活和自动重载不属于本切片。构建没有经过激活，线上检索仍使用原快照。相同内容身份的完整 artifact 会被验证并复用，不强制重新付费建库。

## 数据流与关键文件

```text
内部鉴权 → mutation 开关 → 同目录进程锁
→ 读取配置语料、校验预期摘要与调用上限 → 持久化 RUNNING → HTTP 202
→ 后台线程内构建，按实际批次更新进度
→ 验证并原子发布 artifact → 持久化 SUCCEEDED
或 → 持久化 FAILED、保留候选目录与安全错误码
```

- `services/support-copilot-ai/app/main.py`：两个内部 HTTP 入口、错误 envelope、lifespan 管理任务组。
- `services/support-copilot-ai/app/index_rebuild_models.py`：请求与持久化任务契约。
- `services/support-copilot-ai/app/index_rebuild.py`：配置/预算检查、后台构建、任务终态。
- `services/support-copilot-ai/app/index_rebuild_storage.py`：任务文件原子更新与本机文件锁。
- `services/support-copilot-ai/app/index_rebuild_provider.py`：延迟创建的受管 Provider、分批调用与进度。
- `services/support-copilot-ai/app/embedding_artifact.py`：复用既有构建与验证；任务传入独立 candidate 目录时保留失败现场，旧调用方保留原清理行为。

## 调用与成本口径

写入口默认关闭，需 `KNOWLEDGE_INDEX_MUTATION_ENABLED=true`，并配置 Embedding 凭据、模型与维度。凭据仅来自既有环境变量。`AI_MODE=mock` 描述工单分析模式，不把显式重建变为模拟 Embedding；启用重建并提供真实供应方配置会产生真实外部调用。

`POST /knowledge/index/rebuild` 要求内部服务凭据，body 为：

```json
{
  "expectedCorpusChecksum": "<配置语料内已验证的64位SHA-256>",
  "maxEmbeddingCalls": 1
}
```

摘要绑定本次读取的磁盘语料，不能用进程中旧语料身份代替。请求不接受文件路径、模型覆盖、自动激活或任意命令。配置语料与预期摘要不同返回 `409`；调用上限不足返回 `422`，均不创建 Provider、不调用外部服务。已有任务运行返回 `409`，不排队。

成功受理返回 `202` 和 `Location: /knowledge/index/rebuild/<taskId>`。按该地址 GET 查询任务；读取也要求内部身份，关闭写开关后仍可查询历史任务。未知 UUID 返回 `404`。无效身份优先于功能开关，不向未授权调用者泄漏任务信息。

每批最多 32 个 chunk，预估调用上限为 `ceil(totalChunks / 32)`；Provider 重试固定为 0。`embeddingCalls` 在发送每次请求前落盘，表示已开始的尝试，不能据此推断供应方计费。`completedChunks` 只在批次返回并通过数量、维度与有限值校验后增加；中途失败不会假装完成余下内容。它表示向量完成量，不表示落盘完成；只有 `SUCCEEDED` 才表示产物通过验证并发布。复用既有有效 artifact 时实际调用数为 0。

`elapsedSeconds` 与开始/更新时间记录实测经过时间，`estimatedDurationSeconds=null` 表示尚无可信预测。历史“3015 chunks 约 50 秒”不适用于新的批次策略，不作为接口承诺。未查询可靠价格，不报告货币费用。调用次数上限是明确预算边界，不是实际费用保证。

## 持久化、并发与失败

任务位于 `EMBEDDING_ARTIFACT_ROOT/.rebuild-tasks/<taskId>/`，状态使用原子替换与 fsync。任务记录保存 ID、摘要、进度、时间、traceId、artifact ID 或固定失败码，不记录原始 Provider 响应、凭据或客户正文。

进程间使用同一个 artifact root 的非阻塞文件锁，锁覆盖构建及终态保存；普通退出等待已接受任务结束。进程被强制终止时操作系统释放锁，后续查询可识别遗留 RUNNING 并标为 `FAILED / REBUILD_INTERRUPTED`，不会自动恢复或重试。终态任务重启后仍可查询；这是本机 Unix 文件系统上的 API 重建互斥，不是跨主机分布式协调。已有 CLI 和检索 `build-if-missing` 不参与此 API 锁，运维不得与其并发运行；生产继续使用 `require-active`。

失败保留任务记录和已创建的 candidate 文件；Embedding 尚未完成时 candidate 可能为空，不能声称已保存未返回的向量。任务构建不修改语料、active 指针或检索快照。未知程序错误进入显式 `FAILED / REBUILD_INTERNAL_ERROR` 并记录安全错误类型，不转换为 fallback 或成功。磁盘不可写时返回明确存储错误；不能承诺在磁盘本身失效时仍写下完整终态。

保留目录不会自动清理，也没有取消/续跑接口。后续运维清理需要先确认任务已终止及证据保留要求，不以删除失败记录的方式自动重试。进程若在 artifact 发布后、任务终态落盘前被终止，恢复时仍报告中断；先检查 versions 和完整性，不能因任务失败就推断没有产物或没有外部费用。激活仍使用既有显式 CLI，随后按原运维顺序调用 reload；两者不是构建完成的隐式副作用。

## 验收与证据

以下结果绑定上述基线加本切片改动的 dirty 工作区；不是 `1de4a77` 原始代码的绿色。全量回归之后只补充测试观测记录、主模块错误列表的类型注解及文档，观测记录和相关 HTTP/错误边界分别再次验证。日志保存在本机忽略的 `.local/` 中。

| 检查 | 命令与结果 | 证据 |
| --- | --- | --- |
| Python 完整门禁 | 根目录 `./scripts/verify-ci-gates.sh --mode python`：依赖锁一致、**449 passed**、**31 条 mock 评估通过**，退出 0 | `.local/index-rebuild-python-aggregate.log` |
| 构建失败现场与兼容回归 | AI 目录 pytest：新建 build evidence、原 store、CLI 共 **21 passed**，其中新增 8 项 | `tests/test_embedding_artifact_build_evidence.py` 等 |
| 任务/持久化 | AI 目录 pytest manager + durability：**16 passed** | `tests/test_index_rebuild_manager.py`、`test_index_rebuild_durability.py` |
| API 验证 | 新接口 **9 passed**；主模块类型注解后连同健康/错误/内部鉴权回归再次通过 | `.local/index-rebuild-api-green.log`、`index-rebuild-api-final.log` |
| 真实本机网络 | AI 目录 `.venv/bin/python -m pytest -q tests/test_index_rebuild_http.py -o junit_family=xunit1 --junitxml=../../.local/rebuild-http-review/http-probe.xml`：**3 passed** | [实际 probe](probe.json)，原 XML/log 在 `.local/rebuild-http-review/` |
| 工作区文档契约 | 根目录 `services/support-copilot-ai/.venv/bin/python -m scripts.verify_docs --repo-root .`：通过；提交后仍需运行 `./scripts/verify-docs.sh --static` | `.local/index-rebuild-docs-working.log` |

红绿反证：新增 API 测试在接口不存在时 6 项均因实际 404 失败；真实 HTTP 成功场景在隔离 `git archive 1de4a77` 加新测试的环境中也因 404 而失败，日志为 `.local/rebuild-http-review/baseline-red.log`。保留 candidate 的首条测试在新参数不存在时失败；另一个状态校验反例表明“缺 artifact 的伪成功状态”原先会被读取，增加持久化模型的一致性校验后被拒绝。没有弱化旧断言或删除失败测试。

这 36 项新增回归覆盖鉴权/开关优先级、202 与轮询、构建时健康请求仍响应、同目录独立 manager 并发拒绝、65 chunks 的三批进度、摘要与预算拒绝、复用零 Provider、HTTP 500 零重试、非法向量、未知错误脱敏、磁盘失败阻止下一次调用、失败现场保留、旧 active 不变及重启/中断行为。真实 Uvicorn 测试的 2 chunks 只证明 HTTP 与生命周期，32 条分批边界由 manager 测试证明。

独立 API/生命周期审查与独立 manager/存储审查未发现可确认的阻断项。Ruff 的错误检查通过；技能自定义 noqa 标记仍产生解析提示。新增核心模块 focused basedpyright 为 0 errors / 5 warnings，API 及相关测试为 0 errors / 38 warnings，命令因 warnings 返回 1；这是非阻断的静态提示记录，不宣称严格类型门禁全绿。新增模块/测试的技能检查通过，既有 `main.py` 与 artifact 模块的大文件及历史类型风格没有在本切片进行无关重构。

测试均使用隔离临时语料、临时目录和合成凭据，不访问真实模型供应方或消耗 holdout。没有新增依赖，Java/React 产品代码未改；本轮没有重新验收 MySQL、Docker、Compose、完整发布演练或真人 RAG 质量。

只有最终通过的任务调度、持久化、故障回归和本地网络演练可以成为新增简历证据；不能由此宣称真实 Embedding 质量、生产容量、完整上传功能或线上成本改善。
