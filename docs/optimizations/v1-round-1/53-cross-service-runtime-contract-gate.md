# 优化 53：用真实跨服务响应验证前端契约

## 业务问题

第 52 轮已经让 React 用 Zod 解析网络响应，但自动化测试输入仍是固定 fixture。现有跨服务脚本会验证模式、状态、追踪号、证据和持久化，却不会执行页面实际使用的完整 Schema。因此，Java 的真实 JSON 与前端 fixture 可能同时发生不同方向的变化，而两套检查仍各自通过。

## 改进方案

新增显式 `--contract` 门禁。它在三服务已经启动时，通过 React 代理调用真实工单、指标和分析接口，并复用前端生产 API 客户端：

```text
真实 Java JSON
  -> React 代理
  -> api.ts
  -> apiSchemas.ts
  -> 测试断言业务结果
  -> 刷新工单确认 latestAnalysis
  -> 查询 Java 分析历史
```

集成测试默认跳过，避免普通单测和 CI 隐式依赖本地端口；只有执行 `./scripts/check-local-analysis-flow.sh --contract` 时才启用。测试工单继续使用脚本原有的 `SUPPORT_COPILOT_TICKET_ID` 配置。

## 验证结果

- 红灯：修改前执行 `--contract` 返回退出码 2，脚本不支持该验收模式。
- 离线前端：15 条测试通过，3 条真实服务契约测试明确跳过；lint 通过。
- 真实三服务：3 条契约测试通过，真实工单、指标和 mock 分析均通过前端运行时 Schema；刷新工单可以看到同一个分析 ID，Java 历史最新记录为 `mock / SUCCEEDED / fallbackReason=null`。
- 故障注入：本地 HTTP 服务对三个接口统一返回 `{}`，3 条契约测试全部抛出 `ApiContractError`，命令返回退出码 1。
- Shell：`bash -n scripts/check-local-analysis-flow.sh` 通过。
- 全仓回归：React lint、15 条离线测试和生产构建通过；Java 26 条、Python 80 条测试通过；固定 mock 评估 18/18 通过。生产构建仍有现存的 1.899 MB bundle 体积提示。

## 能力边界

这条门禁验证当前三服务在本地 mock 模式下的响应兼容性，不是自动生成的单一契约源，也不替代正式 API live 验收。它按需运行，GitHub CI 当前不会启动三服务执行该检查。

本轮没有正式聊天模型或 Embedding API 凭据，也没有发起付费调用。真实 RAG 仍处于层级 2，正式 `mode=live` 成功记录仍未完成。

## 面试关键位置

- `apps/support-copilot-web/src/integration/liveApiContract.test.ts`：让真实跨服务响应经过页面使用的生产 API 客户端和 Zod Schema。
- `scripts/check-local-analysis-flow.sh`：提供显式 `--contract` 门禁，并在前端契约通过后检查 Java 持久化历史。
- `apps/support-copilot-web/src/services/apiSchemas.ts`：唯一复用的前端运行时响应规则，门禁没有复制完整字段清单。
