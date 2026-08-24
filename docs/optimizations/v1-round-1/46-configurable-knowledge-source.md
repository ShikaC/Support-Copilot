# 优化 46：支持经过校验的外部知识源

## 业务问题

Python 虽然已有正式 Embedding 和聊天模型入口，但知识检索始终硬编码读取仓库内的 `app/data/knowledge.json`。这意味着 live 模式也只能处理演示知识，无法安全接入经过授权的公开文档、内部支持手册或脱敏知识快照。

## 改进方案

新增 `KNOWLEDGE_PATH` 配置，允许 Python 从仓库外的绝对路径加载预切分 JSON。文件进入检索流程前必须通过 Pydantic 结构解析：字段不能为空、未知字段被拒绝、分类和关键词至少各有一项，并且 `chunk_id` 在整个文件内唯一。

知识校验失败会阻止服务启动，不会退回仓库演示数据，也不会把无效数据静默当作证据。对外抛出的错误只包含文件路径和错误数量，原始 Pydantic 校验异常被切断，避免知识正文进入启动日志。

live 验收预检同时加载该文件，并记录以下可追溯信息：

```text
repository-default 或 configured-external
知识片段数量
知识文件 SHA-256
```

本地路径和知识正文不会进入 live 证据。

向量集成测试还暴露了一个此前被 mock 路径隐藏的运行缺陷：LangChain `InMemoryVectorStore` 的余弦相似度计算依赖 NumPy，但原生产依赖没有声明它。生产范围和两份带哈希锁文件现已加入 NumPy，live 向量检索不会在 Embedding 完成后因本地缺包崩溃。

## 当前验证

- 红灯测试证明原实现忽略自定义路径，仍返回 10 条仓库演示知识。
- 配置自定义文件后，检索器只加载该文件，并返回其中的自定义片段。
- 红灯测试证明原实现会接受重复 `chunk_id`。
- 结构化知识边界会拒绝重复 ID，并抛出 `KnowledgeSourceInvalidError`。
- 隐私故障测试证明原始 Pydantic 校验异常不会保留为 cause，知识正文不会进入异常链。
- 向量集成测试在缺少 NumPy 时稳定失败；按新开发锁安装 `numpy 2.4.6` 后，同一测试通过并返回 `VECTOR` 证据。
- Python 全量测试：56 条通过；固定 mock 评估：18 条通过，失败案例为 0。
- 依赖锁检查和 `pip check` 通过，生产与开发锁文件均包含 Python 3.11 对应的 NumPy 版本与哈希。
- 使用 `/dev/null` 作为知识源时，Python 启动明确失败，只输出路径和 1 个校验错误，不回显正文。
- 实际启动 Python HTTP 服务并配置仓库外单片段文件后，`/health` 返回 `knowledgeChunks=1`，`/analyze` 返回外部 `external-login-runbook` 证据和指定 `traceId`。
- `check-live-rag.sh --preflight` 会在不调用外部 API 的情况下验证知识文件，并输出来源类型和片段数量。

## 能力边界

本轮解决的是“可配置并校验外部预切分知识文件”，不是完整知识平台。项目仍缺少原始 Markdown/PDF 导入、自动切分、增量更新、版本审批、持久化向量索引和权限过滤。外部文件是否真实、是否获授权仍由数据提供者负责；代码不能自行证明数据合规。

后续状态：第 47 轮已经补充 Markdown 和文本型 PDF 的确定性构建入口与 provenance 校验；扫描件 OCR、增量更新、审批和持久化索引仍未完成。
