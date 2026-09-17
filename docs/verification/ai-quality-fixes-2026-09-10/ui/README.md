# 知识依据与检索候选显示修复

已实现并验证：`知识依据 N` 仅计数 `usedAsEvidence=true` 的片段。无采用片段时，即使检索返回候选，也显示“没有找到充分证据”及人工复核说明。候选继续保留并可展开，折叠状态下也明确标出“未作为回复依据”。不再把未采用的候选误称为“未进入上下文”。

该切片只修改 EvidencePanel、AnalysisColumn，新增同目录 EvidencePanel.rendered.test.tsx。沿用 DESIGN.md 中现有样式、Ant Tabs、按钮与折叠状态，不修改知识、引用、模型、人工审核或 API 契约。

## 证据范围

- HEAD：`4df3bf44907c34318132496929bad4a3974ad88b`，工作树有大量先前及并行未提交改动。本次证据针对当前未提交工作树，不能当作该干净 SHA 的验证。组件和产物摘要见 `source-hashes.txt`。
- `npm test -- src/features/analysis/EvidencePanel.rendered.test.tsx`：退出 0，3 个渲染测试通过，覆盖零候选、仅未采用候选、混合采用状态及折叠切换。见 `unit.log`。
- `npm test`：退出 0，88 passed、3 skipped（原有 live API 集成测试开关），23 个测试文件通过、1 个跳过。见 `unit-full.log`。
- `npm run build`：退出 0，TypeScript 和 Vite 构建通过。保留既有大于 500 kB 的 Overview chunk 提示，本次没有全站性能结论。见 `build.log`。
- `npx oxlint src/features/analysis/EvidencePanel.tsx src/features/analysis/AnalysisColumn.tsx src/features/analysis/EvidencePanel.rendered.test.tsx`：退出 0。见 `lint.log`。
- `node docs/verification/ai-quality-fixes-2026-09-10/ui/capture.mjs`：退出 0，真实 Chromium 渲染当前生产构建，375、768、1280 三个宽度乘以三种状态共 9 个场景；横向溢出均 0、浏览器 pageerror 均 0。见 `browser-results.json`、9 张完整页面截图与 6 张展开中/完成截图。
- `interaction-diff.json` 为 375 宽度既有折叠动画中间帧与完成帧的比较，不是设计相似度评分或性能指标。

原 18173 端口连接被拒绝，独立预览使用 18174。浏览器仅拦截 synthetic API GET 响应，任何写请求都会失败；未使用真实客户数据，未触发真实模型、后台分析或审核写入。此证据证明前端消费既有契约的状态显示，不能证明 Java/Python 链路或 live AI 质量。

独立 visual-qa 双审核结论在 `review.md` 中记录。未提交或推送。简历可以描述“实现并验证采用证据与检索候选的区分及无证据人工复核提示”，不能从本次截图推出真实客服成效或生产上线。

清理记录：截图和双审核完成后，已关闭本任务独立创建的 18174 preview 进程。没有关闭主线程恢复的 18173 工作台。
