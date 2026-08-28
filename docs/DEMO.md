# Support Copilot 面试演示

这份脚本用于 5 至 8 分钟的本地面试演示。主路径固定使用 `demo` + `mock`：不需要
API Key，不调用外部模型，也不会把模拟结果描述成真实客服效果。系统能力和运行边界见
[Pilot 运行与证据边界](PILOT_OPERATIONS.md)。

## 1. 演示前验收

环境需要 Node.js 24、Java 21、Python 3.11、npm、Git 和 curl。首次安装依赖后，在仓库
根目录运行：

```bash
./scripts/check-local-startup.sh --preflight
```

正式演示前执行一键 smoke：

```bash
./scripts/run-local-smoke.sh
```

通过标准是最后输出 `Local mock smoke passed.`。脚本使用隔离端口启动 Python、Java 和
React，验证健康状态、成功分析、React 运行时 Schema 和 Java 分析历史，然后只清理自己
启动的进程。它不执行 live API、Docker 或 MySQL。

从 tracked-only 临时副本复验文档、测试、构建和同一 smoke，可运行：

```bash
./scripts/verify-docs.sh
```

## 2. 启动演示环境

按 [README 快速启动](../README.md#快速启动) 在三个终端依次启动 FastAPI mock、Spring
Boot `demo` profile 和 React。三个服务就绪后运行：

```bash
./scripts/check-local-startup.sh --health
```

浏览器打开 `http://localhost:5173`。侧栏应显示业务 API 已连接；若显示“演示数据模式”，
说明页面没有连上 Java，不能把后续操作当成跨服务演示。

## 3. 讲解路径

### 0:00-1:00 问题与边界

打开工单工作台，说明系统不是自动客服：AI 负责分类、检索、证据约束建议和升级提示，
最终回复仍由客服审核。指出页面和分析响应会显示 `mock`、`live` 或 `fallback`，避免来源
混淆。

可验证证据：页面服务状态、分析模式标签和人工审核控件。

### 1:00-3:00 有证据的分析

选择“本月套餐出现重复扣款”，触发分析，然后依次查看：

1. 分类、优先级、情绪、置信度和升级判断。
2. 检索查询、Top K 知识片段、来源、分数和引用。
3. 建议回复中的引用编号与知识片段对应关系。
4. `traceId`、模型/规则来源和耗时字段。

可验证证据：至少一个检索命中、至少一个引用，最新分析出现在 Java 保存的分析历史中。
命令行可以补充执行：

```bash
SUPPORT_COPILOT_TRACE_ID=interview-flow-01 \
  ./scripts/check-local-analysis-flow.sh --success
```

### 3:00-4:30 人工审核与审计

编辑建议回复后采纳，或者拒绝建议并填写原因，再展开审核历史。说明分析、审核和工单实际
变更使用版本校验与幂等键；审核 actor 在 `demo` 中明确为演示身份，在安全 profile 中来自
JWT，而不是浏览器自报字段。

可验证证据：成功提示、刷新后仍存在的审核记录，以及审计页中的受控动作、目标、版本和
`traceId`。审计不保存工单正文、回复正文、拒绝原因、证据或 provider payload。

### 4:30-5:30 无证据安全路径

选择“能否恢复三个月前删除的项目”并分析。预期结果不应编造恢复承诺，而应进入证据不足
的 `fallback`，不给出伪引用，并提示人工处理。

可验证证据：`mode=fallback`、稳定 `fallbackReason`、零证据/零引用和人工复核 warning。

### 5:30-6:30 评估与能力边界

切换质量评估页，说明数字来自版本化 mock 报告，不是静态仪表盘数据。报告缺失或损坏时
页面返回“暂无评估报告”，不会保留旧数字。

说明仓库曾完成一次脱敏合成工单的真实 live 成功链路；后续 4-case live 评估因同一
structured-output provider 错误第二次出现而停止，且人工标签为 0/4，所以不能声称已有
可发布的 live 质量结论。

### 6:30-8:00 故障与下一步

说明 Python 不可用时 Java 会返回明确的人工 fallback，而未知程序错误不会被伪装成 AI
降级。需要现场演练时，手工启动三服务、停止 Python 后执行：

```bash
./scripts/check-local-analysis-flow.sh --fallback
```

演练后重新启动 Python。最后指出真实 MySQL、OIDC 组合、容器、备份恢复和部署回滚仍是
Task 15，当前演示只证明本地单租户 pilot 的工程契约。

## 4. 面试复述模板

每条主路径按以下六项回答：

1. 问题：业务失败会造成什么后果。
2. 风险：模型、检索、并发或权限哪里可能出错。
3. 修改层：React、Java、Python 或数据层各自承担什么。
4. 流程：请求和状态如何跨层流动。
5. 证据：哪个命令、测试、报告或页面状态能复现。
6. 限制：当前结果不能证明什么。

## 5. 禁止表述

- 不把 mock 分类率、延迟或检索指标称为生产准确率、SLO 或真实用户效果。
- 不把一次 live 成功称为模型稳定性或质量基准。
- 不把 H2、合成 JWT 或本地文件 artifact 称为真实 MySQL、OIDC 或多实例部署证据。
- 不声称系统已经自动发送客服回复；当前必须 human approval。
