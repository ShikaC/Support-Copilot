# GitHub CLI 公开问题 RAG 试标注集

2026-09-10：已采集并校验首批公开资料，尚未评测 RAG 质量。用户选择“没有内部数据，先用公开产品文档与真实公开问题”。本批定位为小范围技术支持试标注，不代表真实企业客服分布。

| 项目 | 当前事实 |
| --- | --- |
| 产品 | GitHub CLI |
| 候选来源 | cli/cli GitHub Issues，只读公开 API |
| 候选 / 选入 | 48 / 20 个来源问题 |
| 选择方式 | 标题含 how 的已关闭 issue，按创建时间降序取最多 50；在返回的 48 条中目的性筛选，非随机样本 |
| 输入类型 | PUBLIC_ISSUE_ADAPTED：基于真实 issue 的 AI 归纳，非逐字原文，非凭空合成 |
| 文档版本 | gh 2.100.0，2026-09-03 release |
| 文档快照 | 107 份官方内置帮助文本；含总览和交叉内容，不能等同 107 份独立知识或最终 chunks |
| 数据划分 | 全部 pilot-development；没有独立测试集 |
| 人工审核 / 模型调用 | 0 / 0 |
| 质量分数 | 未评测，accuracy=null |

## 文件导航

- [cases.json](cases.json)：20 个归纳问题、来源时间与摘要、风险、候选资料和空白人工标签。
- [REVIEW.md](REVIEW.md)：逐条人工试标注表，候选资料可点击。
- [ANNOTATION_DRAFTS.md](ANNOTATION_DRAFTS.md)：首批 5 条 AI 预标注、原文行号、候选回复和判定条件；全部待人工审核。结构化建议见 [annotation-drafts.json](annotation-drafts.json)，行号与文件摘要校验见 [annotation-evidence.json](annotation-evidence.json)。
- [selection.json](selection.json)：48 条来源的纳入/排除理由，记录重复问题和有答案混入的排除项。
- [corpus/manifest.json](corpus/manifest.json)：107 份文本的采集命令、来源 URL、版本、SHA-256；[LICENSE](corpus/LICENSE) 保留官方文档 MIT 声明。
- [SOURCE_REVIEW.md](SOURCE_REVIEW.md)：独立 Agent 来源与归纳核查；不计入人工标注。
- [provenance.json](provenance.json)：项目 HEAD、文档上游版本、本地 gh 二进制摘要、候选与案例指纹。
- [verification.log](verification.log) 与 [review-gate.log](review-gate.log)：文件完整性通过与未审核阻断证据。

## 数据事实与边界

原始用户帖子可能夹带个人账号、图片、路径、后续自解和方案建议。本批不复制完整 issue 正文或评论，只保存短标题、来源链接、原正文 SHA-256 及明确标记的归纳。外部来源仍可能被编辑，SHA 标识本次所见版本，不是最初发布版本的证明。原问题作者可通过来源链接核查，不收集额外用户资料。

归纳可能遗漏条件或改变提问方式，所以 fidelity_review 仍为 NOT_REVIEWED。独立 Agent 复核发现 #3373 原文已经给出 owner 用法，随后将其排除并替换为 #375 的无浏览器认证问题；这次调整发生在任何模型评测之前，保留筛选记录。

所有 annotation_proposal 都是 NOT_GOLD；candidate_document_ids 只是查阅起点，不是保证有效的证据。可答性、必要要点和禁止承诺均待人工判断，不能由程序把缺失答案默认为正确拒答。

本批保留旧版本用户问题，目标是“依据 2.100.0 文档处理历史需求”，不是历史时间回放。未来模型输入必须明确当前文档版本；对明确询问旧版本的案例，应区分当前建议与无法核实的历史行为。未经审核不能直接把当前命令当作旧版本正确答案。

这是英文技术支持问题，不能证明中文账单、隐私或企业业务政策质量。选择已关闭且标题含 how 的 issue 有明显覆盖偏差；也无法证明公开问题从未进入模型预训练。未来测试集必须另取独立问题并标注这些限制。

## 官方文档采集方式

本机直接访问 cli.github.com 遇到 DNS 失败，网站源码仓库 API 也未取得。因此使用已安装产品的官方帮助入口 `gh help <command>` 冻结资料，而不声称已下载官网网页。

采集覆盖官方 reference 中 auth、pr、issue、repo、release、extension、project、api、completion 的全部列出命令，以及 environment、formatting、reference。这保证保留整个命令族资料，而非只挑能命中样题的段落。帮助文本包含总览、通用 flags 和相互重复部分；进入检索实验前还需设计分块、处理重复并标注证据，不把文件数当知识规模。

固定上游 release commit：`45437bc7eeeb3359bbfddd1742f79de7652fd3e2`。本地 gh 输出版本与该 release 相符，并记录二进制 SHA；本轮未独立重建或验证官方二进制签名。官方网页 URL 作为对应阅读入口，本地正文来自版本固定的内置帮助。

首轮使用 `<command> --help` 时，`gh extension exec --help` 把 --help 视作扩展名并退出 1，未找到扩展。改用统一 `gh help <command>` 后完整采集 107 份；没有执行登录、创建、发布等业务命令。失败轮不完整文件移至 `.local/public-rag-pilot-2026-09-10/failed-capture`，未作为最终 corpus。

## 可复现检查

从项目根目录运行：

```bash
node docs/verification/public-rag-pilot-2026-09-10/verify.mjs
node docs/verification/public-rag-pilot-2026-09-10/verify.mjs --require-reviewed
```

第一条 exit 0，验证案例来源、版本、候选文档存在、正文 hash 与未评测标记。第二条 exit 2，明确拒绝把本批未审核开发材料视为已审核质量证据；这是本采集快照的阻断检查，不是通用人工评估器。

如需再次采集官方帮助，使用安装有相同版本 gh 的环境，并指定不存在的新目录（不覆盖本次证据）：

```bash
node docs/verification/public-rag-pilot-2026-09-10/capture-corpus.mjs /tmp/support-copilot-gh-help-new-snapshot
```

脚本只采集帮助文本与 manifest；重新发布资料时必须一并携带对应官方 LICENSE。归纳源选取见 selection.json，正文不随本报告再分发；用 issue API 重新拉取时需重新核对 body SHA 与改写忠实度。

## 下一步与验收条件

先从 5 个案例试标注：#375 无浏览器认证、#1331 PR 正文文件、#5100 布尔参数关闭、#9457 中断下载、#5147 扩展升级失败。包含可能可答和需要补充信息的场景，不预填可答性。

作者逐条查看原问题及候选帮助，确认归纳忠实度、适用版本、可答/需补问/无证据/需授权或升级，记录准确原文位置、回答要点和禁止承诺。首批标准达成后，再完成其余问题并冻结标注版本。Agent 审查不能代填真人审核。

之后才进入独立的分块/检索小切片：保存文档位置到 chunk 的映射，先测简单词法检索与当前向量检索的差异，再评估生成与引用支持。当前现有 live runner 要求业务分类、知识权限和 artifact 契约，本批未直接适配，不能把当前 20 例塞入旧 10-chunk 知识库运行后称作公开 RAG 评测。

线上工作台、当前 22 例 live 报告、原有知识库及索引均保持原状。后续真实测试集要使用未用于本次修复的新问题，本批不升级成“未见测试集”。

## Git 与简历证据

项目路径 `/Users/shika/Documents/Support-Copilot`；基础 HEAD `4df3bf44907c34318132496929bad4a3974ad88b`，master，dirty。本轮新增采集资料、校验脚本、记录及状态链接，未提交/推送/部署，未调用模型或写入外部平台。完整性验证只覆盖本批资料，不替代应用测试、真人事实审核或 RAG 成绩。

可陈述：整理了有可追溯来源、固定版本官方文档和明确防泄漏规则的公开技术支持试标注材料。不能陈述：完成真实用户 RAG 准确率评测、人工审核通过、独立测试通过或真实企业效果提升。
