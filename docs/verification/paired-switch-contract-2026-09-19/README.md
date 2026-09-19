# 成组切换契约与现有边界核对

日期：2026-09-19。结论：完成成组切换的设计契约和重复发布版本的回归保护；没有实现或执行成组激活。决策唯一来源为 [ADR-0002](../../decisions/ADR-0002-paired-knowledge-switch.md)，当前状态见 [STATUS](../../STATUS.md)。

## 原问题与本轮边界

成功生成候选和索引，不代表 Java 能发布它们。Doc2Dial 生成器的 releaseVersion 固定为 1，而 Java 要求全局唯一；releaseId 只依赖切片参数，不能区分相同参数的不同来源。Python reload 的原子性只覆盖本进程内存，Java publish 的事务只覆盖数据库。混用两者可能造成暂时不匹配及重启拒绝。

本轮修改层是决策、交接与一条 Java 集成回归，不修改生产接口、数据库约束或候选 bytes。没有尝试用删除唯一约束、修改已构建 artifact、自动付费重建或吞错解决该问题。

## 阅读与修改位置

- `services/support-copilot-ai/knowledge-tools/doc2dial-corpus.mjs`：`releaseId` 与 `buildCorpus`，参数身份及固定版本来源。
- `services/support-copilot-ai/app/knowledge.py`：`RetrievalState`、`reload_index` 与 `search`，内存成组快照与失败保留边界。
- `services/support-copilot-ai/app/embedding_artifact.py`：`_require_compatible`、`_artifact_id`，发布身份属于索引身份。
- `services/support-copilot-api/src/main/resources/db/migration/V4__governed_knowledge_releases.sql`：版本全局唯一约束。
- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/knowledge/KnowledgeReleaseService.java`：publish/rollback 的事务与目标行 expectedVersion。
- 同目录 `KnowledgeCorpusStore.java`、`KnowledgeService.java`、`KnowledgeBaselineInitializer.java`：配置文件读取、请求身份检查和启动拒绝。
- `services/support-copilot-api/src/test/java/com/cyagent/supportcopilot/knowledge/KnowledgeReleaseIntegrationTests.java`：新增 `duplicateReleaseVersionCannotReplacePublishedRelease`。

## 已验证：当前工作区

基础 SHA 为 `b43aad19ef38aea8690871288c3620977e711dc0`；验证时 dirty，只包含本轮测试/文档修改。以下是当前工作区证据，不冒充基础提交已经含有新增回归；最终提交可通过 `git log -1 --format=%H -- docs/decisions/ADR-0002-paired-knowledge-switch.md` 定位。最终 SHA 审查和远端状态由交付消息报告，不在提交内循环写入自身 SHA。

### Java 请求与数据库边界

在 `services/support-copilot-api` 执行：

```bash
./gradlew test --tests '*KnowledgeReleaseIntegrationTests' \
  --tests '*KnowledgeCorpusStoreTests' \
  --tests '*KnowledgeSearchAccessIntegrationTests' --no-daemon --max-workers=1
```

结果：18 tests，0 failures，0 errors，0 skipped；读取 Gradle JUnit XML，未用 BUILD SUCCESSFUL 代替测试计数。新增场景经真实 Spring 安全、MVC、事务与 H2 层创建/审批/发布 version=20，再提交另一个 ID、不同 checksum、同 version 的候选；观察到 HTTP 400，当前 PUBLISHED release 和 checksum 保留，无候选行、无额外成功审计。版本 20 避免依赖测试初始化的 baseline=1；保护的是相同全局版本冲突，而不是数字 1 的特殊分支。

这是 MockMvc 集成证据，不是 Java 外部 TCP curl、MySQL 或完整跨服务切换证据。当前 jdtls 未安装，按已有用户偏好不安装；Java 编译与测试已通过。

### Python 已有正常/失败路径

在 `services/support-copilot-ai` 执行：

```bash
.venv/bin/python -m pytest -q tests/test_index_reload_safety.py \
  tests/test_index_versions.py tests/test_cross_service_knowledge_contract.py \
  tests/test_knowledge_access.py tests/test_knowledge_access_api.py
```

结果：34 passed。范围包括同组 reload、语料不匹配拒绝、半组替换失败保留旧状态、并发 reload 次序、认证/开关和 Java→Python release 契约。未修改这些 Python 测试或生产代码。

### 本机 HTTP 使用核对

复用 `tests/test_index_rebuild_http_support.py` 的 `seeded_index`、`embedding_server`、`running_api`，在临时目录创建合成语料/索引，启动真实 Uvicorn；通过 `curl --noproxy '*' --max-time 5 -X POST` 携带合成内部 token 调用 reload。进程只使用测试辅助函数的 allowlisted 环境，不加载开发者凭据。操作顺序与实际结果：

```text
完整旧组 → reload 200
active.json 改成 invalid-json → reload 409 / INDEX_VERSION_UNUSABLE
versions 仍报告原 corpus 身份；磁盘指针仍是 invalid-json（没有自动修复）
显式恢复保存的原 active.json bytes → 停止并重启 Uvicorn → reload 200
本机 Embedding 替身收到的请求：0
```

这证明 HTTP 失败与人工恢复边界，不证明旧进程的所有后续请求均能成功，也不证明损坏指针下重启会自动恢复。进程在上下文结束时停止、临时目录清理。没有接触运行中的工作台和旧数据。

## 计划中与停止条件

下一步按 ADR 先实现显式发布身份贯穿候选与索引，保留 benchmark 默认 bytes。完整切换仍缺维护/排空、成组恢复记录、事务内 expected-current、重启统一选择和实际已加载 artifact 观测；在这些完成并演练前不能将 ADR 当作执行手册。

本轮没有新增部署、真实供应方调用、holdout 使用、真人审核或作者已掌握的结论。可用于面试的证据是“识别跨服务发布身份与恢复边界，并用请求/数据库回归和本机 HTTP 核对”；不能写成“已实现零停机原子发布”“生产可用”或“无漏洞”。
