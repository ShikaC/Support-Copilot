# 检索-only 评测：query 截断修复后的真实召回（2026-09-17）

> 后续边界：本文保留当时的实验事实。推送前审查已加强缓存来源校验，本文旧缓存缺少执行时计划/向量摘要，不能直接用于当前 CLI 的新验收；详见[审查记录](../adversarial-review-2026-09-18/README.md)。不追补摘要，不自动重跑付费实验。

> 结论：**检索本身没有坏**。旧运行 gold@3 = 0% 的原因不是检索算法，而是 query 截断导致 13 题共用同一条查询。用生产同一套构造方式逐题重建 query 后，真实召回是 **gold@1 54.5% / gold@3 72.7% / MRR 0.636**，13 题产生 13 条不同 query、13 组不同候选。
>
> 本目录是一次**只调用 embedding、不调用生成模型**的检索基线，与预注册比较运行无关，不消耗 comparison claim。

## 1. 为什么需要单独做检索评测

旧运行的 13 题检索结果完全相同（1 条 query、1 组候选、0 命中）。这个数字无法判断检索质量，因为三种可能混在一起：query 构造错、检索算法差、切片不合适。

而 chat 端点不可用时无法重跑整批生成。检索只依赖 embedding 与已经构建好的向量 artifact，可以单独执行——这就是本目录的用途：**把 query 问题与检索问题分开测量**。

## 2. 结果

评测口径与工具见 `docs/verification/retrieval-eval-2026-09-11/README.md`；完整报告见 [REPORT.md](REPORT.md)。

| 指标 | 旧运行（query 截断） | 本次检索-only | 变化 |
| --- | ---: | ---: | ---: |
| gold@1 | — | 54.5%（6/11） | — |
| gold@3 | 0.0%（0/11） | **72.7%（8/11）** | +72.7pp |
| MRR | 0.000 | **0.636** | +63.6pp |
| 去重 query 数 | 1 | 13 | — |
| 去重候选集合数 | 1 | 13 | — |
| 空结果题数 | — | 0 | — |

按领域：dmv 3/3（100%）、studentaid 2/2（100%）、ssa 2/3（66.7%）、va 1/3（33.3%）。`va` 是最弱领域。

**3 道未命中的题不是“召回不到”，而是排序精度不够**：gold 片段在全库 1564 个片段中排名第 4、6、6，且 11 题的 gold 全部进入前 6（全库 recall@6 = 11/11）。详见 [GOLD-RANK-DIAGNOSIS.md](GOLD-RANK-DIAGNOSIS.md)。

2 题（`qa-gh-2661`、`qa-4db57972397af5cd2521167ba8fb5b2f-4`）按协议排除，不进入指标。

## 3. 怎么复现

```bash
cd services/support-copilot-ai

# 只做装配检查与计划，零外部调用
.venv/bin/python -m evaluation.retrieval_only \
  --output docs/verification/retrieval-only-2026-09-17

# 真实执行：每题一次 embedding，无生成调用
.venv/bin/python -m evaluation.retrieval_only \
  --output docs/verification/retrieval-only-2026-09-17 --execute

# 统一评分（离线，零调用）
cd ../.. && node scripts/benchmark/retrieval-eval.mjs \
  docs/verification/retrieval-only-2026-09-17 \
  --baseline docs/verification/retrieval-eval-2026-09-11/baseline-diagnostic-2026-09-10.json \
  --json docs/verification/retrieval-only-2026-09-17/evaluation.json \
  --markdown docs/verification/retrieval-only-2026-09-17/REPORT.md
```

## 4. 这次运行到底做了什么

| 项目 | 值 |
| --- | --- |
| 模式 | `retrieval-only`（`retrieval-only-manifest.json` 记录） |
| embedding 调用 | 13（每题 1 次） |
| 生成调用 | **0** |
| chat 端点 | 未使用 |
| 语料 | `doc2dial-business-benchmark-v1`，1564 片段 / 488 文档 |
| artifact | `2ecf19dd9cd4a2a6…`，1024 维，`doc2dial-codepoints-2000-1600-v1` |
| 检索参数 | top_n=10、top_k=3、min_score=0.35、allowed_scopes=GENERAL、ticket category=UNCLASSIFIED |

检索判定与生产 `LiveVectorIndex.search` 逐步对齐（范围过滤 → 余弦 → 阈值 → top_n → 类别重排 → top_k），并由 `tests/test_retrieval_only.py` 用同一份输入断言两条路径给出**完全相同的候选与分数**。工具本身不修改任何生产检索代码。

## 5. 文件说明

| 文件 | 内容 | 是否入库 |
| --- | --- | --- |
| `retrieval-plan.json` | 执行前的题目、query、参数与预估调用数 | 是 |
| `results.json` | 逐题检索结果，结构与运行记录一致 | 是 |
| `retrieval-only-manifest.json` | 执行时间、实际调用计数、命中题数 | 是 |
| `evaluation.json` / `REPORT.md` | 离线评分结果 | 是 |
| `gold-rank.json` / `GOLD-RANK-DIAGNOSIS.md` | 全库排名诊断与 recall@k 曲线 | 是 |
| `hybrid-experiment.json` / `HYBRID-EXPERIMENT.md` | 融合实验的机器可读结果与表格 | 是 |
| `HYBRID-ANALYSIS.md` | 融合实验的机制分析与统计判断 | 是 |
| `query-vectors.json` | 13 条 query 向量（341KB） | 否（可由计划重算） |

`query-vectors.json` 的用途是让后续**排序、阈值、top_k、融合**实验在同一批向量上离线复现，不需要新的外部调用；只有改动 query 文本或切片方式才需要重新调用 embedding。

## 6. 限制（不要据此下质量结论）

- 这是**检索**指标，不含生成、fallback、引用策略与人工审核；它不证明回答正确，也不代表客服可用性。
- gold 匹配是**文档级**：发布者标注的文档被切成多个片段，命中任一片段即算命中。chunk 级统计会低估当前表现，因此不要用本数字反推切片质量。
- 语料是 Doc2Dial 归档文档，不是真实客服知识库；`va` 领域的低分不代表生产表现。
- 使用的是 development 13 题，作者已见过它们的输出；holdout 仍未使用。
- 本次只改了「query 不再被截断」这一个变量，因此可以把前后差异归因于 query 构造；但同一批次里的其它检索改动没有对照组。

## 7. 下一步候选（按依赖顺序）

排序诊断把方向限制得很死：召回已经够用，改进空间在排序与上下文组装。融合实验（[HYBRID-ANALYSIS.md](HYBRID-ANALYSIS.md)）已经证明这条路上有收益，但**11 题的统计效力不足以验证任何检索改动**。

1. **先解决样本量**（最高优先级）：在 11 题上改检索永远会得到“不显著”的结论。新增独立题目或新增切片版本，并在动手改检索之前固定下来。
2. **换融合策略而不是调参数**：已确认的机制是“简单 RRF 无法抑制单边错误”（有 1 题从向量第 2 掉到融合第 15）。排名截断、分数归一化后加权、交叉编码器重排都能针对这个机制；应在扩容后的题目上做预注册对比。
3. **query 构造实验**：`bm25-only` 的 gold@1（8/11）高于 `vector-only`（6/11），说明当前 query 的字面词重叠很可能在帮忙。比较“只取末尾用户轮次”等变体只需要 13 次 embedding 调用。
4. **切片方式实验**：未命中的题 gold 只有 1–2 个片段，而 8 个片段的题排第 1。固定 query 与向量、只变切片，验证这个相关性观察。
5. **离线参数实验**：用 `query-vectors.json` 重跑 top_k、阈值等。注意 `top_k` 是成本决策，不要记作质量改进。
6. 待 chat 端点恢复后执行预注册的 development 比较，得到「检索 + 生成 + 引用」的完整对照。
