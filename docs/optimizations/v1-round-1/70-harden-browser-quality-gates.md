# 第 70 轮：加固浏览器质量门禁的非浏览器基础

## 问题与风险

Task 12 的首次独立代码审查发现，浏览器门禁存在会产生假绿的基础缺陷：布局审计过滤掉被遮挡或首屏外的控件，bundle 预算只计算入口文件，canvas 只检查 alpha，按需加载失败没有恢复状态，Playwright runner 在父进程信号下可能遗留子进程，隔离 mock 也没有严格执行真实 Spring 命令契约。

## 修改层与流程

React 壳现在用可重试错误边界包住 lazy view；加载失败时保留导航和页面壳，并允许重新创建 lazy component 后重试。拒绝审核对话框覆盖正向/反向焦点循环、Escape、关闭状态和真实 `ReplyReview` owner 的取消后焦点恢复。

Vite manifest 门禁从 `index.html` 递归遍历全部静态 imports，以集合去重初始 modulepreload 图；lazy chart 只计算初始图之外的增量文件。预算同时记录 Task 12 前的真实 raw/gzip 基线、允许 delta 和最终 limit。Node fixture 证明重复可达的传递依赖只计算一次，并能让超限门禁失败。

浏览器布局审计会逐个滚动所有可见且有尺寸的交互控件，报告滚动后仍离屏、无法命中、嵌套交互、普通重叠和无 DOM 祖先关系的 sticky/fixed 遮挡，并恢复原滚动位置；每类 finding 都有零长度断言。canvas 门禁计算主背景色之外的像素和颜色数量。runner 共用可测试的进程组、SIGINT/SIGTERM 和最多三次端口碰撞重试逻辑。mock API 的 method、Idempotency-Key 和 DTO body 检查与实际 Spring controller 保持一致，没有为 fixture 修改生产请求。

## 验证与边界

```bash
cd apps/support-copilot-web
npm test -- --run
npm run lint
npm run build
npm run build:budget
npm run test:node
```

完整 Vitest 为 61 passed、3 个已配置 live contract skipped；Node 为 11/11 passed。初始 JS 为 821599 raw / 263752 gzip，lazy chart 增量为 1142407 / 376260，总 JS 为 1977922 / 644906，CSS 为 27095 / 5845，均在预算内。详细证据见 `.omo/evidence/task-12-non-browser-repair.md`。

本轮没有执行 Playwright、preview、mock browser server、axe 浏览器扫描或截图验收。Task 12 浏览器 acceptance 仍按前两次授权尝试后的暂停状态记为未验证；后续历史中的浏览器绿色记录不能替代该暂停门禁。本轮也没有修改后端、Task 10、Task 15、计划/ledger、远端配置或执行 push。
