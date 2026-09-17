# 本地工作台切换真实模型：2026-09-10

已实现、已验证：用户明确要求工作台使用真实模型后，本地三服务工作区已由 mock 切换为 live。通过浏览器新建合成工单、点击开始分析、观察 LIVE 与模型名，再经 Java GET 读取持久化结果，首次请求成功。原持久化 H2 继续使用，历史工单仍可读取。

## 修改与原因

- `scripts/dev-workspace.sh:7`：接受并提前校验显式 AI_MODE=mock|live，未指定时仍为 mock。此前脚本硬编码 mock，覆盖外部模式选择；改变启动层即可接通已有真实模型配置，无需修改 AI 工作流。
- 启动器导出所选 AI_MODE，并在就绪日志显示实际选择。
- 根 README 增加 live 启动命令；docs/STATUS.md 更新当前运行事实。
- 风险：live 会调用外部模型和 Embedding API；使用合成输入，不修改凭据、索引、模型、超时或重试策略。

## 当前工作树与证据

- HEAD：`4df3bf44907c34318132496929bad4a3974ad88b`；分支 master；dirty，保留已有未提交改动，本轮无提交/推送/部署。
- 证据针对该 HEAD 上的未提交工作区，不能当作干净 HEAD 的验证。
- 启动器 SHA-256：`93c901c7585ee6d3b7bda4c38799ad80316a5b1b42ab0a558e23131cc76d8d19`；同目录保留 `dev-workspace.sh.snapshot`。
- AI 代码沿用 [AI 质量修复证据](../ai-quality-fixes-2026-09-10/README.md)，本轮只改启动器与文档，没有重跑固定质量数据集。

## 验证命令与结果

1. `bash -n scripts/dev-workspace.sh`：exit 0。
2. `AI_MODE=invalid ./scripts/dev-workspace.sh`：exit 1，提示只接受 mock/live；在端口、锁、构建、服务启动之前拒绝错误配置。输出见 `invalid-mode.log`。没有为此注入模型故障或切断运行服务。
3. 对本轮原 launcher PID 9061 发送 SIGTERM，等待其退出清理后执行 `AI_MODE=live ./scripts/dev-workspace.sh`：三服务就绪，日志显示 AI mode: live，仍使用原文件 H2。
4. `curl -fsS http://127.0.0.1:18000/health`：mode=live、liveReady=true，见 `health.json`；Java health=UP，见 `api-health.json`。
5. 在浏览器 http://127.0.0.1:18173/ 创建“真实模型验收 2026-09-10 · SYNC-2047 同步失败”，联系人与企业均明确为合成测试身份，然后点击开始分析。
6. 页面实际显示 LIVE、gpt-5.6-luna、技术问题、待审核和“完成模型分析”审计事件；没有采纳回复或发送客户。
7. `curl -fsS http://127.0.0.1:18173/api/tickets/ticket-9226c9d9-d8ea-4801-908a-468729d1409c/analyses`：读取保存后的分析历史，原始响应见 `analyses.json`；对应工单 GET 见 `ticket.json`。

## 单次真实结果

| 字段 | 结果 |
| --- | --- |
| status / mode | SUCCEEDED / live |
| modelName | gpt-5.6-luna（配置及返回记录中的名称，不独立证明供应商内部路由） |
| traceId | trace_b30566ab86dc |
| 分析 ID | run_AF7391A47968 |
| 生成时间 UTC | 2026-09-10T05:41:17.190717Z |
| 检索 | VECTOR，3 条传入证据；回复引用其中的 chunk-sync-2047 |
| token 用量 | inputTokens=1090，outputTokens=349 |
| usage.durationMs | 8976；这是返回的 usage 耗时，不等同浏览器端到端延迟 |
| 建议回复 | 收集客户端版本、系统版本、代理配置，供支持人员继续排查；不承诺修复时限 |

## 边界与后续使用

当前运行保持 live。以后停止再启动，请使用根 README 的显式 live 命令。旧 mock 分析仍显示其历史标记，需要点击重新分析才能获得新的真实调用结果。

本次首次调用成功，无运行时 fallback；失败路径只验证错误启动模式拒绝。此前真实评估中的连接/读取超时、人审未完成和 publishable=false 仍成立。三条检索结果中只有同步错误码片段被回复引用，其他两条相关性较低；不能把召回条数当作三条均支持答案，也不能用本次成功宣称整体 RAG 质量通过。

可用于项目经历的事实：本地 React→Java→Python→真实模型/向量检索→分析持久化→人工审核入口的单工单链路已验证。尚不能写成真实企业上线、生产稳定性、全部语义正确、人工审核完成或真实客服效果。
