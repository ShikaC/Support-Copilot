# 优化 54：持久化回复建议的人工审核结果

## 业务问题

页面原来的“采纳回复”只显示成功提示，没有向 Java 发出命令，也没有保存审核内容。刷新页面后状态消失，却声称“已写入审计日志”，这会把纯前端交互伪装成真实业务证据。

## 改进方案

增加独立 `AnalysisReview` 实体和审核接口，让回复审核经过真实业务链路：

```text
客服采纳或编辑建议回复
  -> React POST 审核命令
  -> Java 校验工单、分析归属和最新版本
  -> 区分 APPROVED / EDITED
  -> 保存原始内容、审核后内容、版本、traceId 和演示身份
  -> 返回已保存记录
  -> React 才显示审核成功
  -> 刷新工单恢复 latestReview 和处理记录
```

Java 只允许审核当前工单的最新分析，并要求当前工单版本仍等于分析来源版本加一。审核事务会先锁定工单行，再校验版本并写入审核，避免业务修改插入检查与保存之间。分析完成后若负责人、状态等业务事实再次变化，接口返回结构化 `409 ANALYSIS_REVIEW_STALE`，避免把旧建议当成当前结论。同一分析、同一审核内容的顺序重试会返回原记录，不重复写入。

审核人固定记录为 `UNAUTHENTICATED_DEMO / 演示管理员`。这是对当前 `permitAll` 配置的诚实边界，不声称存在真实登录身份。

## 验证结果

- Java 服务测试覆盖原建议采纳、编辑后采纳、同内容顺序重试、审核后再修改工单的过期拒绝，以及并发更新持锁后的版本重检。
- Java API 测试覆盖成功响应与结构化 `409`。
- React API 测试覆盖请求路径、请求体、成功 Schema、过期错误和未知动作契约漂移。
- 三服务契约测试实际完成分析、提交审核并刷新工单，确认相同审核 ID 出现在 `latestReview`。
- 真实 HTTP 故障演练确认两次同内容提交只产生一条记录；工单版本变化后返回 `ANALYSIS_REVIEW_STALE`。
- 浏览器验证确认编辑后采纳只在服务端成功后显示，刷新仍保留审核内容；1440 x 900 与 390 x 844 均无横向溢出或控件重叠。

## 能力边界

当前只实现 `APPROVED` 和 `EDITED`，没有拒绝动作、修改原因、发送给客户或高风险业务执行。审核身份未经认证，H2 重启后数据会重置，不能视为生产级审计。

工单行锁保证业务修改与审核写入具有明确顺序，但两个相同审核请求之间仍可能并发竞争；当前也没有跨实例请求 ID 或数据库唯一约束。正式聊天模型和 Embedding API 的 live 成功记录仍未完成，真实 RAG 继续处于层级 2。

## 面试关键位置

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/review/AnalysisReviewService.java`：审核归属、最新分析、工单版本、动作判断和顺序幂等的业务规则。
- `apps/support-copilot-web/src/features/analysis/ReplyReview.tsx`：只有服务端成功后才展示已记录，并明确标识未认证演示身份。
- `apps/support-copilot-web/src/integration/liveApiContract.test.ts`：让真实三服务响应完成分析、审核和刷新后持久化可见性验证。
