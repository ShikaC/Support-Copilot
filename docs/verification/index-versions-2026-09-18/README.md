# 检索索引的版本清单与热重载（2026-09-18）

> 结论一：Python 服务现在有 `GET /knowledge/index/versions`，只读列出 artifact root 下的所有版本、当前生效版本、上一版本、每个版本的切片身份与行数，以及进程实际加载的语料身份。
>
> 结论二：**索引可以热重载**（`POST /knowledge/index/reload`，默认关闭）。在真实语料与真实 artifact 上验证：先在磁盘上换语料与索引指针，再调一次 reload，**1686 ms** 完成 1564 → 3015 chunks 的切换，进程不重启。
>
> 结论三：安全边界没有被拆掉。只换语料不换索引时返回 **409 `INDEX_VERSION_UNUSABLE`**，进程继续服务旧快照——因为语料身份（release + corpus checksum）与**逐行 chunk 对齐**校验仍然生效。
>
> 本轮消耗：0 次外部调用（只读本地文件 + 加载已缓存的向量矩阵）。

## 1. 先说清楚：为什么最初的做法行不通

第一版实现是 `POST /versions/activate` 与 `POST /rollback`。测试全绿，但用**真实的两套切片**一跑就暴露了：

```
尝试切到另一种切片: artifact-incompatible
指针未移动: 2ecf19dd9cd4a2a6
```

根因是 `_require_compatible` 用来校验的字段（release、corpus checksum、embedding 模型、**chunking version**）与 `_artifact_id` 用的是同一组字段，于是“两个能互相切换的 artifact”根本不存在。

但这暴露的其实是一个**设计错位**，而不是一条不可逾越的约束：

- **真正**该保护的是“索引的每一行是不是它声称的那块内容”——这由 `corpus_checksum` 与逐行 `(chunk_id, content_checksum)` 对齐保证；
- **`chunking_version` 是标签**，它描述“这份语料是怎么切出来的”，而不是索引正确性的证据。拿配置里的标签去比对，只会让“索引跟随语料一起换”这条路被堵死。

而且：**换切片必然换语料**（切片参数决定 chunk 集合），所以 `activate` 这类“只换索引不动语料”的接口在语义上就是错的——语料不换，索引本来就不该换。

## 2. 改了什么

| 位置 | 改动 |
| --- | --- |
| `app/embedding_artifact.py` | `_require_compatible` 不再比对 `chunking_version`；`_artifact_id` 接受 `chunking_version` 参数，校验落盘 artifact 时用 **manifest 自己声明的值**重算 id（否则换过切片的索引会被误判成篡改） |
| `app/knowledge.py` | 新增 `RetrievalState(corpus, live_index)` 快照；检索路径只取一次引用；`reload_index()` 先构建新快照、成功后原子替换 |
| `app/live_vector_index.py` | `reload()` 丢弃缓存并重新加载 active，预加载成功才返回 |
| `app/readiness.py` | 新增 `record_index_success()`（只清索引侧失败标记，不动 embedding provider 状态） |
| `app/main.py` | `POST /knowledge/index/reload`，受 `KNOWLEDGE_INDEX_MUTATION_ENABLED`（默认关闭）与内部服务鉴权双重保护 |
| `evaluation/live_verifier.py` | **未改动**：评测取证仍要求 artifact 的 chunking_version 与记录一致，那是证据绑定，不是运行时保护 |

`chunking_version` 从**校验字段**降级为**观测字段**：它现在由 artifact 自己声明，通过 manifest 对外暴露（清单里可见）。

## 3. 运维顺序（重要）

热切换是三件事，顺序不能乱：

```bash
# 1) 换上新的语料文件（同一个 knowledge_path，原子替换）
# 2) 用新语料建索引，并把 active 指针指过去
#    注意：不能用运行中进程的旧 store 去激活——它的 corpus 已经过期，会被正确拒绝
.venv/bin/python -m evaluation.build_benchmark_index <新语料> <artifact-root>
# 3) 让服务重载
curl -X POST http://localhost:8080/knowledge/index/reload \
     -H "X-Internal-Service-Token: $TOKEN"
```

第二步如果偷懒（直接改指针、跳过用新语料建索引），第三步会失败——这正是我们要的。

## 4. 真实证据

`probe-reload.json` 记录了一次完整演练（真实 3.8 MB / 4.8 MB 语料，真实 artifact `2ecf19dd…` 与 `e418567d…`）：

| 场景 | 结果 |
| --- | --- |
| 启动 | `doc2dial-business-benchmark-v1`，1564 chunks |
| 无变化时 reload | **200** |
| 只换语料、不换索引 | **409** `INDEX_VERSION_UNUSABLE`，进程仍是 1564 chunks（旧快照保住） |
| 换语料 + 换索引后 reload | **200**，**1686 ms**，release 变为 `…-1000-800-v1`，3015 chunks，进程内 `chunk_count` 同步为 3015 |

`probe.json` 记录的是另一件事：用**过期语料的 store** 去激活另一种切片的 artifact 会被拒绝（`artifact-incompatible`）——这条结论**现在依然成立**，因为 release 与 corpus checksum 本来就不同。

演练结束后 `active.json` 已恢复为 `2ecf19dd…`，生产检索路径未受改动。

## 5. 测试

`tests/test_index_versions.py` 16 项，覆盖：

- 空 root、`active`/`previous` 标记、损坏目录归入 `unreadable`
- 同一语料、不同切片标签的 artifact **可以**切换（标签不再是硬门槛）
- **不同语料**的 artifact **仍然被拒绝**（真正的安全边界）
- 回滚在同一语料的多版本间可用
- `reload()` 真的重读指针（把指针指向不存在的 id 会抛错，证明没有复用缓存）
- reload：无变化 200、只换一半 409 且旧快照不变、换齐后语料与索引一起生效
- **检索端到端**：重载后 `search` 命中的内容来自新语料（同 chunk_id、新正文）
- 鉴权（401 优先于功能开关）、开关关闭时 403

全量 Python 375 项通过。

## 6. 现在的状态与下一步

已经具备：切片参数可配（命令行）→ 索引可列表 → 索引可热重载。

**还没有**：前端入口。要让“点一下换切片”真正可用，还需要：

1. **重建作为后台任务**：`POST` 触发构建（数千次 embedding、约 50 秒），轮询进度；现在只能手工跑 CLI。
2. **Java 转发 + 前端面板**：把清单与重载暴露到 `KnowledgeView`。
3. **语料写入流程**：上传文档 → 解析 → 切片 → 生成语料文件（目前语料由离线脚本生成）。

## 7. 限制

- 热重载是**整个进程级**的：重载期间新请求会短暂用到旧快照（安全，但可能看到一个瞬时混合），不做版本化的灰度。
- 语料与索引必须**成对**替换；多副本部署要逐个重载，没有协调机制。
- `provider_identity` 与 `embedding_model` 仍在校验范围内：换 embedding 模型需要改配置并重启（合理，因为查询也要用同一模型）。
- 清单只反映本机 artifact root；`modifiedAt` 是文件系统时间，不是构建证据。
- 本机为了演示把 1000/800 的 artifact 复制进了 runtime root，未改变证据目录，也未改变生产配置默认值。
