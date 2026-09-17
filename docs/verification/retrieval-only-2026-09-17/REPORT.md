# 离线检索评测：development 13 题检索-only（query 截断修复后）

- 运行结果：`docs/verification/retrieval-only-2026-09-17/results.json`
- 评估集：`docs/verification/quality-input-audit-2026-09-10/cases.json` (sha256 7e78989315fd7991…)
- 知识语料：`docs/verification/business-benchmark-2026-09-10/corpus.json` (sha256 e9c1795210db5a33…)
- 语料规模：1564 个片段 / 488 份文档

本报告由 `scripts/benchmark/retrieval-eval.mjs` 离线生成，不调用任何模型；它只判断候选片段是否属于发布者标注文档，不代表回答的事实正确率。

## 汇总

| 指标 | 值 |
| --- | --- |
| 计划题数 / 已执行 | 26 / 13 |
| 按协议排除的题数 | 2 |
| 可评估题数（有 gold 文档）| 11 |
| 无 gold 标注（不计入指标）| 2 |
| gold@1 | 6/11 (54.5%) |
| gold@3 | 8/11 (72.7%) |
| gold@10 | 8/11 (72.7%) |
| MRR | 0.636 |
| gold 文档平均片段数 | 3.00 |
| 空结果题数 | 0 |
| 去重 query 数 | 13 |
| 去重候选集合数 | 13 |
| 去重首候选数 | 11 |

## 与基线对比

| 指标 | 基线 | 本次 | 变化 |
| --- | ---: | ---: | ---: |
| gold@3 | 0.0% | 72.7% | +72.7pp |
| MRR | 0.000 | 0.636 | +63.6pp |

## 按领域

| 领域 | 可评估 | gold@3 | 命中率 | MRR |
| --- | ---: | ---: | ---: | ---: |
| dmv | 3 | 3 | 100.0% | 1.000 |
| github-cli-negative-control | 0 | 0 | 未测 | 未测 |
| ssa | 3 | 2 | 66.7% | 0.500 |
| studentaid | 2 | 2 | 100.0% | 0.750 |
| va | 3 | 1 | 33.3% | 0.333 |

## 逐题明细

| 题号 | 领域 | 候选数 | gold 片段 | 首个 gold 排名 | query 去重键 | 状态 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| qa-c133078c0b8c5805ef25afe | dmv | 3 | 3 | 1 | 172e10fa | RETRIEVED |
| qa-067a4198b35cc78ffa0ae0a | dmv | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-a5d917071665232156177cb | dmv | 3 | 6 | 1 | 00076606 | RETRIEVED |
| qa-b180df810bdee917ef43765 | dmv | 0 | 1 | 未执行 | 无 | 未执行 |
| qa-a508b35d83b70e7ddfa5d23 | dmv | 3 | 3 | 1 | 049e0bf7 | RETRIEVED |
| qa-cb9fe9549014af6ff319d5a | dmv | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-a9212f7fd13c01dd2792c74 | ssa | 3 | 4 | 1 | 9a81d3f0 | RETRIEVED |
| qa-5de9a253ebae7cda68b7c7a | ssa | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-80be4b895fd193b2e3867ef | ssa | 3 | 1 | 2 | afebb03d | RETRIEVED |
| qa-6d5cff9a1b76423262f0b4f | ssa | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-ee3183f59b6c07856fb19df | ssa | 3 | 1 | 未命中 | b737c084 | RETRIEVED |
| qa-e10f962a370d0a7169a7215 | ssa | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-6dc95d6948e2ade445cac0a | studentaid | 3 | 1 | 2 | 43ace850 | RETRIEVED |
| qa-4dd1dc4547298b8efc730bb | studentaid | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-b769077abab7db9a00bf39d | studentaid | 3 | 8 | 1 | 036c3a7c | RETRIEVED |
| qa-0f9db9fb71ab8ffa38faf6c | studentaid | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-ab054785181de6bcbb7dd36 | studentaid | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-f521296dc8cf7b95aa840da | va | 3 | 2 | 未命中 | 7a674e5f | RETRIEVED |
| qa-907d9c979feae54cacbf82b | va | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-9a1702284047fab39b63adf | va | 3 | 2 | 未命中 | 4d0ee6d5 | RETRIEVED |
| qa-f72ccc9b3097e53bd51bf58 | va | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-28b3c8e7d96670a365f5f41 | va | 3 | 2 | 1 | ecf1197b | RETRIEVED |
| qa-3e710d117294fae7681d5a6 | va | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-gh-695 | github-cli-negative-control | 3 | 无标注 | 无标注 | 9c431dba | RETRIEVED |
| qa-gh-1466 | github-cli-negative-control | 3 | 无标注 | 无标注 | 17e231db | RETRIEVED |
| qa-gh-110 | github-cli-negative-control | 0 | 无标注 | 未执行 | 无 | 未执行 |

## 口径与限制

- gold@k 只表示发布者标注文档的片段出现在前 k 个候选中，不表示片段包含答案、也不表示模型正确使用了它。
- 同一 gold 文档可能被切成多个片段，命中任一片段即算命中；`gold 文档平均片段数` 表示难度参考。
- 无 gold 标注的题目（公开 issue 摘录）不计入召回指标，但仍报告候选数。
- 评估集中 `included: false` 的题目按冻结协议排除，不参与统计。
- 本工具不调用模型，因此不产生费用，也不能替代真人回答审核。
