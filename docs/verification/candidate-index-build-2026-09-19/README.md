# 成功候选语料到索引构建

## 当前结果与范围

已实现：现有 `POST /knowledge/index/rebuild` 支持可选 `corpusBuildTaskId`，显式选择 B1 已成功任务的候选语料。不传该字段仍使用配置中的 knowledge_path 与 provenance。索引任务保存来源 ID，成功产物的 corpus checksum 与切片版本绑定候选；不自动激活、reload、替换知识文件或修改 Java release。

本轮为用户在 B1 交付后要求“继续”的单个垂直切片。复用已有任务管理、调用预算、provider、文件锁和 artifact 校验，不新增路由、后台框架或部署依赖。仅使用合成文档、真实本机 Node/Uvicorn 和 localhost Embedding 替身，没有真实供应方费用、评估集变动或 holdout 消耗。

## 问题、修改层和数据流

原来 B1 生成的候选与 A 的索引任务没有明确交接；构建 A 只能读取配置语料。直接替换正在使用的 knowledge_path 再建索引，会让准备工作影响运行状态。现在把选择放在索引任务接纳层：在任何 provider 调用和 RUNNING 记录前完成候选校验，随后沿用原构建流程。

主要代码：AI 服务 `app/index_rebuild_models.py` 增加可选 UUID 与状态来源 ID；`app/index_rebuild_source.py` 选择并校验源；`app/index_rebuild.py` 在锁内完成选择、预算检查、保存状态，并让 artifact 使用候选切片版本。

1. 先执行既有内部鉴权和索引写开关。请求不接受文件路径、激活选项或任意生成器参数。
2. 有 `corpusBuildTaskId` 时，从配置 corpus build root 读取该 UUID 的严格任务记录。只有经过模型校验的 SUCCEEDED 记录带有 result；RUNNING/FAILED 不能被选中。
3. 读取 `result/corpus.json` 一次，沿用 B1 的 64 MiB 文件上限。核对保存的文件 SHA-256，再把同一份 bytes 解析成不可变 KnowledgeCorpus，验证语义摘要、片段唯一性与结构、保存的片段数量。
4. 核对调用者明确提交的 expectedCorpusChecksum 和 maxEmbeddingCalls。任何不符在调用 provider 前拒绝；调用配额仍按 32 个片段一批估算。
5. 返回 202 + Location。已接受任务保存来源 UUID，工作线程使用内存中的语料快照；接受后磁盘文件变化不会替换本次输入。artifact 的 chunking_version 来自成功候选参数，而非当前服务使用的旧切片配置。
6. 完成后 GET 返回 artifactId、corpusChecksum、corpusBuildTaskId 和真实调用量；如果相同 artifact 已存在且验证通过，复用它并记录零次新增调用。来源候选文件仍可被后续操作删除，所以该关联不是永久源文件归档。

请求示例（示意值，实际 ID/摘要必须来自自己的成功任务）：

```json
{
  "corpusBuildTaskId": "00000000-0000-4000-8000-000000000001",
  "expectedCorpusChecksum": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "maxEmbeddingCalls": 1
}
```

真实测试文档 `A😀BCDE` 使用 window=4、stride=3：Node 产出 `A😀BC` 和 `CDE`，localhost SDK 请求恰好发送这两段，artifact 记录 `doc2dial-codepoints-4-3-v1`。当前服务知识文件和 active.json 的字节在整个流程中不变。

## 失败路径与兼容性

| 情形 | 结果 |
| --- | --- |
| 候选 UUID 不存在 | 404 / CORPUS_TASK_NOT_FOUND |
| 候选未成功 | 409 / CORPUS_CANDIDATE_NOT_READY |
| 候选文件丢失、变化、解析失败或结果摘要/数量不匹配 | 409 / CORPUS_CANDIDATE_INVALID |
| 候选任务状态损坏 | 503 / CORPUS_STORAGE_UNAVAILABLE |
| 调用者授权摘要不匹配 | 409 / CORPUS_CHECKSUM_MISMATCH |
| 预算低于所需批数 | 422 / EMBEDDING_CALL_BUDGET_EXCEEDED |
| SDK 收到 provider 500 | 任务 FAILED / EMBEDDING_PROVIDER_FAILED，保留来源和失败现场，不重试或激活 |

没有新增 provider 降级；未知错误继续是失败。既有 API 文件锁覆盖旧语料与候选语料任务，禁止同 artifact root 的 API 构建重叠。读取成功候选不要求重新打开语料生成写开关，但索引构建仍要求既有索引写开关和 provider 配置；选择候选不是免费调用授权。

旧请求与旧持久化状态无新增必填字段，来源 ID 默认为 null。配置语料分支沿用原 loader/provenance 校验。候选分支以 B1 的成功记录和文件摘要作为来源证据，不错误套用当前在线语料的 provenance 文件；这是独立本地候选的可信边界，不是允许导入任意外部语料。root 与磁盘记录由运维控制，未实现多租户/上传授权。

## 验证证据

基线 `860434ac0a05cbf5fd5ca457202b93fbaf482477` 已推送且四条 CI 通过。以下本地命令绑定其后的本切片未提交工作树；最终 SHA、独立复查和远端结果见交付消息及本地任务证据账本，不把旧 CI 复用为本轮证据。

- 红绿回归：新增请求最初返回 422 extra_forbidden；接入后通过。日志 `.local/candidate-index-red.log` / `-green.log`。
- `services/support-copilot-ai/.venv/bin/python -m pytest -q services/support-copilot-ai/tests/test_candidate_index*.py --junitxml=.local/candidate-index-http.xml -o junit_family=legacy`：11 passed。包括实际 Node 生成、接受后的磁盘变化、八类接纳拒绝、真实 HTTP 成功/失败/重启与零调用复用。实际响应从 JUnit 属性导出至 [probe.json](probe.json)，不手填结果。
- `./scripts/verify-ci-gates.sh --mode python`：479 项 Python 测试、31 项 mock 评估通过（`.local/candidate-index-python.log`）。
- 新/改生产模块的 basedpyright 为 0 errors，保留 2 条既有穷尽 match 的 unreachable 分支警告，不宣称零警告；未安装 LSP 服务，本轮未要求安装，使用已有离线命令工具验证。
- 没有运行真实模型、质量评分、生产负载、Docker 或 MySQL 演练。

## 下一步与简历边界

本轮可写：复用持久化任务串联候选语料生成与有预算的索引构建，使用文件/语义摘要防止来源混用，以真实本机网络和故障测试验证隔离与重启追溯。不能写：回答质量提升、生产容量、客户效果、已完成一键切换或真实付费建库。

下一切片先明确如何把匹配的语料与索引作为一组显式切换，包含 Java release 一致性、切换中失败/重启、旧快照保留和回滚边界；不要只恢复一个“换索引指针”的按钮。作者尚无本轮人工 diff review 或新复述记录，AI 审查与自动测试不代替它们。
