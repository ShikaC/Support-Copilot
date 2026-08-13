# 优化 29：防止新增案例错误类型漏测

## 原来的问题

第 28 轮已经用参数化测试覆盖六种案例错误，但存在两份需要人工保持一致的名单：

```text
models.py
允许保存哪些 CaseFailureMetric

test_evaluation_report.py
哪些 CaseFailureMetric 已经拥有显示测试
```

如果以后允许名单增加 `spelling`，开发者却忘记增加对应的显示测试，pytest 仍只会运行原来的六组参数，无法主动报告漏测。

## 本次如何修改

使用 Python 的 `get_args()` 读取 `CaseFailureMetric` 中的全部 `Literal` 值：

```python
allowed_metrics = set(get_args(CaseFailureMetric))
```

再从参数化案例中取得全部已测试类型：

```python
tested_metrics = {failure.metric for failure, _ in FAILURE_RENDERING_CASES}
```

最后要求两份集合完全相等：

```python
assert tested_metrics == allowed_metrics
```

只要允许名单新增、删除或改名，而测试参数没有同步修改，这条完整性测试就会失败。

## 红绿验证

为了证明测试确实能发现漏项，首次运行时故意没有加入 `reply_constraint`。测试失败并明确显示：

```text
Extra items in the right set:
'reply_constraint'
```

补回 `reply_constraint` 后，专用 Markdown 测试变为 7 条全部通过：

- 6 条分别检查六种错误的报告文字。
- 1 条检查测试类型与允许类型完全一致。

## 测试文件拆分

案例错误显示测试从完整报告测试中移到独立文件：

```text
test_evaluation_report.py
负责完整评估报告行为

test_evaluation_markdown.py
负责单条案例错误的 Markdown 显示和覆盖完整性
```

拆分后，两个测试文件的职责更明确，也避免完整报告测试继续膨胀。

## 相对原来的改进

```text
原来：
开发者人工维护允许名单和测试名单
-> 新增类型时可能忘记补测试

优化后：
自动比较 allowed_metrics 和 tested_metrics
-> 漏测立即导致测试失败
-> pytest 会指出缺少的具体类型
```

## 自动化验证

- 故意漏掉 `reply_constraint`：完整性测试按预期失败。
- 补齐后专用 Markdown 测试：7 条全部通过。
- 完整 Python 测试：48 条全部通过。
- 真实 mock 评估：18 条案例，基线通过。
- `git diff --check`：通过。

完整测试仍有一条已有的 Starlette/httpx 弃用警告。当前虚拟环境仍未安装 `ruff` 和 `basedpyright`。

## 涉及文件

- `services/support-copilot-ai/tests/test_evaluation_report.py`
- `services/support-copilot-ai/tests/test_evaluation_markdown.py`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/29-case-failure-test-completeness.md`

## 当前边界

这条完整性测试只能证明每种允许类型都有对应的参数化案例。具体显示文字是否正确，仍由同一文件中的六条参数化测试分别验证。
