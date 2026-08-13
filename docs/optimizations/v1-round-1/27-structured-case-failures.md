# 优化 27：结构化保存案例失败详情

## V1 原来的问题

案例检查会把错误直接拼成英文句子：

```text
priority: expected HIGH, got LOW
```

这句话适合人阅读，却不适合程序继续处理。程序如果想分别取得错误类型、人工标准答案和系统实际答案，只能再次拆解字符串。显示文案稍有变化，拆解逻辑就可能失效。

判断错误的代码同时决定了英文显示内容，也让“业务判断”和“报告展示”混在一起。

## 本次如何修改

新增 `CaseFailure` 数据模型，将每条案例错误保存为三个独立字段：

```json
{
  "metric": "priority",
  "expected": "HIGH",
  "actual": "LOW"
}
```

- `metric`：错误属于哪个评估指标。
- `expected`：人工评估集给出的标准答案。
- `actual`：Python 分析工作流产生的实际结果。

分类、优先级、人工升级、引用、无证据安全和回复约束现在都使用统一的结构化错误模型。

## 判断与展示分工

```text
case_checks.py
比较人工标准答案和系统实际结果
        ↓
生成 CaseFailure 结构化数据
        ↓
markdown.py
根据 metric 生成中文说明
```

例如，结构化的优先级错误会显示为：

```text
优先级：预期 HIGH，实际 LOW
```

`case_checks.py` 不再决定中文或英文文案。以后增加网页报告、英文报告或其他输出格式时，可以继续使用同一份结构化数据。

## 相对 V1 的改进

```text
V1：
错误是一整句英文字符串
-> 程序无法可靠读取单个字段
-> 判断逻辑与显示文案耦合

优化后：
错误保存为 metric / expected / actual
-> JSON 可以直接读取和筛选
-> Markdown 负责中文展示
-> 修改显示语言不会影响错误判断
```

## 自动化测试

测试验证：

- 优先级错误可以分别读取 `metric`、`expected` 和 `actual`。
- 结构化错误可以正确序列化为 JSON 对象。
- 分类、优先级、人工升级、引用、无证据安全和回复约束仍能正确生成失败详情。
- Markdown 使用中文展示分类和优先级错误。
- 完整 Python 测试通过，共 41 条测试。
- 真实 mock 评估运行成功，共 18 条案例且基线通过。

## 涉及文件

- `services/support-copilot-ai/evaluation/models.py`
- `services/support-copilot-ai/evaluation/case_checks.py`
- `services/support-copilot-ai/evaluation/markdown.py`
- `services/support-copilot-ai/tests/test_evaluation_case_checks.py`
- `services/support-copilot-ai/tests/test_evaluation_report.py`

## 当前边界

`metric` 和约束名称仍使用稳定的英文机器标识，便于 JSON 消费者处理；中文只属于 Markdown 显示层。当前真实 mock 基线没有失败案例，因此生成的基线报告不会出现失败详情，错误路径由自动化测试中的故意错误结果覆盖。

当前虚拟环境没有安装 `ruff` 和 `basedpyright`，本次无法执行这两项静态检查；完整 `pytest` 和真实 mock 评估均已通过。
