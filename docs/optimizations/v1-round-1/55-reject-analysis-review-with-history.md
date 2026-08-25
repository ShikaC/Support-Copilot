# 优化 55：补齐回复建议拒绝与审核历史

## 业务问题

上一轮只能采纳原建议或编辑后采纳。客服发现建议证据不足、风险判断不完整或不适合发送时，没有明确的拒绝动作，也无法留下原因；页面也只显示最新状态，不能查看同一分析经历过的审核决策。

## 改进方案

在现有 `AnalysisReview` 历史中增加拒绝语义，不创建第二套审计模型：

```text
客服点击拒绝建议
  -> React 要求填写拒绝原因
  -> POST /reviews/reject
  -> Java 锁定工单并校验最新分析与工单版本
  -> 保存 REJECTED、原始建议、拒绝原因、版本和 traceId
  -> reviewedReplyContent 明确保存为 null
  -> React 同步最新审核和处理记录
  -> GET /reviews 按需加载完整审核历史
```

`APPROVED` 和 `EDITED` 必须包含审核后回复且 `reason=null`；`REJECTED` 必须包含非空原因且 `reviewedReplyContent=null`。React 使用可辨识联合 Zod Schema 在运行时执行这组约束，避免把拒绝的原始建议误当成已经审核通过的回复。

采纳与拒绝共用同一个版本保护入口。接口先锁定工单行，再确认目标分析仍是最新分析、工单版本仍等于分析完成后的预期版本；工单变化后拒绝请求返回结构化 `409 ANALYSIS_REVIEW_STALE`。同一分析、同一拒绝原因的顺序重试返回已有记录。

## 验证结果

- Java 41 条测试通过；新增覆盖拒绝持久化、审核后回复为空、原因保存、同原因顺序重试、过期拒绝、空原因 400 和刷新后事件原因一致。
- React 24 条测试通过，另有 3 条仅在显式真实契约模式运行的测试被默认跳过；新增覆盖拒绝命令、历史查询、运行时 Schema 和父工单状态。
- 真实跨服务契约 3 条通过；TypeScript、oxlint、生产构建和严格 no-excuse 审计通过。
- Python 80 条测试通过，固定 mock 评估 18/18；本批次没有改变分类、检索或生成逻辑。
- 真实 HTTP 流程验证 `分析 -> 拒绝 -> 历史查询 -> 刷新工单`，拒绝记录保留相同 `traceId`；修改工单后重试拒绝返回 `409 ANALYSIS_REVIEW_STALE`。
- 浏览器实际操作验证原因必填、拒绝成功、刷新后的处理记录和按需审核历史；桌面 1440 x 900 与移动 390 x 844 均无横向溢出、文字截断或控件重叠。

## 能力边界

当前 `APPROVED`、`EDITED`、`REJECTED` 三种人工决策已经形成可演示的本地闭环，但审核人仍是 `UNAUTHENTICATED_DEMO / 演示管理员`，没有登录、RBAC 或可信生产身份。当前也没有通用审计日志、审核请求并发唯一约束、生产数据库或跨实例幂等；H2 重启后记录会重置。

拒绝只记录人工决策，不会自动发送回复、退款、封号或修改客户数据。正式聊天模型和 Embedding API 的真实 live 成功记录仍未完成，真实 RAG 继续处于完成标准层级 2。

## 面试关键位置

- `services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/analysis/review/AnalysisReviewService.java`：采纳与拒绝共用的行锁、最新分析、版本检查和顺序重试规则。
- `apps/support-copilot-web/src/services/analysisReviewSchema.ts`：用可辨识联合表达采纳与拒绝互斥的数据不变量。
- `apps/support-copilot-web/src/features/analysis/ReplyReview.tsx`：拒绝命令、旧异步响应保护和审核历史按需加载。
