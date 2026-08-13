# 优化 30：防止案例错误显示测试重复

## 原来的问题

第 29 轮通过集合比较检查测试类型与允许类型是否一致：

```python
assert tested_metrics == allowed_metrics
```

集合 `set` 会自动删除重复值。因此下面的参数表虽然重复测试了 `priority`，转换成集合后仍然只有六种类型：

```text
classification
priority
priority
escalation
citation
no_evidence_safety
reply_constraint
```

集合完整性检查可以发现漏项，却不能发现重复项。重复测试会浪费维护成本，也可能掩盖另一个案例原本应该测试不同类型的错误。

## 本次如何修改

新增独立的唯一性测试。它先用 `tuple` 保留原始参数顺序和重复项：

```python
tested_metrics = tuple(
    failure.metric for failure, _ in FAILURE_RENDERING_CASES
)
```

然后比较原始数量与集合去重后的数量：

```python
assert len(tested_metrics) == len(set(tested_metrics))
```

- 两个数量相同：没有重复类型。
- 原始数量更大：至少有一种类型重复。

## 红绿验证

为了证明测试有效，首次运行时临时加入第二个 `priority`：

```text
原始参数数量：7
去重后的类型数量：6
```

测试按预期失败并显示：

```text
AssertionError: assert 7 == 6
```

删除临时重复项后，参数表恢复为六种类型各一次，专用 Markdown 测试全部通过。

## 两条保护的分工

```text
集合成员比较
tested_metrics == allowed_metrics
-> 防止缺少或多出错误类型

原始数量与去重数量比较
len(tuple) == len(set)
-> 防止同一种错误类型重复出现
```

两条测试组合后，参数表必须满足：允许类型全部覆盖，并且每种类型恰好出现一次。

## 自动化验证

- 临时重复 `priority`：唯一性测试按预期失败，显示 `7 != 6`。
- 删除重复项后专用 Markdown 测试：8 条全部通过。
- 完整 Python 测试：49 条全部通过。
- 真实 mock 评估：18 条案例，基线通过。
- `git diff --check`：通过。

完整测试仍有一条已有的 Starlette/httpx 弃用警告。当前虚拟环境仍未安装 `ruff` 和 `basedpyright`。

## 涉及文件

- `services/support-copilot-ai/tests/test_evaluation_markdown.py`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/30-case-failure-test-uniqueness.md`

## 当前边界

唯一性测试只检查 `metric` 是否重复。不同错误类型的测试数据是否具有代表性，以及中文文案是否符合产品用语，仍需要代码审查和产品验收。
