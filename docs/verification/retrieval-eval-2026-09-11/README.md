# 离线检索评测基线（2026-09-11）

> 状态：**工具已实现并验证；修复前基线已冻结。** 本目录不包含任何模型调用结果。
>
> 相关事实：[当前状态](../../STATUS.md)、[query 修复交付](../query-context-fix-2026-09-10/README.md)、[隔离运行器操作说明](../isolated-runner-2026-09-10/OPERATIONS.md)、[修正后比较协议](../development-comparison-2026-09-11/PROTOCOL.md)。

## 1. 这份记录解决什么问题

在它之前，"检索好不好"只能通过生成模型的成败来判断：模型说证据不足，就无法区分是**没检索到**、**检索到了但排序靠后**，还是**检索到了但模型没用**。每改一次分块、检索方式或阈值，也只能付一次真实调用费才知道结果。

`scripts/benchmark/retrieval-eval.mjs` 把这件事变成离线、可复现、零费用的数字：把运行记录里的候选片段与评估集里发布者标注的文档比对，直接给出 gold@k 与 MRR。

## 2. 指标口径

| 指标 | 定义 |
| --- | --- |
| `gold@k` | 前 k 个候选中是否出现 gold 文档的任一片段 |
| `MRR` | 第一个 gold 片段排名的倒数均值；未命中记 0 |
| `去重 query 数` | 已执行题目中不同 query 的数量，用于发现"所有题共用一条查询" |
| `去重候选集合数` | 不同候选片段列表的数量，用于发现"所有题返回同一批片段" |

gold 文档是 `cases.json` 里 `source.document_id`（Doc2Dial 原始文档标识），通过与语料 `source_uri` 的 anchor 匹配到 `corpus.json` 的 `document_id`。一个文档被切成多个片段时，命中任一片段即算命中。

## 3. 用法

```bash
node scripts/benchmark/retrieval-eval.mjs <runDir> \
  --label "人类可读的标签" \
  --json   <输出报告.json> \
  --markdown <输出报告.md> \
  --baseline <旧报告.json>          # 可选，输出对比表
```

只读取三份输入，全部来自本地文件，不产生网络请求：

- `<runDir>/results.json`（隔离运行器或业务运行的逐题结果）
- `docs/verification/quality-input-audit-2026-09-10/cases.json`
- `docs/verification/business-benchmark-2026-09-10/corpus.json`

## 4. 修复前基线（`baseline-diagnostic-2026-09-10.json`）

来源：`docs/verification/quality-runs/development-live-diagnostic-20260910`，即 query 截断修复之前的 13 题真实诊断运行。

| 指标 | 值 |
| --- | --- |
| 计划题数 / 已执行 | 26 / 13 |
| 可评估题数（有 gold 文档） | 11 |
| gold@1 / @3 / @10 | 0 / 11（0.0%） |
| MRR | 0.000 |
| gold 文档平均片段数 | 3.00 |
| 去重 query 数 | 1 |
| 去重候选集合数 | 1 |

结论：13 题共用一条被截断的 query，因此返回完全相同的候选片段，发布者标注文档一次都没有进入候选。**这是有效故障诊断，不是检索能力的正常基线**——本目录不把它当作"修复后仍然如此"的证据。

## 5. 与既有指标的关系

`scripts/benchmark/summarize-business.mjs` 的 `gold_document_hit` 是本指标在 32 题 × 3 并发业务运行中的一次具体应用，口径相同（Top 3 是否含标注文档）。本工具是它的抽取与泛化：接受任意运行目录，输出 gold@1/@3/@10、MRR 与逐题明细，并额外诊断 query 与候选的重复度。

## 6. 已知限制

- gold@k 不表示片段包含答案，也不表示模型正确使用了它；它只衡量检索是否把正确文档找回来。
- 2 题公开 issue 摘录没有文档级 gold，不计入召回指标。
- 评估集中 `included: false` 的 2 题按冻结协议排除。
- 11 题有 gold 的样本量偏小，只能用于同一语料、同一评估集下的相对比较，不能外推为通用召回率。
- 本工具不调用模型，因此**不能**替代真人回答审核，也不能证明回答说对了。

## 7. 下一步怎么用

1. 比较协议执行后，对新的运行目录重跑本工具，即可得到修复后的真实 gold@3 与 MRR（`--baseline` 指向本目录的报告）。
2. 检索改动（分块、混合检索、重排、参数）先在离线评测上比较，再决定是否花真实调用。
3. 任何改动都必须保持同一评估集、同一语料、同一口径；换语料或换评估集要新建目录与新的对比基线。
