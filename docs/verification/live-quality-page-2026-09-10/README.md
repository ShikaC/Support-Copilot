# 质量页真实报告接入与简历差距核查

2026-09-10，当前工作区配置已验证。工单 AI 服务为 live，质量页也已显示已有 final-2 真实评估报告。不是本轮新跑的数据集，也不是在线客服效果。

## 原因与修改层

用户发现质量页仍为 mock。`EvaluationReportReader.java:30` 与 `application.properties:22` 默认读取 mock-latest.json；`EvaluationReportReader.java:86` 已实现 live 报告解析；`QualityView.tsx:8` 根据报告 mode 展示。工单 AI_MODE 与质量页 EVALUATION_REPORT_PATH 是两个独立配置。

本轮仅通过已有 EVALUATION_REPORT_PATH 指向 `docs/verification/ai-quality-fixes-2026-09-10/final-2/live-latest.json`，停止本轮自有旧 launcher PID 11872 后重新启动三服务，保持 live 与原 H2。没有修改 Java、Python、React 代码或报告原文。根 README 已记录完整启动命令，docs/STATUS.md 更新当前事实。下次只传 AI_MODE=live 而不指定报告，质量页仍会使用默认 mock 报告。

## 验证证据

- 基础 HEAD：4df3bf44907c34318132496929bad4a3974ad88b；master；dirty（开始时 git status 共 171 项）。无本轮提交/推送/部署。历史测试数量不是本轮重新执行结果。
- AI 服务目录执行 `.venv/bin/python evaluation/verify_live_evaluation.py --report ../../docs/verification/ai-quality-fixes-2026-09-10/final-2/live-latest.json --dataset evaluation/data/live-quality-v2.json`，exit 0，`live-evaluation-valid=true`。该命令验证报告一致性，不代表机器或人工质量通过。
- 原报告 SHA-256：b87f84bd9e4606a4cc0221c809882850693ab3547f0ce28ce91d77ad71948218。报告 runtime hash 与当前 AI 实现相符；证据针对 dirty 工作区，不能视作干净 HEAD 验证。
- GET `http://127.0.0.1:18000/health`：up、live、liveReady=true。
- GET `http://127.0.0.1:18173/api/metrics`：exit 0，保存为同目录 metrics.json，evaluation.mode=live、totalCases=22、passed=false。
- CUA 浏览器刷新后点击质量评估：实际显示 Live · 固定数据集评估、support-copilot-live-quality@2.1.0、gpt-5.6-luna、22 例、p95 20170 ms、未通过 · 1 项。
- 失败展示路径：选用包含真实超时失败的报告，确认页面保留未通过；没有重跑来筛选成功，没有把 publishable=false 改为通过。缺失/损坏报告的 Optional.empty 路径只读代码确认，本轮未注入。

## 当前展示限制

Reader 把 live 的 retrieval_success_rate 映射到通用 hitRateAtK，把 citation_valid_rate 映射到 citationCoverage；页面沿用 Hit@K、引用覆盖率标签。该汇总不是原始向量检索正例 Recall@3，且不能当作回复事实正确率。页面目前也没有单独显示人工审核进度和具体失败案例。本轮完成真实报告配置，完整指标口径与失败明细展示仍待小切片完善。

## 简历判断

已具备个人 AI 应用项目素材：React/Java/Python 工单闭环、真实模型与向量检索、证据约束与人工审核、版本冲突保护、可追溯评估及故障记录。可以描述已实现的工程机制和限定范围的验证。

主打面试项目仍需要：作者能独立解释主链路与失败语义；固定一轮报告完成真实人工事实审核并处置超时；审核 dirty diff 后冻结可复现演示版本；整理短演示、架构图和与实际职责相符的简历条目。无需为写个人项目先堆入新基础设施。

不能描述为真实企业生产系统、已完成真人审核、零幻觉或生产准确率；不能将小合成集指标换算成效率提升或用户规模。真实企业 SSO、完整 Pilot 恢复/回滚、安全发布与容量仍属后续部署目标，见 docs/ROADMAP.md。
