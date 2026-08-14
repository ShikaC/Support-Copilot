# 优化 42：增加跨服务分析流程检查

## 业务问题

单独验证 Python、Java 和 React 健康状态，不能证明客服点击分析后结果真的穿过了 React 代理、Java 业务服务和 Python AI 服务，也不能证明 Python 不可用时 Java 会保留业务连续性。

## 关键数据流

成功场景：

```text
React Vite /api 代理
  -> Java POST /api/tickets/{id}/analyze
  -> Python POST /analyze
  -> Java 保存 AnalysisRun
  -> React/代理收到 SUCCEEDED + mode=mock + 证据和引用
```

失败场景：

```text
停止 Python
  -> React 仍请求 Java
  -> Java 捕获 AI 外部调用失败
  -> 保存并返回 FALLBACK
  -> 响应保留 traceId、人工复核警告和无引用降级语义
```

新增 `scripts/check-local-analysis-flow.sh`，通过真实 HTTP 请求检查响应和 Java `/analyses` 历史的最新记录。脚本不负责服务编排，故障注入由操作者明确执行。

## 验证结果

- 成功路径：`SUCCEEDED`、`mode=mock`、BILLING 分类、3 条证据、3 条引用、`traceId` 存在；Java 历史最新记录同步为 mock 成功。
- Python 停止后的 fallback 路径：`FALLBACK`、`mode=fallback`、`traceId` 存在、1 条人工复核警告；Java 历史最新记录同步为 fallback。
- 通过 React Vite `/api` 代理发起两条请求，确认不是只调用 Python 或 Java 内部测试替身。
- 三服务停止后未留下 8000、8080、5173 监听进程。

## 能力边界

这轮证明了本地 mock 模式的跨服务成功和 AI 服务不可用降级，不证明真实模型、Embedding 或浏览器组件渲染已经 live 验证。Java 当前使用 H2 内存数据库，重启后历史会重置；该脚本也不覆盖工单版本冲突和真实 UI 点击录制。
