# 优化 57：增加隔离端口的本地 mock smoke 验收

## 业务问题

此前的本地启动检查只验证依赖和健康端点，跨服务分析检查还要求操作者预先启动三个服务。面试演示或新环境复现时，容易出现端口冲突、忘记启动服务或验证完成后遗留进程的问题。

## 改进内容

新增 `scripts/run-local-smoke.sh`，只在隔离端口启动 mock 模式的 Python、Java 和 React：

```text
启动 Python mock、Java H2、React Vite
    -> 等待三个健康端点
    -> check-local-startup.sh --all
    -> check-local-analysis-flow.sh --success
    -> check-local-analysis-flow.sh --contract
    -> 只清理本脚本启动的进程
```

默认端口是 `18000`、`18080` 和 `15173`。脚本会先检查端口是否已经被占用；发现冲突时直接失败，不会停止已有服务。进程日志只写入临时目录，成功后删除，失败时输出最近日志帮助定位。

## 验证结果

执行：

```bash
bash -n scripts/run-local-smoke.sh
./scripts/run-local-smoke.sh --help
./scripts/run-local-smoke.sh
```

结果：

- Python、Java、React 均在隔离端口 ready。
- `check-local-startup.sh --all` 通过。
- mock 分析为 `SUCCEEDED / mock`，返回 3 条证据和 3 条引用。
- Java 分析历史最新记录为 `mock / SUCCEEDED`。
- 前端真实运行时契约测试为 3 passed。
- smoke 结束后 `18000`、`18080`、`15173` 均已释放。

## 能力边界

该脚本只验证本地 mock 链路，不调用正式模型或 Embedding API，也不自动执行停止 Python 的 fallback 故障注入。真实 live 仍需使用 `scripts/check-live-rag.sh`，并满足正式凭据、知识来源和干净提交条件。
