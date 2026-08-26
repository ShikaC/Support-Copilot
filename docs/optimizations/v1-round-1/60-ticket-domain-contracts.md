# 优化 60：收紧工单值域、状态转换与版本写入

## 问题与风险

原 PATCH 接口接受任意状态、优先级和分类，也没有要求客户端提交读取时的工单版本。两个客服并发操作时，后提交者可能覆盖先提交者；非法人工状态或 AI 值也可能直接写入工单。

## 新契约

- PATCH 必须携带非空、非负 `expectedVersion`。匹配时保存并返回递增版本；过期版本和 JPA 乐观锁失败统一返回 `409 VERSION_CONFLICT`。
- 手工状态为 `NEW`、`READY_FOR_REVIEW`、`READY_FOR_MANUAL_REVIEW`、`NEEDS_ESCALATION`、`IN_PROGRESS`、`WAITING_CUSTOMER`、`RESOLVED`、`CLOSED`。`ANALYZING` 只属于 React 等待状态。
- 手工转换只允许：`NEW -> IN_PROGRESS`；三种待处理/升级状态 `-> IN_PROGRESS`；`IN_PROGRESS -> WAITING_CUSTOMER/RESOLVED`；`WAITING_CUSTOMER -> IN_PROGRESS`；`RESOLVED -> CLOSED`。同状态或不提交状态不算转换。
- priority 为 `LOW/MEDIUM/HIGH/URGENT`；channel 为 `EMAIL/CHAT/WEB_FORM/PHONE`；customer tier 为 `STANDARD/PREMIUM/ENTERPRISE`。
- category 为 `UNCLASSIFIED/GENERAL/BILLING/ACCOUNT_ACCESS/INVOICE/DATA_EXPORT/SUBSCRIPTION/PRIVACY/SECURITY/LEGAL/TECHNICAL/DATA_RECOVERY`。其中 `UNCLASSIFIED` 是创建初始化值，`GENERAL` 是分类 fallback，`INVOICE` 等业务分类由当前本地 AI 分类器、固定评估集或演示数据产生；`SECURITY/LEGAL` 由高风险策略消费并允许结构化 live 结果进入持久化边界。没有仓库生产者或消费者证据的任意分类不会作为兼容值保留。

分析写入不复用手工转换图。它通过同一类型化值域校验分类、优先级和分析状态，再按分析决策进入 `READY_FOR_REVIEW` 或 `NEEDS_ESCALATION`；非法 AI 值在创建分析历史或修改工单前被拒绝。

## 前端行为

真实后端工单的 PATCH 和取消负责人请求发送当前版本。收到 `VERSION_CONFLICT` 后，`ApiError` 保留 expected/current 详情，React 重新读取受影响工单并显示原有过期状态提示。没有 `version` 的 Demo 工单继续只在本地更新。

## 验证

```bash
cd services/support-copilot-api
./gradlew test --tests '*TicketUpdateContractTests'
./gradlew test

cd apps/support-copilot-web
npm test -- --run src/services/api.test.ts src/services/apiContract.test.ts src/App.staleUpdate.test.tsx
npm test -- --run
npm run lint
npm run build
```

这些测试覆盖当前版本成功与递增、过期和并发冲突无丢失更新、全部允许转换、代表性非法/终态转换、边界非法值、AI 非法值无数据库修改，以及 React 版本请求和冲突刷新。当前仍是单实例 H2 本地验证；可信身份、持久化审计和 MySQL 迁移属于后续任务。
