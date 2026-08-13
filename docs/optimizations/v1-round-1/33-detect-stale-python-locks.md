# 优化 33：自动检测过期的 Python 锁文件

## 原来的问题

第 32 轮已经建立范围文件和锁文件，但二者是否同步仍完全依赖开发者记忆：

```text
修改 requirements.txt
        ↓
忘记重新生成 requirements.lock.txt
        ↓
提交了不完整的依赖变更
```

其他人按锁文件安装时不会得到新增依赖。程序可能直到运行到对应 `import` 时才失败，而且报错发生位置离真正原因“忘记更新锁文件”很远。

## 本次如何修改

新增检查命令：

```bash
.venv/bin/python -m scripts.check_dependency_locks
```

检查器分别处理两组文件：

```text
requirements.txt
-> requirements.lock.txt

requirements-dev.txt
-> requirements-dev.lock.txt
```

每一组都会在系统临时目录中重新运行 `uv pip compile`，再与仓库锁文件比较。临时目录退出时自动清理，正式锁文件不会被覆盖。

## 为什么先复制现有锁文件

`uv pip compile` 会优先保留输出文件中已经锁定且仍然合法的版本。检查器先把仓库锁文件复制到临时输出位置，然后再解析当前范围文件。

这样检查的问题是：

```text
当前锁定版本是否仍能准确表达当前范围文件？
```

而不是：

```text
包索引今天是否发布了更新版本？
```

因此，新版本发布不会让检查器无缘无故失败。只有范围文件变化导致锁定内容应该变化时，才报告过期。

## 为什么忽略顶部生成命令

`uv` 会把输出文件路径写在锁文件顶部注释中。临时文件路径每次都不同，如果直接比较整份文本，依赖完全一致也会被误报。

比较器只移除第一个依赖之前的生成命令注释，仍然保留：

- 包名和准确版本。
- 环境条件。
- SHA-256 hash。
- `# via` 依赖来源。

所以临时路径不会影响结果，但直接依赖和间接依赖关系发生变化时仍会被发现。

## 退出码

检查成功：

```text
Python dependency locks are up to date.
exit code = 0
```

检查失败：

```text
Python dependency locks are stale:
- requirements.lock.txt
- requirements-dev.lock.txt
Regenerate the lock files with the commands in README.md.
exit code = 1
```

非零退出码使本地脚本和未来的 CI 都能阻止不完整的依赖变更继续通过。

## 红绿验证

第一版比较函数直接比较完整文本。测试提供相同版本和 hash、不同顶部命令注释，测试按预期失败，证明直接文本比较会误报。

修正后，三类测试通过：

1. 只有顶部生成命令不同，视为一致。
2. 包版本不同，视为过期。
3. `# via` 依赖来源不同，视为过期。

随后进行真实故障演练：临时在 `requirements.txt` 增加 `redis>=5.0,<6.0`，故意不更新锁文件。检查器列出两个过期锁文件并返回退出码 `1`。撤销临时依赖后，同一命令恢复为退出码 `0`。

## 相对 V1 的改进

优化前：

```text
开发者必须记得更新锁文件
忘记后仍可能正常提交
```

优化后：

```text
检查器重新计算并比较锁文件
不一致时明确失败并列出过期文件
```

项目从“文档提醒”前进到“机器可以验证”。

## 自动化验证

- 专项测试：3 条通过。
- 当前真实锁文件检查：通过。
- 过期锁文件故障演练：返回退出码 `1`。
- Python 完整测试：52 条通过。
- mock 评估：18 条案例通过，失败案例为 0。

## 涉及文件

- `services/support-copilot-ai/scripts/__init__.py`
- `services/support-copilot-ai/scripts/check_dependency_locks.py`
- `services/support-copilot-ai/tests/test_dependency_locks.py`
- `README.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/33-detect-stale-python-locks.md`

## 当前边界

检查命令目前需要开发者主动运行，仓库还没有 GitHub Actions 或 pre-commit 自动触发它。下一步可以把它接入 CI，使每个远程提交都必须通过检查。

检查器需要访问 Python 包索引来重新解析依赖。网络或包索引不可用时命令也会失败；这种失败不能被伪装成“锁文件同步”。
