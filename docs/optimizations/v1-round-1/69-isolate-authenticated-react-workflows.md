# 第 69 轮：隔离认证前端工作流与严格 API 边界

## 问题与风险

原 React `App.tsx` 同时负责工单、分析、知识、质量和布局，安全模式也没有统一的访问令牌注入边界。继续扩展会让并发分析、401/403、409 刷新和契约漂移互相污染；在无令牌时隐式显示演示身份还会制造错误的权限事实。

## 修改层与流程

本轮增加 session/memory 范围的 typed auth adapter。`demo` 与 `secured` 是显式状态；secured 请求只在会话存在 token 时注入 Bearer，缺失 token 时省略 Authorization 并保留后端 401。请求通过 `AbortSignal.timeout/any` 限制超时与取消，错误只保留稳定 code、traceId 和安全 message。

HTTP client 在信任边界用 Zod 严格解析工单、指标、分析/审核、知识检索/发布和审计分页。写命令携带后端实际要求的 `expectedVersion`；分析和审核幂等键按用户命令指纹保留到一次确定成功，失败后的重试不会意外换键。

`App.tsx` 变为组合壳，工单队列/详情/更新、分析、知识、审计、质量分别进入 feature 组件与 hook。分析状态按 ticket id 隔离，切换工单或重试时旧成功结果不会残留或覆盖当前视图。已有视觉结构、色彩和组件 anatomy 保持不变，只修复了 768 px 知识发布行的真实横向溢出。

## 验证与边界

```bash
cd apps/support-copilot-web
npm test -- --run
npm run lint
npm run build
```

生产 Vite secured build 通过隔离 mock API 和 synthetic JWT 在真实浏览器验证 401、分析成功、fallback/no evidence、409 刷新、审核、知识 403 read-only、审计分页和质量视图。375x812、768x1024、1280x800 的 33 张状态截图均非空，document-level 横向溢出为 false；证据位于 `.omo/evidence/task-11-browser/`。

本轮没有实现真实 OIDC 登录、token refresh、生产身份、Docker/MySQL、外部 API 调用或自主动作。Task 12 仍负责 Playwright/axe/Lighthouse 和完整性能预算；Task 10 live provider machine gate 仍按既有记录阻塞。上述本地证据不能描述成生产认证、生产流量、真实企业部署或正式模型效果。
