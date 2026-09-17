# 质量证据中心交付

> 2026-09-10 · 当前工作区实现与验证 · HEAD `4df3bf44907c34318132496929bad4a3974ad88b` · master / dirty

已完成一个产品切片：将冻结原始记录转换为可核验、可查失败原因的产品页面。合成回归和公开文档业务基准分别展示，正常 live、证据不足、超时、其他降级与错误分别计数；人工审核仍为 0，回答准确率、问题解决率、节省工时与费用保持未知。本轮新模型调用 0、Embedding 调用 0，没有新增人工审核、提交、推送或生产部署。

## 已实现的业务变化

1. 新 `/api/quality-reports` 在两个独立槽位读取派生报告，最多读取 2 MiB，同一字节数组同时用于 SHA-256 校验和解析。路径和摘要都未配置、只配置一项、文件缺失、校验失败分别有明确状态。一份失败不影响另一份。local/pilot 仍要求既有支持人员角色；测试验证匿名 401、无关角色 403、三个支持角色 200。
2. 质量页正确区分 live 的“检索流程成功率”“引用规则通过率”和真正的回答准确率。显示实际分母、不同问题数/运行数、人工审核数量、模型产出分类、并发 p50/p95、全部非正常产出明细、case ID、trace ID、源文件摘要和结论限制。
3. 刷新、请求失败重试、结果筛选/全部重置、空分类、单份报告损坏均有可见状态。新报告请求失败/MISSING/INVALID 时，不再显示旧 mock 指标充当替代。只有 live 槽位为 NOT_CONFIGURED 时才显示明确标注的兼容旧评估。
4. 当前鉴权客户端贯穿工作台和新报告请求，避免登录状态与模块默认客户端分离。样式复用现有 DESIGN/Ant Design 原语，修复定义列表语义及按钮悬停对比度；所有 CSS 仍计入原有预算，未提高上限。

## 数据来源和能证明的范围

原始事实分别来自 [22 例合成回归](../ai-quality-fixes-2026-09-10/README.md)、[96 次业务基准](../business-benchmark-2026-09-10/README.md)。派生文件是 [live.json](reports/live.json) 与 [business.json](reports/business.json)，输出摘要见 [manifest.json](reports/manifest.json)。导出器逐条重算正常/降级/超时计数并对照旧摘要；业务即时读回按完整对象重新比较。

本轮派生报告没有重新读取或重演重启过程，未新增重启成功率指标。旧重启证据只保存 id、traceId、mode、回复正文四项匹配结论，不能声称重启后全部字段一致。页面明确说明该边界。

导出器检查合成案例所有人工标签为 NOT_REVIEWED，v1 API 和前端均拒绝非零人审计数和非 null 的四项未知业务指标。未来正式人审导入需要独立契约和审核来源，不能通过改计数假装完成。原始文件摘要由派生报告声明；API 只核验配置指定的派生报告摘要，不冒充重新核查了所有原始文件，也不证明文件由真人签署。

Doc2Dial 是基于公开文档人工构建的对话，不是企业真实客服日志；32 个问题重复于三个并发组，96 次运行不是 96 个独立质量样本。旧输入含寒暄、上下文不足及 fuzzy 标注，词语 F1/跨度覆盖/指定文档命中仍不能写成回答准确率。新输入审计依旧独立保留，详见 [输入审计](../quality-input-audit-2026-09-10/README.md)。

## 实现入口与 Git 边界

数据流：`scripts/quality/{live-report,business-report}.mjs` 重算 → `export-reports.mjs` 独占新目录发布文件及最后的 manifest → Java `quality/QualityReportsReader` / `QualityReportParser` → `/api/quality-reports` → Zod `services/qualityReports.ts` → `features/quality/QualityView`。

新文件及修改文件摘要见 `verification.json`。前端共享样式仅进行有记录的声明合并/原语复用，具体转换清单见 [css-consolidation.json](css-consolidation.json)。首次合并前没有保存精确字节副本，因此不声称有逐像素前后等价证据；最终运行通过五页三种屏宽检查和既有 21 个 E2E 场景。没有用 Git 回退覆盖此前未提交改动。

[本轮工作区基线](workspace-before.json) 记录 1,411 个既有文件。`verify-delivery.mjs` 仅允许列明的产品/文档文件变化，确认三个旧实验目录中的 452 个文件完全未变，并检查旧输入审计 manifest 的 26 项摘要。旧 run-1、旧脚本与冻结标签未修改。现有旧 JAR 保留；新 Java 包输出到 `.local/quality-center/build`，未覆盖旧运行 JAR。

## 验证命令和结果

| 范围 | 命令 | 最终结果与边界 |
|---|---|---|
| 导出与反造假 | 根目录 `node --test scripts/quality/reports.test.mjs` | 8 通过：真实两份数据、HTTP200超时分类、完整读回、坏摘要、伪人审、重复、重复导出拒绝 |
| 历史保护 | 根目录 `node scripts/quality/verify-delivery.mjs` | PASS；只证明本轮清单与哈希保护，不替代人工答案审核 |
| Java | API 目录 `./gradlew test --tests '*QualityReports*Tests' --tests '*EvaluationReportReaderTests' --tests '*MetricsServiceTests' --max-workers=1` | 53 通过、0 失败、0 跳过；其中新质量 45，旧评估/metrics 8；未跑本轮全仓/MySQL门禁 |
| Web | Web 目录 `npm test` | 108 通过、3 项原有显式跳过 |
| Web Node | Web 目录 `npm run test:node` | 12 通过 |
| Web E2E | Web 目录 `npm run test:e2e` | 21 通过；合成 mock API，覆盖审核/冲突/知识发布/审计/图表/键盘/三个屏宽，不是新增真实模型测量 |
| 构建 | Web 目录 `npm run build:budget` | TypeScript、生产构建及原预算通过；CSS 39,506/40,000 bytes，gzip 8,483/8,500 bytes；原 Overview 大 chunk 警告保留 |
| 实际 API/浏览器 | 根目录 `node scripts/quality/browser-check.mjs <新证据目录> http://127.0.0.1:18174` | Chrome、真实 Java API，两报告；375/768/1280 × 6 状态，共 18 个组合 |
| 共享样式 | 根目录 `node scripts/quality/shared-browser-check.mjs <新证据目录> http://127.0.0.1:18174` | 五页 × 三屏宽，共 15 个组合 |

全部 33 个实际 Chrome 组合均为 0 axe 违规、0 页面横向溢出、0 pageerror。截图仅证明这些已列状态；没有声称 Lighthouse 100、真实设备性能或所有生产情形均通过。截图在采集时将动画推进到静止终态；不把静止截图当作运动性能测量。PNG 签名/尺寸检查见 [capture-integrity.json](capture-integrity.json)，页面/状态与截图索引分别见 [质量页](browser-verified/checks.json)、[五页回归](shared-verified/checks.json)。

独立 AI [代码/完整性终审](../../../.omo/evidence/quality-center-final-integrity.md)与[视觉/设计系统终审](../../../.omo/evidence/quality-center-final-visual.md)均为 APPROVE，各自直接检查了全部 33 张最终截图。它们是代码和 UI 审阅，不属于模型回答的真人审核。实际 Java 浏览器预览使用 demo profile；角色拒绝/允许另由 secured filter chain 测试证明，不能合称为已验证生产登录。审阅保留的限制包括：没有 CSS 修改前精确截图/字节副本、Chrome 单浏览器范围、自动 axe 不替代完整人工无障碍审核、gzip 预算仅剩 17 bytes。

## 失败与修复保留

- 首轮构建预算失败：CSS 44,348 / gzip 9,262。通过复用现有原语、合并相同声明和共享压缩输出降到原预算内，未调高门禁。
- 实际 axe 首轮发现 `dl > div > p` 非法结构，已把说明放入对应 `dd`；后续发现默认按钮悬停对比度 4.48，使用 DESIGN 中的深色 hover 修正。新增回归先失败后通过。
- 全量 Web 的旧 characterization fixture 未声明新报告接口，原 E2E 的“通过”文字定位又匹配到了新说明文案。前者显式提供 NOT_CONFIGURED，后者使用 exact 匹配；保留原行为断言，没有删除测试。
- 旧 `node scripts/benchmark/verify-quality-inputs.mjs` 现在在最后的整工作区不变断言失败，原因是本轮已授权源码变化。旧门禁原样保留；新的范围校验不是把旧失败写成通过。
- 隔离预览第一次从错误 cwd 启动 Java，知识库相对路径无法加载；改为 API 服务目录启动同一新 JAR 后成功。自定义 Gradle init 脚本第一次类路径引用失败，修正 task-name 配置后成功。未因此改变业务错误策略。
- 浏览器验收脚本经历了动画等待/axe 显式 context 和构建配置串扰问题。最终使用有上限的动作、终态截图，以及独立的 demo 构建目录；不把之前不完整截图计入最终 33 项。相关失败日志保留在本轮 `.omo/evidence/quality-center-2026-09-10/`。

## 本地查看与下次启动

当前用于交付检查的隔离预览：`http://127.0.0.1:18174/` → 质量评估，真实 Java API 为 `127.0.0.1:18081`。该实例是 demo profile、内存 H2，使用已有冻结报告，未启动新的模型服务；不要把其中示例工单当成本轮模型调用。原有 live 工作台/持久化数据库未迁移或覆盖。原服务要获得新后端端点，需在常规重启时使用当前源码和下列配置；混用新前端与旧 Java 时，新报告入口会明确失败。

在停止既有工作台后，从根目录使用现有启动器（启动器仍检查端口/数据锁）附加：

```bash
QUALITY_LIVE_REPORT_PATH="$PWD/docs/verification/product-quality-center-2026-09-10/reports/live.json" \
QUALITY_LIVE_REPORT_SHA256=170dffe55cc8e5f7e3ac4dec6a49fa123ea43c8bea8bccdbceec2c0aeb24d2a9 \
QUALITY_BUSINESS_REPORT_PATH="$PWD/docs/verification/product-quality-center-2026-09-10/reports/business.json" \
QUALITY_BUSINESS_REPORT_SHA256=417ec4a2020cca23a8642c8e2f3f14418a72a71228af9d5132673f36571f180b \
AI_MODE=live ./scripts/dev-workspace.sh
```

`AI_MODE=live` 沿用既有凭据/授权，不是质量页自身的开关。没有真实调用需求时可用 mock；质量报告仍是冻结真实实验。报告路径和 digest 必须成对配置；生成新的展示版本用 `node scripts/quality/export-reports.mjs <全新目录>`，已有目录包括不完整导出均拒绝覆盖。只有成功生成的 manifest 才是完成标记，不手工从部分文件拼接摘要来发布。

## 简历与后续

可以写：“实现跨 Java/React 的 AI 质量证据中心，基于冻结原始记录重算模型正常产出、证据不足与超时；通过摘要校验、逐例失败追溯和独立不可用状态防止误报；完成真实 API 浏览器验证及自动回归。”数字若引用 96 次业务分析，必须注明那是前一轮实测，本轮是接入与再核验。

不能写：回答准确率提高、超时减少、节省客服工时、真实客户问题解决率、生产 SLO 达标、已完成真人审核或生产上线。

下一切片是独立实验运行器（run ID/端口/数据库/预算/停止条件/完整重启读回）与人工确认后的 development 测量。此运行器尚未在本轮实现；holdout 没有用于调参。项目真实身份接入、生产恢复/发布和费用核算仍是后续独立工作。
