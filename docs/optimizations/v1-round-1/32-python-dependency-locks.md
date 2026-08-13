# 优化 32：锁定 Python 完整依赖树

## 原来的问题

AI 服务原来只有两个依赖范围文件：

```text
requirements.txt
requirements-dev.txt
```

例如 `fastapi>=0.115,<1.0` 只规定允许安装的范围。不同日期或不同电脑重新安装时，解析器可能选择不同的 FastAPI、Starlette 或其他间接依赖版本。测试通过的是当前环境，但项目无法要求新环境安装同一组版本。

第 31 轮迁移 `httpx2` 后，这个风险更加具体：Starlette 测试客户端、OpenAI SDK 和 LangSmith 分别依赖 `httpx2` 或 `httpx`。如果间接依赖自行变化，已经消除的兼容性问题可能再次出现。

## 范围文件与锁文件的职责

本次保留范围文件，同时新增锁文件：

```text
requirements.txt          -> 生产依赖允许范围
requirements-dev.txt      -> 开发依赖允许范围
requirements.lock.txt     -> 生产环境准确版本和文件 hash
requirements-dev.lock.txt -> 开发环境准确版本和文件 hash
```

范围文件由开发者维护，用于表达允许升级的边界。锁文件由工具生成，记录当前验证过的全部直接依赖和间接依赖，不应手工逐行修改。

## 为什么记录 hash

准确版本只能限制包名和版本，例如：

```text
fastapi==0.140.7
```

锁文件还为可安装文件记录 SHA-256 hash。安装时使用 `--require-hashes`，如果下载文件的内容与锁文件不一致，pip 会拒绝安装。因此它同时检查：

1. 安装的版本是否正确。
2. 下载的发行文件内容是否匹配。

## 为什么使用 uv 生成

最初尝试使用 `pip-tools --generate-hashes`。运行采样和详细日志表明，它会逐个下载并计算 `pydantic-core` 等包在多个 Python 版本和操作系统上的大量发行文件 hash；在当前网络代理下，首次生成超过十分钟仍未完成。

本次改用 `uv pip compile`。它仍然输出普通、兼容 pip 的 requirements 锁文件，但可以从包索引信息快速完成跨平台解析。两个锁文件约十秒生成完成。

`requirements-dev.txt` 明确声明：

```text
uv>=0.12,<1.0
```

生成工具属于开发依赖，不进入生产锁文件。

## 生成和升级

项目使用 Python 3.11，并生成跨操作系统锁文件：

```bash
.venv/bin/python -m uv pip compile --universal --python-version 3.11 --generate-hashes --output-file requirements.lock.txt requirements.txt
.venv/bin/python -m uv pip compile --universal --python-version 3.11 --generate-hashes --output-file requirements-dev.lock.txt requirements-dev.txt
```

已有锁文件会作为下一次解析的版本偏好。修改范围文件后运行以上命令，可以只完成必要变化；明确希望升级全部依赖时，才额外使用 `--upgrade`。依赖升级必须再次运行测试和评估，不能只生成文件就认为升级成功。

## 安装方式

开发环境从开发锁文件安装：

```bash
.venv/bin/python -m pip install --require-hashes -r requirements-dev.lock.txt
```

生产环境只需要生产锁文件：

```bash
.venv/bin/python -m pip install --require-hashes -r requirements.lock.txt
```

生产锁文件包含 OpenAI 和 LangSmith 所需的 `httpx`，但不包含测试专用的 `httpx2`、pytest 或 uv。开发锁文件则包含生产依赖和全部测试工具。

## 自动化验证

本次没有只在原有 `.venv` 中验证。系统新建了空白临时虚拟环境，并只根据开发锁文件执行带 hash 的安装：

```text
pip install --require-hashes -r requirements-dev.lock.txt
```

结果：

- 全部锁定依赖安装成功。
- `pip check` 未发现损坏或冲突的依赖。
- Starlette `TestClient` 的父类来自 `httpx2`。
- Python 完整测试 49 条全部通过。
- mock 评估 18 条案例通过，失败案例为 0。

生产锁文件也在独立空白环境中安装，并验证 AI 服务和 OpenAI SDK 可以导入。

## 相对 V1 的改进

优化前：

```text
范围文件 -> 每次重新选择满足范围的版本 -> 环境可能随时间变化
```

优化后：

```text
范围文件 -> 工具有意识地解析和更新锁文件
锁文件   -> 日常安装固定版本和 hash -> 测试对应明确环境
```

这使“49 条测试通过”可以对应到仓库中一组明确的 Python 依赖版本，而不再只对应开发者电脑当时的 `.venv`。

## 涉及文件

- `services/support-copilot-ai/requirements.txt`
- `services/support-copilot-ai/requirements-dev.txt`
- `services/support-copilot-ai/requirements.lock.txt`
- `services/support-copilot-ai/requirements-dev.lock.txt`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/32-python-dependency-locks.md`

## 当前边界

锁文件基于 Python 3.11 生成，并使用通用解析覆盖常见操作系统条件。它不能证明所有操作系统都已经真实运行过测试；本轮实际验证环境是 macOS ARM64、Python 3.11.15。

锁定依赖也不等于依赖永远不升级。安全修复或功能需要出现时，应有意识地更新范围或使用 `--upgrade`，检查锁文件差异，并重新执行完整测试和评估。

后续状态：第 33 轮已经增加过期锁文件检查器，可以在临时目录重新解析范围文件，并在锁文件未同步时返回失败。以上边界仍适用于有意识的依赖升级。
