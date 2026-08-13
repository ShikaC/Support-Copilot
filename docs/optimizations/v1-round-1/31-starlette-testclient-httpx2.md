# 优化 31：将 Starlette 测试客户端迁移到 httpx2

## 原来的问题

Python 测试虽然全部通过，但每次运行都会出现弃用警告：

```text
Using `httpx` with `starlette.testclient` is deprecated;
install `httpx2` instead.
```

当前功能仍可使用，但 Starlette 已说明旧的测试客户端依赖将在未来被移除。继续忽略警告，会把兼容性风险推迟到依赖升级时集中暴露。

## 运行机制

当前 Starlette `TestClient` 会按以下顺序选择客户端：

```text
优先导入 httpx2
        ↓ 失败
回退导入旧 httpx
        ↓
发出弃用警告
```

V1 的开发依赖只明确声明了旧 `httpx`，因此每次 API 测试都会进入回退分支。

## 本次如何修改

将测试客户端的开发依赖改为：

```text
httpx2>=2.0,<3.0
```

下限 `2.0` 来自当前 Starlette 1.3.1 的依赖要求；上限避免未来自动跨入不兼容的主版本。

pytest 同时增加定向警告保护：

```ini
filterwarnings =
    error:Using `httpx` with `starlette.testclient` is deprecated:starlette.exceptions.StarletteDeprecationWarning
```

如果以后开发依赖误删 `httpx2`，Starlette 再次回退旧客户端，这条警告会直接让测试失败，不会被长期忽略。

README 的安装和启动命令也改为由虚拟环境 Python 启动模块：

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

这样不依赖 pip 或 uvicorn 脚本中记录的历史绝对路径。即使项目目录移动过，命令仍明确使用当前 `.venv` 的 Python。

## 两个 HTTP 包为什么共存

迁移过程中曾临时卸载旧 `httpx`。运行证据表明，这会破坏其他依赖：

```text
openai 2.49.0 requires httpx
langsmith 0.10.10 requires httpx
```

并且 `import openai` 会因为找不到 `httpx` 直接失败。

因此正确状态不是二选一，而是各自承担不同职责：

```text
httpx2 2.10.0
-> Starlette TestClient 使用

httpx 0.28.1
-> OpenAI 和 LangSmith 使用
```

实际运行确认 `TestClient` 的父类来自 `httpx2`，同时 OpenAI 仍可正常导入，`pip check` 也没有发现损坏的依赖。

## 红绿验证

迁移前，将该弃用警告提升为错误后，API 测试在收集阶段失败：

```text
ModuleNotFoundError: No module named 'httpx2'
StarletteDeprecationWarning: Using `httpx` ... is deprecated
```

安装 `httpx2` 后，同一警告保护保持启用，API 测试与完整测试均通过且不再输出 warning。

## 自动化验证

- `pip check`：没有损坏的依赖。
- 实际客户端检查：`TestClient` 父类来自 `httpx2`。
- API 测试：6 条全部通过。
- 完整 Python 测试：49 条全部通过，无 warning。
- 真实 mock 评估：18 条案例，基线通过。

## 涉及文件

- `services/support-copilot-ai/requirements-dev.txt`
- `services/support-copilot-ai/pytest.ini`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/31-starlette-testclient-httpx2.md`

## 当前边界

本次只迁移 Starlette 的测试客户端依赖，没有把 OpenAI SDK 的内部 HTTP 客户端改为 `httpx2`。live 模式仍受 OpenAI SDK 自身依赖约束，不能为了消除测试警告而卸载旧 `httpx`。

项目当前仍使用范围依赖文件而不是锁文件。不同时间重新创建环境时可能安装不同的小版本或次版本；后续需要根据部署方式决定是否引入可复现的依赖锁定流程。
