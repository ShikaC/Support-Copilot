# 优化 34：使用 GitHub Actions 自动验证 Python AI 服务

## 原来的问题

第 33 轮已经提供锁文件检查命令，但它仍然依赖开发者主动运行：

```text
开发者修改代码或依赖
        ↓
忘记执行本地检查
        ↓
有问题的提交仍然被推送到 GitHub
```

本地测试通过也不能证明其他电脑能够重新安装依赖并得到相同结果，因为本机 `.venv` 可能残留以前安装的包。

## 本次如何修改

新增 GitHub Actions 工作流：

```text
.github/workflows/python-ai-ci.yml
```

它会在以下事件发生时自动启动：

- 向仓库推送代码。
- 创建或更新 Pull Request。

CI 使用 GitHub 临时提供的 Linux 环境，并按顺序执行：

```text
下载仓库代码
-> 安装 Python 3.11
-> 按 requirements-dev.lock.txt 安装依赖
-> 检查范围文件与锁文件是否同步
-> 运行 Python 测试
-> 运行固定 mock 评估
```

步骤是线性执行的。任何一步返回非零退出码，任务都会失败，后续步骤不会把失败结果改成成功。

## 为什么使用开发锁文件

CI 需要运行测试、锁文件检查和评估，因此除了生产依赖，还需要 `pytest`、`httpx2` 和 `uv` 等开发工具。

安装命令是：

```bash
python -m pip install --require-hashes -r requirements-dev.lock.txt
```

开发锁文件固定直接依赖、间接依赖、准确版本和发行文件 hash。这样 CI 不会在不同时间随机选择不同依赖版本。

## 为什么不需要 OpenAI API Key

CI 运行的是固定 mock 评估。评估入口明确创建：

```python
Settings(ai_mode="mock")
```

因此 CI 不会调用真实模型，不消耗 API 预算，也不会要求把密钥交给普通测试流程。

## 安全和稳定性设置

### 只读权限

工作流只声明：

```yaml
permissions:
  contents: read
```

检查任务只需读取仓库，不应该拥有修改代码、创建发布或写入其他 GitHub 资源的权限。

### 固定第三方 Action

工作流使用 GitHub 官方的 `actions/checkout` 和 `actions/setup-python`，并固定到已经核对过的完整 Git 提交 SHA。

完整 SHA 不会像版本标签一样被移动，可以降低 Action 依赖被替换后改变 CI 行为的风险。旁边保留版本注释，方便后续维护升级。

### 限制运行时间

任务设置 `timeout-minutes: 15`。如果网络或工具异常导致任务一直不结束，GitHub 会取消它，而不是无限占用 CI 时间。

### 缓存下载文件

`setup-python` 根据 `requirements-dev.lock.txt` 缓存 pip 下载内容。锁文件变化时缓存键也会变化；缓存只用于减少重复下载，正式安装仍然执行 `--require-hashes` 校验。

## 相对 V1 的改进

优化前：

```text
检查是否执行取决于开发者记忆
本机旧环境可能掩盖依赖缺失
GitHub 不知道提交是否通过测试和评估
```

优化后：

```text
每次推送和 Pull Request 自动创建干净环境
锁文件、测试和评估形成统一验收链路
任意一步失败都会留下明确的 GitHub 检查结果
```

项目由“本地可以手动验证”前进到“远程提交拥有自动验收入口”。

## 自动化验证

工作流提交前完成了以下本地验证：

- `actionlint v1.7.12`：工作流语法和 GitHub Actions 结构检查通过。
- 全新 Python 3.11 虚拟环境：按开发锁文件和 hash 安装成功。
- 锁文件同步检查：通过。
- Python 完整测试：52 条通过。
- 固定 mock 评估：18 条案例通过，失败案例为 0。
- `git diff --check`：通过。

本地验证能够证明工作流语法和其调用命令有效，但不能替代 GitHub 托管环境的实际执行。提交推送后，还要在 GitHub Actions 页面确认第一次远程运行结果。

## 涉及文件

- `.github/workflows/python-ai-ci.yml`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/33-detect-stale-python-locks.md`
- `docs/optimizations/v1-round-1/34-python-ai-github-actions-ci.md`

## 当前边界

- 当前 CI 只覆盖 Python AI 服务，Java 和 React 仍需后续接入自动验证。
- 只配置 CI 不会自动禁止失败代码进入 `master`，还需要在 GitHub 仓库中配置分支保护和必需检查。
- 当前没有上传测试覆盖率或评估报告 artifact。
- CI 尚未替代真实 live 模式验证；mock 评估结果不能代表真实模型或生产 RAG 效果。
