# 优化 28：覆盖全部案例错误显示分支

## 原来的问题

结构化失败详情共有六种合法类型：

```text
classification
priority
escalation
citation
no_evidence_safety
reply_constraint
```

Markdown 报告已经为六种类型实现中文显示，但自动化测试只直接检查了分类和优先级。其他四个显示分支如果在后续修改中被误删或写错，测试不一定能准确指出是哪个分支发生回归。

## 本次如何修改

增加一组 `pytest.mark.parametrize` 参数化测试。测试函数只写一份，参数列表分别提供六种 `CaseFailure` 输入和对应的报告文字。

pytest 会把它展开成六轮独立测试：

```text
第 1 轮：classification
第 2 轮：priority
第 3 轮：escalation
第 4 轮：citation
第 5 轮：no_evidence_safety
第 6 轮：reply_constraint
```

测试 ID 使用稳定的英文机器标识。某个分支失败时，pytest 可以直接显示具体类型，例如 `citation`，便于开发者定位。

## 相对原来的改进

```text
原来：
六个显示分支只直接测试两个
-> 其余分支存在未被直接保护的回归风险

优化后：
一组参数化测试覆盖全部六个分支
-> 每种结构化错误都验证对应报告文字
-> 新增错误类型时，测试参数表也需要同步增加
-> 单个分支出错时可以快速定位
```

## 本次没有修改什么

本次只补充防回归测试，没有修改：

- AI 分析逻辑。
- 案例通过或失败的判断规则。
- 评估指标和发布门槛。
- Markdown 的现有显示文案。

因此这轮优化提高的是测试保护范围，不是模型准确率。

## 自动化验证

- 参数化测试单独运行：6 条全部通过。
- 完整 Python 测试：47 条全部通过。
- 真实 mock 评估：18 条案例，基线通过。
- `git diff --check`：通过。

完整测试仍有一条已有警告：Starlette `TestClient` 使用的 `httpx` 接口已弃用，后续需要迁移到 `httpx2`。当前虚拟环境仍未安装 `ruff` 和 `basedpyright`。

## 涉及文件

- `services/support-copilot-ai/tests/test_evaluation_report.py`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/28-case-failure-rendering-tests.md`

## 当前边界

该测试直接保护 Markdown 报告的用户可见输出。它不能证明 AI 是否正确分析工单；AI 分析质量仍由评估案例、准确率、安全率和发布门槛负责衡量。
