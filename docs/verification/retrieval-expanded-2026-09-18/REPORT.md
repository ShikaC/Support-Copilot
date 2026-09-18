# 离线检索评测：扩展集 development 40 题（切片 2000/1600）

- 运行结果：`docs/verification/retrieval-expanded-2026-09-18/results.json`
- 评估集：`docs/verification/retrieval-cases-expanded-2026-09-18/cases.json` (sha256 245ece52663636f6…)
- 知识语料：`docs/verification/business-benchmark-2026-09-10/corpus.json` (sha256 e9c1795210db5a33…)
- 语料规模：1564 个片段 / 488 份文档

本报告由 `scripts/benchmark/retrieval-eval.mjs` 离线生成，不调用任何模型；它只判断候选片段是否属于发布者标注文档，不代表回答的事实正确率。

## 汇总

| 指标 | 值 |
| --- | --- |
| 计划题数 / 已执行 | 76 / 40 |
| 按协议排除的题数 | 0 |
| 可评估题数（有 gold 文档）| 40 |
| 无 gold 标注（不计入指标）| 0 |
| gold@1 | 20/40 (50.0%) |
| gold@3 | 32/40 (80.0%) |
| gold@10 | 32/40 (80.0%) |
| MRR | 0.625 |
| gold 文档平均片段数 | 3.25 |
| 空结果题数 | 0 |
| 去重 query 数 | 40 |
| 去重候选集合数 | 38 |
| 去重首候选数 | 31 |

## 按领域

| 领域 | 可评估 | gold@3 | 命中率 | MRR |
| --- | ---: | ---: | ---: | ---: |
| dmv | 10 | 9 | 90.0% | 0.850 |
| ssa | 10 | 6 | 60.0% | 0.433 |
| studentaid | 10 | 10 | 100.0% | 0.650 |
| va | 10 | 7 | 70.0% | 0.567 |

## 逐题明细

| 题号 | 领域 | 候选数 | gold 片段 | 首个 gold 排名 | query 去重键 | 状态 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| qa-d2c0327a9736dcb34a451fb | dmv | 3 | 3 | 1 | feedb8f9 | RETRIEVED |
| qa-e151c95a3a4ed3521298f6f | dmv | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-c3fb592c073ff2de66b5ed7 | dmv | 3 | 1 | 1 | 74e53c6b | RETRIEVED |
| qa-da721d167aa0ccf0f46ac86 | dmv | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-831e0030e98ffa5f4755d7b | dmv | 3 | 4 | 未命中 | 88f1a9db | RETRIEVED |
| qa-4a4aa99646ec063bb3b8def | dmv | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-be98bb760dd7ff224ec9d75 | dmv | 3 | 2 | 1 | ff554f74 | RETRIEVED |
| qa-ef2359d03c975196c5562cd | dmv | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-5d68fec39530256adc77c21 | dmv | 3 | 4 | 1 | 5d13f8fa | RETRIEVED |
| qa-aede8686db8cc652622178a | dmv | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-cac90c90583744d896f2567 | dmv | 3 | 2 | 2 | 3cbfdd3e | RETRIEVED |
| qa-53ae80a9aa64385a24037e8 | dmv | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-3637d14187420b78288c898 | dmv | 3 | 3 | 1 | 62cb5e56 | RETRIEVED |
| qa-a097a9f12a738bed82da721 | dmv | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-41680c19730b59b04eda716 | dmv | 3 | 4 | 1 | c20ee40f | RETRIEVED |
| qa-3cd0fb8c1ccf43fc7be1c0e | dmv | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-e6a8b47fb0ff5ed1a980a4b | dmv | 3 | 3 | 1 | 14a0ffa9 | RETRIEVED |
| qa-81bfd1b117b769896efef66 | dmv | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-e34b1b3160d3ce255b6248b | dmv | 3 | 7 | 1 | 0f5b3e1f | RETRIEVED |
| qa-4fee4f119f9cb6f417546b3 | ssa | 3 | 2 | 未命中 | a8c189ee | RETRIEVED |
| qa-992c03b23279092c1e8eea6 | ssa | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-00b3df8ed106bc3194bc305 | ssa | 3 | 2 | 1 | ee8e37c6 | RETRIEVED |
| qa-720f21c0e4259a87ce2ad78 | ssa | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-a496c8fcff7497a253ce2bb | ssa | 3 | 7 | 3 | ab0d3258 | RETRIEVED |
| qa-a344b757fc838b39c4ac66c | ssa | 0 | 1 | 未执行 | 无 | 未执行 |
| qa-53591aafbb7b1aa8c7d9899 | ssa | 3 | 1 | 2 | 2c4e62cb | RETRIEVED |
| qa-9f66bf41b437b2e227985c2 | ssa | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-82a54ead72e4d274bbe0daa | ssa | 3 | 7 | 未命中 | 4ad221fc | RETRIEVED |
| qa-436a4cba9d0853a925a6e2b | ssa | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-aeef4e8c55fd27e73a4e831 | ssa | 3 | 2 | 1 | b0b236c3 | RETRIEVED |
| qa-38b4aae9b2a7be94a8fe1d7 | ssa | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-016cf0849b0c801d2515d0d | ssa | 3 | 2 | 未命中 | 37b1d43d | RETRIEVED |
| qa-00bb98a2b4f6877ca228864 | ssa | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-829c4f406cc56578eb12198 | ssa | 3 | 4 | 1 | 848f1a80 | RETRIEVED |
| qa-1a42edfb51305e5d9fae24d | ssa | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-5a743ace2239552da73cd5f | ssa | 3 | 2 | 未命中 | 30dcab5d | RETRIEVED |
| qa-fd1e93460b85bb44b11f927 | ssa | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-8d5db793af142260b6531dc | ssa | 3 | 2 | 2 | df4363f3 | RETRIEVED |
| qa-edce5c4b0660321d1aeb8d8 | studentaid | 3 | 8 | 1 | 86a79d91 | RETRIEVED |
| qa-b5567fbacdae5ed24d30527 | studentaid | 0 | 8 | 未执行 | 无 | 未执行 |
| qa-368abe8171c4fa05484a46f | studentaid | 3 | 1 | 1 | 061b1900 | RETRIEVED |
| qa-2aea0dd7042c3b367702e0f | studentaid | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-aced8883d86eeba05d57c68 | studentaid | 3 | 2 | 2 | df1eb546 | RETRIEVED |
| qa-158251fa0162915345481c1 | studentaid | 0 | 9 | 未执行 | 无 | 未执行 |
| qa-011ed108ec1fde84e22a071 | studentaid | 3 | 1 | 2 | 379b1fd9 | RETRIEVED |
| qa-540a6a3be0724e310c1b916 | studentaid | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-5e91c548b9b9afdae84a9ea | studentaid | 3 | 7 | 1 | f9aaa1fb | RETRIEVED |
| qa-9cb41c5a51d97cca08ab3f8 | studentaid | 0 | 6 | 未执行 | 无 | 未执行 |
| qa-f8976f74f01d096e1682c86 | studentaid | 3 | 6 | 3 | 8efd8143 | RETRIEVED |
| qa-b4ded6b50ad2fbd716b20cf | studentaid | 0 | 1 | 未执行 | 无 | 未执行 |
| qa-0b2463a734bb5bf15e8bf52 | studentaid | 3 | 1 | 2 | 2d019b1b | RETRIEVED |
| qa-26e019e8e07b45430194245 | studentaid | 0 | 1 | 未执行 | 无 | 未执行 |
| qa-1280944e244ef83e9c34a76 | studentaid | 3 | 1 | 1 | 195ebee8 | RETRIEVED |
| qa-688d876e1d8b7890a7af1ec | studentaid | 0 | 8 | 未执行 | 无 | 未执行 |
| qa-660589fbfefaac122d89328 | studentaid | 3 | 1 | 3 | 15670aca | RETRIEVED |
| qa-93581640265a7f1c04887ba | studentaid | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-25b46c3bfdb8bed790af357 | studentaid | 3 | 3 | 3 | e6785fec | RETRIEVED |
| qa-6ac49004abfb04cc7c4f117 | va | 3 | 1 | 1 | f87ed7c5 | RETRIEVED |
| qa-c391621ab8602fffe50f624 | va | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-65f3b9dd47a6d34df2588ea | va | 3 | 3 | 1 | 30cb7406 | RETRIEVED |
| qa-47ee708713bb7166bb675a5 | va | 0 | 1 | 未执行 | 无 | 未执行 |
| qa-dcb97440f7eae9f40d215c5 | va | 3 | 5 | 未命中 | 2ef0bf53 | RETRIEVED |
| qa-6cc8637d3f86127df82922e | va | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-d9ae4758f904a702172438b | va | 3 | 2 | 1 | c8d2595a | RETRIEVED |
| qa-5de05450bb6cf2568c2d060 | va | 0 | 3 | 未执行 | 无 | 未执行 |
| qa-87a49a6d6ba97ce60abafa5 | va | 3 | 1 | 未命中 | 169836c9 | RETRIEVED |
| qa-522352fae1d674bb1014d52 | va | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-29db4545fe12bf4c311ed72 | va | 3 | 3 | 1 | 945c052d | RETRIEVED |
| qa-c2c7cc8ffe54846344975c1 | va | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-1c8f9736dd6de7e223e9921 | va | 3 | 6 | 未命中 | ee171112 | RETRIEVED |
| qa-860db6445eec2633d4a5a09 | va | 0 | 2 | 未执行 | 无 | 未执行 |
| qa-847c7e0f6fb8b78f6d44b5b | va | 3 | 2 | 3 | 696f1b15 | RETRIEVED |
| qa-97b5ac191ca1d25e9275ac5 | va | 0 | 4 | 未执行 | 无 | 未执行 |
| qa-28592664d078fb22d6d8e1e | va | 3 | 9 | 1 | f87bd1d6 | RETRIEVED |
| qa-1c17378544d0adfe586625d | va | 0 | 5 | 未执行 | 无 | 未执行 |
| qa-a3e94e5eafaffb5fdce0951 | va | 3 | 3 | 3 | efa282ea | RETRIEVED |

## 口径与限制

- gold@k 只表示发布者标注文档的片段出现在前 k 个候选中，不表示片段包含答案、也不表示模型正确使用了它。
- 同一 gold 文档可能被切成多个片段，命中任一片段即算命中；`gold 文档平均片段数` 表示难度参考。
- 无 gold 标注的题目（公开 issue 摘录）不计入召回指标，但仍报告候选数。
- 评估集中 `included: false` 的题目按冻结协议排除，不参与统计。
- 本工具不调用模型，因此不产生费用，也不能替代真人回答审核。
