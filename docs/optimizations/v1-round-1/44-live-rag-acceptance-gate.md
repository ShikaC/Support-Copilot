# 优化 44：增加真实 RAG 验收与脱敏证据门禁

## 业务问题

项目已经具备 OpenAI 聊天模型和 Embedding 的 live 代码骨架，但只有启动命令，没有一条能够防止误报的验收命令。人工只看到 HTTP 200 时，可能把 mock、fallback、没有向量证据或没有持久化的结果误写成“真实 RAG 已完成”。

## 改进方案

新增 `scripts/check-live-rag.sh`，提供两个明确入口：

```text
--preflight
  -> 从 Python Settings 读取配置状态，不输出 API Key
  -> 要求 AI_MODE=live、API Key、聊天模型和 Embedding 模型齐全
  -> 校验配置的知识文件，并计算不含正文的来源类型、片段数和 SHA-256
  -> 要求 Git 工作区干净，使证据绑定到准确提交
  -> 不调用任何外部 API

--success
  -> 先执行 preflight
  -> 要求 Python /health 返回 mode=live、liveReady=true
  -> 经 React 代理调用 Java 的 SSO 模拟工单分析
  -> 要求响应为 live/SUCCEEDED，保留指定 traceId
  -> 要求全部检索证据使用 VECTOR，且至少有一条引用
  -> 要求聊天模型报告正数 input/output token
  -> 要求 Java 分析历史的最新记录与响应一致
  -> 生成不含密钥、授权头和工单正文的 Markdown 证据
```

默认使用仓库内的虚构 SSO 工单 `ticket-10041`。证据只记录日期、提交 SHA、官方或兼容端点类型、模型名、知识来源类型/片段数/SHA-256、工单编号、`traceId`、证据片段 ID/来源/排名、引用、耗时和 token。报告不记录本地知识路径或知识正文；报告目录默认被 Git 忽略，真实成功后需要人工检查再选择性加入版本控制。

## 当前验证

- `bash -n scripts/check-live-rag.sh`：通过。
- `./scripts/check-live-rag.sh --help`：通过。
- 当前没有 OpenAI 环境变量时执行 `--preflight`：明确返回退出码 `1`，且不调用 API。
- 使用占位模型和占位 Key、但保持 `AI_MODE=mock` 时执行 `--preflight`：明确返回退出码 `1`，不能把配置存在误判为 live。
- 使用占位 live 配置但工作区未提交时执行 `--preflight`：明确返回退出码 `1`，避免生成无法绑定代码版本的证据。
- 合成的 `live/SUCCEEDED`、VECTOR 证据、引用和正数 token 响应通过结构验收，并能生成不含敏感输入的 Markdown 记录。
- 把同一合成响应改为 `mode=mock` 后，结构验收返回退出码 `1`，证明不会把 mock 记录为 live 成功。

## 能力边界

当前机器没有设置 `OPENAI_API_KEY`、`OPENAI_CHAT_MODEL` 和 `OPENAI_EMBEDDING_MODEL`，因此本轮没有执行 `--success`，没有产生正式 API 费用，也没有生成 live 成功记录。该脚本只是严格验收器，不是完成证据本身；只有未来真实运行成功并人工检查脱敏记录后，项目才达到真实 RAG 层级 3。
