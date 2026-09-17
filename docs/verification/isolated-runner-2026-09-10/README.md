# 隔离运行器与13题真实诊断

**已执行用户明确授权的固定development真实诊断；当前产品未通过回答质量验收。** 13题最终全部为证据不足降级。实际查询和候选列表完全相同，已经定位到正文前180字符截断导致业务上下文未进入检索。本轮保留全部真实结果，没有重跑挑选成功；没有修改该生产逻辑或宣称修正收益。

唯一真实run：[development-live-diagnostic-20260910](../quality-runs/development-live-diagnostic-20260910/RESULTS.md)。[summary](../quality-runs/development-live-diagnostic-20260910/summary.json)记录数字，[manifest](../quality-runs/development-live-diagnostic-20260910/manifest.json)记录配置，[DIAGNOSIS](../quality-runs/development-live-diagnostic-20260910/DIAGNOSIS.md)记录已确认缺陷。[授权修订](AUTHORIZATION.md)在调用前保存：标签未人审也可先诊断，语义分数必须留空。

## 实际结果

| 项目 | 本轮实测 |
| --- | --- |
| 固定输入/执行/未执行 | 13 / 13 / 0；并发1；holdout0 |
| 应用侧真实SDK操作 | query Embedding13，generation13，document Embedding0 |
| SDK操作终态 | 26个STARTED和26个SUCCEEDED；未知中断0 |
| 正常live最终回答 | 0/13 |
| 最终证据不足/超时/其他降级/未知错误 | 13 / 0 / 0 / 0 |
| API分析返回/即时全对象匹配/重启全对象匹配 | 13 / 13 / 13 |
| 创建到分析返回（包含Java保存）p50 / p95 | 6.863s / 18.640s；13个样本，nearest-rank；含全部降级 |
| 已返回generation token | input28119 / output3596，13个响应；不是账单 |
| 输入人审/输出人审 | 未完成 / 0 |
| 准确率/解决率/节省工时/总费用 | 未测，null |

这是真实外部模型和Embedding响应，但13个最终回复均是实际工作流生成的安全fallback。SDK正常完成、HTTP200和保存成功分别保留，不合并成正常AI回答成功。数据来自公开归档上人工构建对话及公开issue，不是内部真实客服日志。当前检索缺陷使本轮只适合故障诊断，不能拿这组延迟当正常业务查询的代表性基线。0超时也不能证明旧超时问题已经优化。

逐题原始Java分析响应、即时history和重启完整history保存在run的`trials/`与`restart-readback.json`。`attempts.jsonl`记录每次provider操作开始/终态/trace；`retrieval/`保存候选原貌，Java响应显示最终采用状态。账本不证明远端接收或费用；没有保存供应商原始HTTP响应或中间ModelDraft，不能冒充完整供应商原文归档。

## 本轮实现与为何改这一层

原runner固定旧run-1，直接复跑有覆盖风险，且缺少逐次调用账本。新增运行工具，不改生产Java/Python业务逻辑、提示词、模型或知识库内容：

- `scripts/benchmark/isolated-inputs.mjs`：验证冻结来源/白名单、独占目录、保留端口与人工审核身份；绝不把gold/holdout发模型。
- `isolated-runtime.mjs`：独立JAR、文件H2和端口；固定实际模型/协议/endpoint身份及20/90/105/130秒期限；复用1564×1024已有artifact，禁止自动重建。
- `isolated-engine.mjs`与`run-isolated.mjs`：顺序创建/分析/读回、trace关联、失败停止、保存未执行行、重启全对象核对；一次性dataset claim阻止续跑和重复付费。
- `services/support-copilot-ai/evaluation/isolated_observation.py`、`isolated_benchmark_app.py`、`isolated_preflight.py`：基准专用观察器复用真实provider/生产工作流；调用前写STARTED并执行预算保护。未知程序错误或证据写盘失败保留原错误并锁定后续调用；已建模模型降级不会被误判为未知错误。
- `summarize-isolated.mjs`：仅离线汇总真实记录，生成可读回复和空白人审表；不生成质量分数。

实际run保存源码副本/哈希与JAR摘要；开发树仍dirty，因此不能仅用HEAD证明运行版本。Java使用loopback demo安全profile提供本地匿名访问，但fixture关闭且调用前实际GET确认空工单库，Python为live。本轮未使用演示工单、mock模型，也未验证生产身份系统。

## 验证与失败记录

根目录实际执行：

```sh
node --test scripts/benchmark/isolated-runner.test.mjs
services/support-copilot-ai/.venv/bin/python -m pytest services/support-copilot-ai/tests/test_isolated_observation.py -q
node scripts/benchmark/run-isolated.mjs --id development-live-diagnostic-20260910 --execute --diagnostic
node scripts/benchmark/summarize-isolated.mjs development-live-diagnostic-20260910
node docs/verification/isolated-runner-2026-09-10/verify.mjs
node scripts/quality/verify-delivery.mjs
node --test scripts/quality/reports.test.mjs
```

上述真实执行命令仅用于追溯，**不要再次执行模型命令**。本轮claim与原始run不可覆盖。摘要脚本也拒绝覆盖已存在产物；现有报告可直接阅读，无需重建。

Node11项、Python9项定向测试通过；Ruff通过；在AI服务目录执行`uvx basedpyright --pythonpath .venv/bin/python evaluation/isolated_observation.py evaluation/isolated_benchmark_app.py evaluation/isolated_preflight.py`为0错误/0警告。真实隔离Gradle bootJar成功；此轮未运行全仓/前端测试，因没有修改业务或UI源码。旧报告导出8项测试通过。命令输出见本目录日志，独立AI代码审查见[CODE_REVIEW](CODE_REVIEW.md)，不是人工质量审阅。

失败路径测试覆盖占用TCP端口、不合法ID/保留端口、未人审模板、标签/SHA不一致、嵌套读回不一致、预算耗尽、未知异常、429、操作中断、账本/检索写盘故障、成功provider后下游异常和模型合法降级。真实CLI未人审执行门禁和已有目录拒绝覆盖均在任何付费调用之前按预期阻断，见`review-gate.log`、`overwrite-gate.log`；用户明确诊断授权用`--diagnostic`区分。

两次早期prepare记录保留在`quality-runs/preflight-development-20260910`与`preflight-development-final-20260910`，均0调用。第一份存在已修复的evidenceKind错误文字（inputHumanReview仍明确PENDING），只能视为运行器开发过程记录，不能当人审通过。其后预算/配置/异常保护修复均已进入实际run源码快照。开发时缺失本地ruff、从错误工作目录做类型检查、最后类型字典赋值与import排序均曾失败；最终用正确工具/目录与实际修复通过，没有删除业务失败记录或弱化门禁。

## 产品操作与后续限制

详细操作见[OPERATIONS](OPERATIONS.md)：知识库页面目前没有正文新增/编辑/删除，release元数据操作不等于内容上传；工单回复“记录审核/拒绝建议”已有真实保存路径，但质量页的评测人工审核目前仍需文件/CLI，尚无网页逐题提交入口。

[本轮输出审核表](../quality-runs/development-live-diagnostic-20260910/output-review-working.json)、[输入参考审核表](input-review-working.json)和[旧22例事实审核表](live22-review-working.json)均保持待审。不要用AI代填reviewer，不要手改质量页人审计数。新13题尚未接入质量页；18174预览中的旧22/96数据不能解释为本轮结果。

下一切片优先修复query构造与上下文保留，方案与验收见实际run的DIAGNOSIS。先离线回归，再另行预注册development复测；旧13题已见输出，不是未见盲测。超时先保留逐次调用证据，之后单变量测量输出长度/有效上下文/等待上限；本轮没有提高deadline或增加重试，不能宣称超时优化完成。

## Git、环境与简历边界

HEAD `4df3bf44907c34318132496929bad4a3974ad88b`，master、dirty，无提交/推送/部署。`workspace-before.json`保护本轮开始时1525个文件；只更新STATUS、ROADMAP、READING_LOG、HANDOFF四个权威文档，其他既有源码、旧报告、旧JAR/artifact逐项不变。新文件及结果以`verification.json`摘要为准。原工作台18173/18080/18000和数据库不重启/不写入；独立18280/18200服务在结束时已停止，日志和H2只保留在`.local/quality-runs/development-live-diagnostic-20260910/`。

可写简历：实现真实评测运行隔离、逐次调用预算/失败保护、Java/Python真实链路完整重启读回；以固定13题运行证据定位query截断造成的检索退化。不可写回答准确率、问题解决率、降本、生产容量、企业客户经历或尚未测得的修复收益。
