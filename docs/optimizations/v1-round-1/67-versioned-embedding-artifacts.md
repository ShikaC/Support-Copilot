# 第 67 轮：持久化版本化 Embedding artifact

## 问题与风险

Task 8 的 live 检索在每个 Python 进程内按访问范围创建 `InMemoryVectorStore`。进程重启或新实例首次查询会再次把文档发送给 Embedding provider，增加启动延迟、费用和外部数据暴露次数，也没有可验证的构建、激活或回滚边界。

## 修改层与流程

Python 新增 typed artifact models、provider abstraction、file-backed store 和 lifecycle CLI。artifact identity 绑定 knowledge release、semantic corpus checksum、脱密 provider endpoint、model、精确 dimension、chunking/schema version 与 ordered chunk/document checksums，因此 provider 调用前可确定目标；matrix 使用 NumPy `float32` `.npy`，其实际内容仍由 manifest 中的文件 SHA-256 完整校验。metadata 和 manifest 使用严格 JSON，不保存正文、凭据或 provider response。

构建先按 identity 检查并完整验证已有目标；同一 store 的并发调用在进程内锁中再次检查，命中时不调用文档 Embedding。损坏或不兼容的既有目标返回 typed integrity error，不覆盖、删除或改变 active pointer。只有缺失目标才请求一次 release 全量文档 vectors，验证 batch count、dimension 和 finiteness，再写唯一临时同级目录并 fsync。完整 candidate 自验证后原子 rename；activation 重新验证 candidate，再原子替换只含 active/previous identity 的 pointer。失败不会修改旧 pointer。rollback 只切回重新验证且与当前 corpus/model/config 兼容的 previous artifact。

live 检索首次访问才验证 active artifact。request release 仍先与已加载 corpus 比较；允许范围映射成 row indices 后才切片 matrix 并计算 cosine score。空范围在 artifact/provider 前返回零命中。artifact 错误降低 index readiness 并保留 liveness，不转换成 AI fallback。

## 验证证据

- `tests/test_index_lifecycle.py`：重启零文档 Embedding、ranking 一致、rollback ranking、readiness/liveness、空范围和 pre-score scope filter。
- `tests/test_embedding_artifact_store.py`：identity、corruption/hash/model/dimension/release/order mismatch、atomic pointer、rollback、并发 convergence、redaction。
- `tests/test_embedding_artifact_cli.py`：corrupt verify 非零退出和稳定脱密错误。
- `.omo/evidence/task-9-enterprise-minimum-pilot.md`：RED/GREEN、完整 Python 门禁和手工临时目录 lifecycle。

## 当前限制

本轮 fake provider 证据只证明本地文件系统生命周期。没有构建或提交真实 provider vectors，没有热加载 Java release，没有验证 NFS/共享卷、多主机锁、生产性能或容量，也没有引入向量数据库。真实 live artifact 仍需使用获授权/脱敏 corpus 和实际 provider 单独构建、核对与部署。
