# 切片参数化与切片粒度实验（2026-09-18）

> 历史证据说明：以下结果保留为当时实验记录。后续[对抗式审查](../adversarial-review-2026-09-18/README.md)要求离线重算绑定执行时计划与 query 向量摘要；本轮旧缓存不含该信息，当前 CLI 会拒绝它。不得补写事后哈希冒充原始取证，也不得自动重跑付费实验。

> 结论一：切片参数（窗口 / 步长 / 每领域题数）已从硬编码改为命令行参数，默认参数经过自检证明仍能**逐字段复现冻结产物**，因此旧证据继续有效。
>
> 结论二：把切片从 2000/1600 改成 **1000/800** 后重跑同一批 40 题，片段数 1564 → **3015**（成本约翻倍），而 **gold@3 完全不变（32/40）**，gold@1 20→22，MRR 0.625→0.667，逐题 8 好 7 坏（净 +1）。**更细的切片没有带来可测量的质量收益**，切片粒度不是当前检索的瓶颈。
>
> 本轮消耗：3015 次文档 embedding（建索引）+ 40 次 query embedding，0 次生成调用。artifact 建在独立 root，未触碰现有 active artifact。

## 1. 切片参数化

改了两个文件，都保持向后兼容：

| 文件 | 改动 |
| --- | --- |
| `scripts/benchmark/prepare-doc2dial.mjs` | 新增 `--window` / `--stride` / `--per-domain` / `--output` / `--source` / `--verify-against`；切片逻辑抽成可测函数；新增 `chunking.json` 记录切片身份 |
| `services/support-copilot-ai/evaluation/build_benchmark_index.py` | 不再硬编码 chunking_version，改为从 corpus 目录的 `chunking.json` 读取；缺文件时 fail-closed（可显式 `--chunking-version` 覆盖）；`index-build.json` 记录切片身份与相对路径 |

两个关键设计：

- **切片身份由参数唯一决定**：`doc2dial-codepoints-{window}-{stride}-v1`。默认参数得到的正是历史值 `doc2dial-codepoints-2000-1600-v1`，所以新旧 artifact 不可能撞版本，也不会意外复用。
- **步长大于窗口直接拒绝**：那会静默丢掉两段之间的文档内容。`validateChunking` 会失败退出。

自检（`--verify-against`）比对了 `corpus.json` / `chunk-map.json` / `cases.json` / `protocol.json`（除 `frozen_at`）并与冻结目录完全一致：

```
{"verified":true,"chunks":1564,"cases":32,
 "corpusChecksum":"9c1e91d5fff7f1b9…",
 "chunkingVersion":"doc2dial-codepoints-2000-1600-v1"}
```

测试：`prepare-doc2dial.test.mjs` 12 项 + `test_benchmark_index.py` 7 项。

## 2. 新切片的重建

```bash
# 1) 生成新切片语料（零调用，约 10 秒）
node scripts/benchmark/prepare-doc2dial.mjs --window 1000 --stride 800 \
  --output .local/chunking-variants/1000-800

# 2) 建立独立的 artifact（3015 次 embedding，49.6 秒）
cd services/support-copilot-ai
.venv/bin/python -m evaluation.build_benchmark_index \
  <仓库>/.local/chunking-variants/1000-800/corpus.json \
  <仓库>/.local/chunking-variants/1000-800/artifacts
```

**隔离**：新 artifact root 是 `.local/chunking-variants/1000-800/artifacts`，与在用的 `.local/business-benchmark-runtime/artifacts` 完全分开，因此 `activate()` 不会切换当前检索用的 artifact。

| | 2000/1600（冻结） | 1000/800（新） |
| --- | ---: | ---: |
| 片段数 | 1564 | **3015** |
| 片段长度 p50 | 1998 | 999 |
| 建索引 embedding | — | 3015 次 / 49.6 秒 |
| artifact | `2ecf19dd…` | `e418567d…` |
| release_id | `…benchmark-v1` | `…benchmark-1000-800-v1` |
| chunking_version | `…codepoints-2000-1600-v1` | `…codepoints-1000-800-v1` |

## 3. 结果：40 题上的切片对比

同一批 development 40 题、同一套 query、同一套评分口径：

| 指标 | 2000/1600 | 1000/800 | 变化 |
| --- | ---: | ---: | --- |
| gold@1 | 20/40（50.0%） | 22/40（55.0%） | +2 |
| gold@3 | **32/40（80.0%）** | **32/40（80.0%）** | **0** |
| MRR | 0.625 | 0.667 | +0.042 |
| 空结果 | 0 | 0 | — |
| 平均 gold 片段数 | 3.25 | 6.40 | 更细切片把同一文档切成更多片段 |

逐题排名变化：**不变 25 题、变好 8 题、变差 7 题**（净 +1，McNemar 精确检验 p ≈ 1.0，无法区分于随机）。

一个值得注意的细节：1000/800 让平均 gold 片段数从 3.25 涨到 6.40——每道题的"命中彩票"几乎翻倍，而且候选上限仍是 top_k=3，但 **gold@3 一点没变**。这说明瓶颈不在"文档被切得太粗所以命中不了"，而是排序本身。

全库召回（`gold-rank.json`）也基本持平、略有改善：

| k | 2000/1600 | 1000/800 |
| ---: | ---: | ---: |
| 1 | 20/40 | 22/40 |
| 3 | 32/40 | 32/40 |
| 6 | 36/40 | 37/40 |
| 10 | 37/40 | **38/40** |

## 4. 融合在两个切片下的表现

零调用、复用各自缓存的向量：

| 配置 | 2000/1600 gold@3 | 1000/800 gold@3 |
| --- | ---: | ---: |
| vector-only | 32/40 | 32/40 |
| **rrf-equal k=60（主对比）** | **36/40** | **37/40** |
| 改善 / 退化 | 5 / 1 | 7 / 2 |
| 不一致样本数 | 6 | 9 |
| McNemar p | 0.2188 | **0.1797** |

**融合的提升不依赖切片粒度**（两个切片下都提升，方向一致），这是它比"切片调参"更值得继续投入的原因。但两个切片下都**没有达到统计显著**，所以仍然不修改生产检索。

## 5. 结论

1. **切片粒度不是瓶颈**。把片段切小一倍、片段数翻倍，gold@3 一动不动。继续在切片上花 embedding 预算不会换来质量。
2. **真正起作用的是排序**。融合在两个切片下都带来 +4～+5 的 gold@3，方向稳定，只是样本量还不足以判定显著。
3. **成本结论**：1000/800 让建索引成本翻倍（1564 → 3015 次 embedding），换来的只是 MRR +0.042 和净 +1 题。若考虑默认配置变更，理由不足。

## 6. 附带修复：评测器现在会拒绝错配的语料

本轮犯过一次真实错误：给 1000/800 的运行评分时忘了传 `--corpus`，评测器用默认的 2000/1600 语料去匹配，结果所有候选都找不到，报出 `gold@1 0/40` 这种看起来像"质量崩塌"的假结论。

`retrieval-eval.mjs` 现在会统计候选 chunk_id 是否属于被评分的语料，**不匹配率超过 10% 就直接报错**，并在 summary 里输出 `corpusMismatchRate`。测试覆盖了"拒绝"和"正常不误报"两条路径。

## 7. 复现

```bash
node scripts/benchmark/prepare-doc2dial.mjs --window 1000 --stride 800 --output <目录>
cd services/support-copilot-ai
.venv/bin/python -m evaluation.build_benchmark_index <目录>/corpus.json <目录>/artifacts
.venv/bin/python -m evaluation.retrieval_only \
  --inputs docs/verification/retrieval-cases-expanded-2026-09-18/inputs-development.json \
  --corpus <目录>/corpus.json --artifact-root <目录>/artifacts \
  --chunking-version doc2dial-codepoints-1000-800-v1 \
  --output docs/verification/chunking-1000-800-2026-09-18 --execute
cd <仓库>
node scripts/benchmark/retrieval-eval.mjs docs/verification/chunking-1000-800-2026-09-18 \
  --cases docs/verification/retrieval-cases-expanded-2026-09-18/cases.json \
  --corpus <目录>/corpus.json --json … --markdown …
```

语料（4.8MB）未入库，可由上面的命令确定性重建；证据目录里保留切片身份 `chunking.json` 与构建记录 `index-build.json`。

## 8. 限制

- 只有两个切片、40 道 development 题、单一 embedding 模型；不能外推到其他语料或生产知识库。
- 扩展题未审计，gold 是文档级匹配；指标只能横向比较，不能当作绝对质量。
- 切片参数变了就是新基线，与冻结集的绝对数字不可混算。
- 本轮没有改任何生产检索配置：默认仍是 2000/1600，active artifact 仍是 `2ecf19dd…`。
- 结果不构成"参数已调优"的结论：`1000/800` 只是在一次实验里看起来略好，没有独立验证。
