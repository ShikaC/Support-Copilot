# 第 66 轮：知识发布治理与硬访问过滤

## 问题与风险

Java 和 Python 的独立 Task 8 切片最初都能通过测试，但 Java 使用 `bundled-v1` 和原始知识文件 SHA，Python 使用 `support-copilot-bundled-v1` 和规范化 chunks 的语义 checksum。真实 Java-to-Python 请求因此稳定返回 `409 KNOWLEDGE_RELEASE_MISMATCH`。另一个缺口是 `test` profile 在 JWT 缺少 `support_scopes` 时默认授予全部范围，与 `local`/`pilot` 的零权限语义不一致。

## 修改层与流程

Java 以 `DRAFT -> APPROVED -> PUBLISHED -> ARCHIVED` 管理 release。release id、release version、corpus checksum、允许范围和创建信息不可更新；审批、发布和回滚要求 `expectedVersion`。发布/回滚在一个事务内锁定唯一 active pointer、切换 release 状态并写受控审计事件，审计失败会回滚全部状态。

Java 分析请求和 `GET /api/knowledge/search` 都只从 JWT `support_scopes` 读取白名单范围，再与 active release 范围求交集。缺失、空值和未知范围都不能扩大权限，浏览器 query、正文或 header 不能提供范围。Java search 为每个目录片段保留内部 `KnowledgeScope` 元数据，先过滤再计分和排序，响应不暴露内部 allowlist；active release 不可用或不一致时保留既有 409 失败关闭。Python 先校验 release id/version/checksum，再在本地打分、向量文档构建和 Prompt 生成前过滤片段；无范围时不会构造 Embedding provider 或调用生成 provider。

基线统一为：

- release id：`support-copilot-bundled-v1`
- release version：`1`
- semantic corpus checksum：`b25240587df1ebb903a8555284a0f35faaa35e2d837add0fc5dd49418ca8b874`

checksum 对排序键、紧凑编码的 chunks JSON 计算 SHA-256，不包含 release 元数据，也不等于整个知识文件的原始 SHA。Java 真实序列化请求保存在一个共享 fixture 中；Java 比较完整 wire JSON，Python 用严格 Pydantic `AnalyzeRequest` 解析同一 fixture，并从实际 corpus 独立重算 checksum。

## 验证

红阶段真实 loopback 观察到 Java active release 是旧 identity，Python 收到已认证的 `/analyze` 后返回 409，Java 保留稳定 `KNOWLEDGE_RELEASE_MISMATCH`，没有生成 fallback。修复后，隔离 test-profile HTTP 验证：BILLING caller 返回 `200 SUCCEEDED` 并有证据/引用；缺少 scope 返回 `200 FALLBACK` 且证据/引用均为零；Java search 的缺失 scope 返回 `[]`，每种规范 scope 只能返回所属目录片段，碰撞 query、document id 或伪造范围 header 无法扩大结果；匿名 search 返回 401，删除 active pointer 时 search 返回既有 409；匿名创建 release 返回 401，agent 创建返回 403；激活未部署 release 后分析返回非 fallback 409；回滚基线后恢复 `200 SUCCEEDED`。自动化命令与日志见 `.omo/evidence/task-8-enterprise-minimum-pilot.md`。

## 限制

Python 仍在进程启动时加载单个 file-backed corpus，Java 发布不会触发热加载。新 release 的 corpus 尚未部署时，409 失败关闭是预期安全边界；本轮只实测了回滚到已加载基线后的恢复，没有把动态部署或持久化 Embedding artifact 归入 Task 8。Task 9 负责 artifact 生命周期，Task 15 负责 MySQL 8 的 migration、锁和事务 parity。本轮只使用 H2、mock Python、合成 JWT/工单和本地 loopback，不代表生产运行或真实客服效果。
