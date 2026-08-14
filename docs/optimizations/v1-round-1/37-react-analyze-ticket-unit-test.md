# 优化 37：验证 React 发送正确的分析请求

## 原来的问题

第 36 轮 React CI 只执行 lint 和生产构建：

```text
lint 通过 + build 通过
          ↓
只能证明代码可以检查和编译
不能证明 analyzeTicket 使用了正确工单 ID 和 HTTP 方法
```

例如，把 `ticket-10042` 错误发送成 `ticket-10043` 仍可能通过类型检查，因为两个值都是字符串。

## 本次如何修改

增加 Vitest 测试运行器和单次测试命令：

```json
"test": "vitest run"
```

新增测试文件：

```text
apps/support-copilot-web/src/services/api.test.ts
```

测试覆盖的业务规则是：

```text
输入 ticket-10042
-> 调用 analyzeTicket
-> 请求地址必须为 /api/tickets/ticket-10042/analyze
-> HTTP 方法必须为 POST
```

## 为什么模拟 fetch

单元测试把浏览器的 `fetch` 临时替换为一个记录调用的模拟函数。这样可以直接检查 React 准备的 URL、HTTP 方法和请求头，不需要启动 Java，也不受网络状态影响。

每条测试结束后都会恢复全局 `fetch`，防止测试之间互相污染。

这个模拟边界的含义必须保持准确：

```text
能够证明 React 准备了正确请求
不能证明 Java 实际收到或正确处理了请求
```

后者仍需要跨服务集成测试或浏览器端到端测试。

## Given、When、Then

测试按照三个阶段组织：

```text
Given：准备模拟成功响应和 fetch 记录器
When：请求分析 ticket-10042
Then：检查请求路径、工单 ID 和 POST 方法
```

这让测试失败时可以直接看出是准备条件、执行动作还是结果检查出现问题。

## 接入 React CI

工作流现在执行：

```text
npm ci
-> npm run lint
-> npm run test
-> npm run build
```

测试失败会返回非零退出码，后续 build 不会继续，整个 `React Web CI` 任务失败。

## 相对 V1 的改进

优化前：

```text
前端没有测试运行器
CI 不执行任何 React 单元测试
错误工单 ID 只能依赖人工操作发现
```

优化后：

```text
Vitest 和依赖版本进入 package-lock.json
analyzeTicket 的工单 ID 和 POST 请求规则受到测试保护
每次 push 和 Pull Request 都会执行这条测试
```

## 自动化验证

本轮完成以下验证：

- Vitest：`4.1.10`，支持当前 Node.js 24 环境。
- 正确代码：1 个测试文件、1 条测试通过。
- 故障注入：临时把请求地址改成 `ticket-10043` 后，测试明确报告预期 `ticket-10042`、实际 `ticket-10043`，并返回退出码 1。
- 恢复正确代码后，在不包含旧 `node_modules` 和 `dist` 的临时目录执行 `npm ci`，安装 128 个包。
- `npm run lint`：通过。
- `npm run test`：1 条通过。
- `npm run build`：TypeScript 和 Vite 生产构建通过。
- `actionlint v1.7.12`：React 工作流检查通过。
- 新测试文件有效代码 22 行，职责仅为验证分析请求构造。
- `git diff --check`：通过。

构建仍有现存主 JavaScript 包超过 500 kB 的提示，本轮没有修改页面或打包结构。

## 涉及文件

- `.github/workflows/react-web-ci.yml`
- `apps/support-copilot-web/package.json`
- `apps/support-copilot-web/package-lock.json`
- `apps/support-copilot-web/src/services/api.test.ts`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/36-react-web-github-actions-ci.md`
- `docs/optimizations/v1-round-1/37-react-analyze-ticket-unit-test.md`

## 当前边界

- React API 边界已在后续第 38 轮增加结构化 `409` 错误测试，但其他错误类型、请求函数和页面组件仍未覆盖。
- 模拟 `fetch` 不会启动 Java，因此不能替代跨服务集成测试。
- 当前没有真实浏览器端到端测试，不能证明客服点击按钮后的完整页面流程。
- 新 CI 修改尚未推送，GitHub 托管环境还没有实际运行记录。
