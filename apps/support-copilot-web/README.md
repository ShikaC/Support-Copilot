# Support Copilot Web

React + TypeScript 工单工作台。页面通过 typed API client 和 Zod 校验读取 Java API，支持
明确区分的 `demo` 与 `secured` auth mode；它不包含真实 OIDC 登录或 token refresh。

```bash
npm ci
npm run dev
```

常用验证：

```bash
npm run lint
npm test -- --run
npm run build:budget
npm run test:e2e
```

完整环境、三服务启动、演示和能力边界见仓库根目录的
[README](../../README.md)、[面试演示](../../docs/DEMO.md) 和
[Pilot 运行手册](../../docs/PILOT_OPERATIONS.md)。
