# Mock 评估基线：2026-08-24

## 验证对象

- Git commit：`d0989834bab0d76b3966e5288e0e75d7d37f2815`
- 工作区状态：干净
- 运行时间：`2026-08-24T06:45:32.544968+00:00`
- 模式：`mock`
- 模型标识：`deterministic-demo`
- 提示词版本：`ticket-analysis-v1`
- Top N / Top K：`10 / 3`
- 固定案例数：18

## 可重复输入

- 数据集：`services/support-copilot-ai/evaluation/data/tickets.jsonl`
- 数据集 SHA-256：`0f820696cd08a69ca7b2875353b3127e7e05497739078e3e8ab793d2666d1bd4`
- 知识库：`services/support-copilot-ai/app/data/knowledge.json`
- 知识库 SHA-256：`619a7169605128bf642065a909f186c7d1bbe144ecee0da001d2db1b382f1e5d`

## 运行环境

- Python：`3.11.15`
- Java：`21.0.2`
- Node.js：`24.18.0`

## 执行命令

```bash
cd services/support-copilot-ai
.venv/bin/pytest -q
.venv/bin/python -m evaluation.run_mock_evaluation
```

执行结果：Python `53 passed`；评估命令退出码为 `0`，18 条案例全部通过，失败案例为 0。

## 指标与门槛

| 指标 | 本次结果 | 通过门槛 |
| --- | ---: | ---: |
| 分类准确率 | 1.000 | >= 0.900 |
| 优先级准确率 | 1.000 | >= 0.900 |
| 高风险优先级降级数量 | 0 | = 0 |
| 升级召回率 | 1.000 | >= 1.000 |
| 升级准确率 | 1.000 | >= 0.900 |
| Hit@3 | 1.000 | >= 0.900 |
| MRR | 1.000 | >= 0.800 |
| 引用覆盖率 | 1.000 | >= 0.900 |
| 无证据安全率 | 1.000 | >= 1.000 |
| 回复约束通过率 | 1.000 | >= 1.000 |

本次平均耗时为 0.1 毫秒，P95 为 0 毫秒，最大值为 1 毫秒。该耗时只用于本地确定性回归，不代表 live 模型延迟或生产性能。

## 结论与边界

这份记录证明当前提交上的本地确定性 mock 工作流满足固定评估集门槛，并且失败门槛会影响命令退出码。指标只能解释这 18 条人工维护的模拟案例，不能外推为通用模型准确率、真实 Embedding 检索质量或生产 RAG 效果。

当前机器仍未配置正式聊天模型和 Embedding API 凭据，因此真实 live RAG 成功记录依然缺失。mock 基线不能替代 `scripts/check-live-rag.sh --success` 的层级 3 验收。
