# 检索索引版本清单（2026-09-18）

> 结论一：Python 服务现在有一个**只读**的索引版本清单端点 `GET /knowledge/index/versions`，能列出 artifact root 下的所有版本、当前生效版本、上一版本，以及进程实际加载的语料身份。
>
> 结论二：**“切换索引”的写端点被有意移除**。原因是本轮发现的架构事实：artifact 的兼容校验会比 pair（release、corpus checksum、embedding 模型、chunking version），而 artifact id 由同一组字段决定——所以同一进程配置下**只可能存在一个 artifact**，热切换在当前架构下必然失败，包括回滚。
>
> 本轮消耗：0 次外部调用（纯本地文件读取）。

## 1. 新增能力

| 位置 | 内容 |
| --- | --- |
| `app/embedding_artifact.py` | `list_artifacts()` 返回 `ArtifactInventory`：每个版本的切片版本、行数、模型、语料校验和、是否 active/previous；损坏目录归入 `unreadable` 而不是让整个列表失败 |
| `app/live_vector_index.py` | `artifact_store` 属性（让管理与检索共用同一个 store 与 root）；`reload()` 丢弃缓存并重新加载 active，预加载成功才返回 |
| `app/knowledge.py` | `artifact_store`、`corpus_metadata`（当前语料身份）、`reload_index()` |
| `app/main.py` | `GET /knowledge/index/versions`，走内部服务鉴权 |

返回结构（真实输出）：

```json
{
  "activeArtifactId": "2ecf19dd…",
  "previousArtifactId": null,
  "unreadable": [],
  "corpus": {"releaseId": "doc2dial-business-benchmark-v1", "corpusChecksum": "9c1e91d5…", "chunkCount": 1564},
  "versions": [
    {"artifactId": "2ecf19dd…", "rowCount": 1564, "chunkingVersion": "doc2dial-codepoints-2000-1600-v1", "active": true},
    {"artifactId": "e418567d…", "rowCount": 3015, "chunkingVersion": "doc2dial-codepoints-1000-800-v1",   "active": false}
  ]
}
```

## 2. 为什么没有写端点

最初的实现包含 `POST /knowledge/index/versions/activate` 和 `POST /knowledge/index/rollback`，还有一个默认关闭的 `KNOWLEDGE_INDEX_MUTATION_ENABLED` 开关。它们通过了测试……直到我用**真实的两套切片**去跑：

```
尝试切到另一种切片: artifact-incompatible
指针未移动: 2ecf19dd9cd4a2a6
```

根因在 `_require_compatible`：

```python
expected = (corpus.release_id, corpus.release_version, corpus.corpus_checksum,
            provider_identity, model, chunking_version)
actual   = (manifest.release_id, manifest.release_version, manifest.corpus_checksum,
            manifest.provider_identity, manifest.embedding_model, manifest.chunking_version)
```

而 `_artifact_id` 又是用**同一组字段**加 `metadata_sha256` 算出来的。于是：

> 两个 artifact 能互相切换 ⟺ 它们的前六项相同 ⟹ 它们必然有同一个 artifact id。

结论：在同一进程配置下，**不存在两个可以互相切换的 artifact**。`activate` 只可能是空操作，`rollback` 只可能失败。

这不是 bug，而是设计意图的副作用：进程配置里的 `chunking_version` 是用来**防止用错索引**的。所以正确的结论不是“加个开关绕过它”，而是**这个操作在当前架构里不成立**。留着按钮只会让运维点完之后拿到一个 409 而不知道为什么。

因此最终交付里：写端点被删除，`KNOWLEDGE_INDEX_MUTATION_ENABLED` 与 `ActivateIndexRequest` 一并移除，测试改为断言这些路由**不存在**（404）。

## 3. 这意味着什么

**换切片 = 改配置 + 重启**，这是当前架构下的唯一路径：

```bash
# 1) 用新参数生成语料与索引（见 docs/verification/chunking-1000-800-2026-09-18/README.md）
# 2) 把服务配置指向新语料与新的 chunking_version
# 3) 重启服务；启动时 load_active() 会校验配置与 active artifact 一致
```

要让“前端点一下换切片”真正可行，需要一个明确的架构决策：**把 `chunking_version` 从校验字段降级为观测字段**。

- 现状：配置里的切片版本参与兼容校验 ⇒ 配置换了但索引没换（或反之）会立刻失败。
- 可选：只在 manifest 里记录切片版本用于展示，兼容校验只保留 release / corpus checksum / input format / dimension。因为 artifact 的每一行都与语料 chunk 顺序和内容校验和对齐，切片参数只影响“文档被切成什么样”，不影响“第 N 行是不是它声称的那块内容”。

这个改动的代价是失去一层保护（配置与索引错配时不再立刻报错），收益是索引可以真正热切换。**本轮没有做这个改动**：它改变了检索的安全边界，应该单独作为一片来评估，而不是顺手塞在版本清单里。

## 4. 复现

```bash
cd services/support-copilot-ai
SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN=probe-token .venv/bin/python - <<'PY'
# 见本目录 probe.json 的生成方式：构造指向真实 artifact root 的 Settings，
# 用 TestClient 调 GET /knowledge/index/versions，并尝试切换另一种切片。
PY
```

证据文件 `probe.json` 记录了：端点真实返回、错误 token 的 401、已移除写端点的 404、跨切片切换的 `artifact-incompatible`、以及拒绝之后指针没有移动。

测试：`tests/test_index_versions.py` 10 项（空 root、active/previous 标记、损坏目录、跨切片拒绝、幂等激活、回滚拒绝、`reload` 真的重读指针而非复用缓存、鉴权、清单内容、写端点不存在）。

## 5. 限制

- 清单只反映**本机 artifact root**；跨主机的 artifact 分布不在范围内。
- `modifiedAt` 是文件系统时间，只用于展示，不是构建证据。
- 没有把清单接到 Java 或前端：本轮只做 Python 侧能力，接入是下一片。
- 本机为了演示，把 1000/800 的 artifact 复制进了 runtime root；这不改变任何 active 指针，也不影响证据目录。
- 结论只覆盖当前单进程架构；多副本部署下每个副本仍需按同一配置启动。
