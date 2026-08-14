# 优化 41：增加可复现本地启动检查

## 业务问题

V1 原来提供了三个分散的启动命令，但新环境缺少 Python 虚拟环境、前端依赖或错误端口时，使用者只能逐个尝试启动，无法快速区分“环境未准备好”和“服务已经启动但健康检查失败”。这会降低演示复现性，也容易把前端演示数据误认为完整系统已经可用。

## 修改层和数据流

新增仓库根目录脚本 `scripts/check-local-startup.sh`，不进入 Java、Python 或 React 业务逻辑：

```text
--preflight
  -> 检查 Node.js、Java、Python、npm、curl
  -> 检查 Python 虚拟环境、uvicorn、Gradle Wrapper 和 Vite

--health
  -> GET Python /health
  -> GET Java /actuator/health
  -> GET React /
  -> 检查 HTTP 成功状态和 Python/Java 预期健康字段
```

端口默认与当前配置一致：Python `8000`、Java `8080`、React `5173`。如本地端口被占用，可以通过 `SUPPORT_COPILOT_AI_PORT`、`SUPPORT_COPILOT_JAVA_PORT` 和 `SUPPORT_COPILOT_WEB_PORT` 指定检查地址；这些变量必须与实际启动参数同步。

## 验证方式

- `bash -n scripts/check-local-startup.sh`：检查 shell 语法。
- `./scripts/check-local-startup.sh --preflight`：验证新环境的本地依赖前提。
- 三服务实际启动后执行 `./scripts/check-local-startup.sh --health`：验证真实 HTTP 健康面。
- 停止任一服务后再次执行 `--health`：确认脚本返回非零并指出失败服务。
- `git diff --check`：检查文档和脚本格式。

## 能力边界

脚本只做检查，不负责启动、停止、重试或编排服务；它也不检查业务分析是否成功。Java 使用 H2 内存数据库，Python 默认仍为 mock 模式，React 在 Java 不可用时仍可能进入明确标识的演示数据模式。完整跨服务分析和 live RAG 仍需单独验证。
