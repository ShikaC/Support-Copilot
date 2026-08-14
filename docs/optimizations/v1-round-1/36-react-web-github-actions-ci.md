# 优化 36：使用 GitHub Actions 自动验证 React 前端

## 原来的问题

第 34、35 轮分别自动验证了 Python 和 Java，但 React 前端仍只依赖开发者手动检查：

```text
Python CI 通过 + Java CI 通过
              ↓
不能证明 React 代码通过静态检查
也不能证明 TypeScript 能编译或 Vite 能生成生产文件
```

因此，一个只破坏前端的提交仍可能在缺少本地检查时进入仓库。

## 本次如何修改

新增工作流：

```text
.github/workflows/react-web-ci.yml
```

它会在每次 `push` 和 Pull Request 时执行：

```text
下载仓库代码
-> 准备 Node.js 24
-> 按 package-lock.json 执行 npm ci
-> 执行 npm run lint
-> 执行 npm run build
```

任意步骤失败，整个 `React Web CI` 任务都会失败。

## 为什么使用 Node.js 24

项目使用的 Vite 8 要求 Node.js `^20.19.0 || >=22.12.0`。虽然旧 README 允许 Node.js 20，但 Node.js 20 已经停止维护；本轮把本地环境说明和 CI 统一为仍受支持的 Node.js 24 LTS。

工作流使用官方 `actions/setup-node` 准备 Node.js，并将 Action 固定到完整提交 SHA。Node.js 版本不再取决于 GitHub 临时机器原本安装了什么。

## 为什么使用 npm ci

`npm ci` 严格按照 `package-lock.json` 安装依赖：

```text
package.json 与锁文件一致 -> 安装锁定版本
package.json 与锁文件不一致 -> 立即失败
```

CI 不复用开发者本机原有的 `node_modules`，避免旧依赖或额外依赖掩盖问题。

## 工作目录和缓存

前端文件位于：

```text
apps/support-copilot-web
```

工作流把该目录设为所有 `run` 命令的默认工作目录，所以 `npm ci`、lint 和 build 都会读取正确的 `package.json`。

`actions/setup-node` 根据 `apps/support-copilot-web/package-lock.json` 缓存 npm 下载内容。缓存只减少重复下载，不缓存 `node_modules`，也不会跳过安装、lint 或 build。

## 检查链路

前端脚本定义为：

```json
"lint": "oxlint",
"build": "tsc -b && vite build"
```

因此本轮 CI 覆盖：

- `oxlint` 静态代码检查。
- TypeScript 项目编译检查。
- Vite 生产构建。

只有前一步成功，后一步才会执行。

## 安全与资源边界

工作流只有仓库只读权限，并设置 15 分钟超时。第三方 Action 都固定为完整 Git 提交 SHA，并在旁边记录对应发布版本：

- `actions/checkout` v7.0.1。
- `actions/setup-node` v7.0.0。

## 相对 V1 的改进

优化前：

```text
React 检查依赖开发者手动执行
Python 和 Java CI 绿色可能被误认为整个项目正常
前端依赖环境可能复用本机旧 node_modules
```

优化后：

```text
每次推送和 Pull Request 自动验证 React
Python、Java、React 分别拥有独立 CI 结果
Node.js 版本、锁定依赖、lint 和生产构建进入验收链路
```

## 自动化验证

本轮在本地完成以下验证：

- `actionlint v1.7.12`：React 工作流语法和 Actions 结构检查通过。
- Node.js：`24.18.0`。
- npm：`11.16.0`。
- 干净环境：把前端源码复制到不包含 `node_modules` 和 `dist` 的临时目录。
- `npm ci`：按锁文件安装 99 个包，退出码为 0。
- `npm run lint`：通过。
- `npm run build`：TypeScript 和 Vite 构建通过，共转换 3839 个模块。
- `git diff --check`：通过。

构建仍然报告主 JavaScript 包超过 500 kB 的提示。当前产物可以成功生成，因此这不是本轮 CI 的失败条件；后续应单独分析路由拆分和依赖体积，不能通过提高警告阈值掩盖问题。

本地验证不能替代 GitHub 托管环境的运行结果。提交推送后，还需要确认 GitHub Linux 环境中的第一次 CI 状态。

## 涉及文件

- `.github/workflows/react-web-ci.yml`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/35-java-api-github-actions-ci.md`
- `docs/optimizations/v1-round-1/36-react-web-github-actions-ci.md`

## 当前边界

- 新工作流尚未推送，所以 GitHub 托管环境还没有实际运行记录。
- 三条 CI 尚未配置为 `master` 合并前的必需检查。
- React 当前没有自动化组件测试或端到端测试；本轮只覆盖静态检查和生产构建。
- 现有前端主包仍有体积提示，需要后续单独优化和验证。
