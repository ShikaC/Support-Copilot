# Embedding 输入协议修复与真实 A/B 证据

已验证：原先 LangChain 默认将中文输入编码为 OpenAI cl100k token ID 后发送给 Qwen 兼容接口，导致错误检索。相同 10 个知识片段、相同 3 个合成查询，只切换 `check_embedding_ctx_length`，正确 top-1 从 0/3 变为 3/3。此小样本用于根因验证，不代表完整 RAG 质量基线。

## 真实调用

- 模型：Qwen/Qwen3-Embedding-0.6B；维度 1024。
- 时间、知识 checksum、逐条排名和分数见 `ab.json`。
- 8 次 embedding 请求，0 次 chat 请求；未记录或输出凭据。
- SSO 查询：旧 top-1 `chunk-invoice-03`，新 top-1 `chunk-account-sso-01`（0.697572）。
- 发票查询：旧 top-1 `chunk-refund-02`，新 top-1 `chunk-invoice-03`（0.821701）。
- 导出查询：旧 top-1 `chunk-billing-07`，新 top-1 `chunk-export-04`（0.713836）。
- 可复现脚本 `ab.py` 使用本地服务配置；从 AI 服务目录执行 `PYTHONPATH=. .venv/bin/python ../../docs/verification/live-baseline-2026-09-09/embedding/ab.py` 会再次产生真实 embedding 调用。该脚本不调用聊天模型、不修改现有 artifact 或 `.env`。

## 实现与兼容边界

`OpenAIEmbeddingProvider` 显式设置 `check_embedding_ctx_length=False`，文档和查询统一发送原始字符串，由目标提供方按自身 tokenizer 处理。远程输入超过模型限制时保持真实供应方错误，不在客户端偷偷截断。

新 manifest 写入 `input_format=raw-text-v1`，该值参与 artifact identity。缺少此字段的旧 manifest 解析为 `legacy-tokenized-v1`，加载和激活时拒绝为 `artifact-input-format-incompatible`。因此同一 corpus/model/dimension 的构建仍会获得新 ID 并重新计算，不会静默复用旧矩阵。旧目录与 active pointer 不被兼容层自动覆盖；根任务负责显式构建和切换。

## 回归证据

先写并运行失败测试：`wire-red.log` 两项失败，观察到真实序列化后的整数 token 列表；`artifact-red.log` 两项失败，证明旧实现接受无格式 artifact 且重建复用旧 ID。随后应用修复。

命令（AI 服务目录）：`.venv/bin/python -m pytest tests/test_embedding_provider_wire.py tests/test_embedding_input_compatibility.py tests/test_embedding_artifact_store.py tests/test_embedding_artifact_cli.py tests/test_knowledge.py -q`。结果：25 passed in 2.36s，见 `focused-green.log`。

`uvx ruff check app/embedding_provider.py app/embedding_artifact_models.py app/embedding_artifact.py tests/test_embedding_provider_wire.py tests/test_embedding_input_compatibility.py` 通过，见 `lint.log`。全套回归由根任务在并行评估修改完成后执行；本报告不将并行工作期间的整套结果声称为全量通过。

Git HEAD：`4df3bf44907c34318132496929bad4a3974ad88b`，分支 `master`，工作区非干净。本报告绑定 `source-hashes.json` 中的当前未提交工作区文件，测试证据不能仅由 HEAD 复现。实现仅涉及输入序列化和 artifact 兼容性，不改变业务审核、访问范围或检索阈值。ArtifactStore 为 248 行非空非注释代码，接近文件大小限制；本轮没有增加独立功能或额外抽象。新增类型为明确 Literal，未增加 Any/cast/异常吞错。

参考：[LangChain OpenAIEmbeddings check_embedding_ctx_length 官方说明](https://reference.langchain.com/python/langchain-openai/embeddings/base/OpenAIEmbeddings/check_embedding_ctx_length)。根因结论以本地 wire 回归和真实 A/B 为直接证据。
