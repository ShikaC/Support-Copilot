# 优化 59：将 mock 评估报告接入质量页面

## 业务问题

Python 已经可以生成包含指标、评估配置和失败门槛的 `mock-latest.json`，但 Java `/api/metrics` 一直返回 `evaluation=null`，React 质量页只能显示占位信息。与此同时，页面使用的 `groundedness` 和 `citationAccuracy` 并不是当前评估报告的字段，容易让展示名和真实计算过程脱节。

## 改进内容

- 增加可配置的 `EVALUATION_REPORT_PATH`，默认指向 Java 服务工作目录下的 `../support-copilot-ai/evaluation/reports/mock-latest.json`。
- Java 读取报告中的数据集、模式、模型、Prompt 版本、样本数、Top N/K、Hit@K、MRR、引用覆盖率、无证据安全率、平均耗时、P95、门禁失败数量和生成时间。
- 报告缺失、JSON 损坏、必需字段类型不匹配、比例超出 0 到 1、计数或耗时为负、Top K 大于 Top N 时，只记录不含报告正文的告警并返回 `evaluation=null`，不影响其他工单指标。
- React Schema 和质量页改用报告实际字段，展示报告来源和门禁状态。

## 验证结果

```bash
cd services/support-copilot-api
./gradlew test --no-daemon --tests 'com.cyagent.supportcopilot.metrics.*'

cd ../../apps/support-copilot-web
npm test -- --run
```

Java 指标相关测试和 React API 契约测试通过。完整三服务 smoke 还需在本轮最后执行。

## 能力边界

评估报告当前由文件提供，不是 Java 数据库中的评估运行实体；删除或替换文件后需要重新加载页面。报告只描述固定 mock 评估集，不代表 live 模型质量、生产延迟或真实客服效果。正式 live RAG 仍受 Embedding 服务能力限制。
