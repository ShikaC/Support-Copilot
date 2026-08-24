# 优化 47：从 Markdown 和 PDF 构建可追踪知识

## 业务问题

第 46 轮允许服务加载仓库外的知识 JSON，但数据提供者仍需要手工切块和填写每个 `chunk_id`。这个过程难以重复，也无法证明某份知识 JSON 来自哪些原始文件；正文变化后仍可能错误沿用旧的来源说明。

## 改进方案

新增 `scripts.build_knowledge_corpus` 命令。它读取仓库外的 JSON 清单，并按以下流程构建知识：

```text
授权清单
-> 限制源文件只能位于清单目录内
-> Markdown 按标题分节、PDF 按页提取文本
-> RecursiveCharacterTextSplitter 确定性切块
-> 内容与文档版本共同生成稳定 chunk_id
-> 输出知识 JSON
-> 输出不含正文的 provenance
```

清单必须显式声明文档 ID、标题、来源 URI、分类、关键词、版本、发布状态和更新时间。只有 `PUBLISHED` 内容进入检索；`ARCHIVED` 用于记录来源状态，不作为证据。

provenance 保存 corpus SHA-256、清单 SHA-256、索引版本、切块参数、源文件 SHA-256 和片段 ID。设置 `KNOWLEDGE_PROVENANCE_PATH` 后，Python 启动时会验证 provenance 与 corpus 是否一致；文件缺失、格式非法或哈希漂移都会阻止启动。live 验收记录这些脱敏字段，但不记录本地路径和正文。

## 当前验证

- 红灯测试证明仓库原来没有原始文档构建命令；实现后，同一 Markdown 输入重复构建得到完全相同的 corpus 和 provenance。
- PDF 专项测试使用真实文本层，生成的证据保留 `Page 1`，并能由现有知识加载器读取。
- 测试过程中发现冻结 dataclass 异常会阻止 `contextlib` 写入 traceback；专项红灯复现二次 `TypeError`，改为普通类型化异常后恢复原始错误。
- 空的 `KNOWLEDGE_PROVENANCE_PATH` 配置红灯证明其原先会变成 `Path('.')`；设置层现在忽略空环境值并保持 `None`。
- Python 全量测试：61 条通过；固定 mock 评估：18 条通过，失败案例为 0。
- 故障演练证明目录逃逸、无文本 PDF 和 provenance 哈希漂移都会被拒绝。
- 实际 CLI 从一份 Markdown 和一份 PDF 生成 2 个片段及索引版本。
- 使用生成结果启动 FastAPI 后，`/health` 返回 `knowledgeChunks=2`；`/analyze` 保留 `qa-raw-docs-01`，并命中 PDF 的 `proxy-runbook`、`Page 1` 证据。

## 能力边界

本轮证明的是原始文档可以重复转换并进入本地 RAG 检索，不是正式模型 API 已成功调用。HTTP 验证运行在 mock 分析模式；正式聊天模型与 Embedding API 的 live 成功记录仍需凭据、网络和调用预算。

PDF 必须包含可提取文本层，扫描件 OCR 尚未实现。当前每次构建仍是全量重建，向量索引仍位于 Python 进程内存；增量更新、审批发布、权限过滤和持久化向量索引属于后续成熟 RAG 范围。
