# ADR-0002：语料、索引与 Java 发布版本成组切换

日期：2026-09-19。状态：设计契约已记录，成组切换尚未实现。本 ADR 不是可直接执行的运维手册。

结论：先解决候选发布身份，再实现单实例、维护窗口内的显式切换。允许暂时不可用，但不能用旧语料解释新向量，也不能把数据库 publish 成功当作整个系统已切换。现阶段不新增仅接收 artifactId 的 activate/rollback HTTP 接口。

当前事实与验证统一见 [STATUS](../STATUS.md) 和 [边界核对报告](../verification/paired-switch-contract-2026-09-19/README.md)。下文“要求”均为后续实现的验收条件，不表示已有功能。

## 1. 为什么现有接口不能直接拼成一键切换

| 已有机制 | 实际保护 | 尚不覆盖 |
| --- | --- | --- |
| Python `KnowledgeRetriever.reload_index` | 校验新语料和 active artifact，成功后替换单个 `RetrievalState`；失败保留旧内存 | 磁盘文件恢复、多进程同步、Java 数据库 |
| Python `EmbeddingArtifactStore` | 核对 release、corpus、provider/model 与逐行内容，单独原子写 active.json | corpus 与 pointer 的联合事务 |
| Java `KnowledgeReleaseService.publish/rollback` | 在数据库事务中修改 release、active 与审计 | Python 准备状态、语料文件、索引与跨服务提交 |
| Java `KnowledgeCorpusStore` / `KnowledgeService.search` | 每次加载配置路径，核对数据库当前 release 与 corpus | 维护窗口、固定版本的文件选择 |
| Java `KnowledgeBaselineInitializer` | 启动时拒绝数据库 release 与磁盘 corpus 不一致 | 启动失败后的自动修复 |

Python 的 reload 锁只串行化本进程 reload；Java `expectedVersion` 是目标 release 行的乐观锁版本，不是“调用者预期的当前 active”。Java 的 active 行锁能串行化数据库写入，但不能阻止等待中的另一个发布覆盖刚生效的版本。未来切换必须额外核对预期 active 身份。

## 2. 先解决身份，不能在建库后改标签

现有 Doc2Dial 生成器把 `release_version` 固定为 1，releaseId 只随切片参数变化。Java V4 migration 对 `release_version` 设置全局唯一约束。因此：

- 版本 1 已存在时，另一份候选即使 releaseId 不同，也不能创建 Java release。
- 同样参数、不同源文档也可能得到相同 releaseId。参数标签不是发布身份。
- artifact manifest、artifactId 都绑定 releaseId/version。不得在索引建好后只改 corpus 的两个字段，也不得修改成功候选的既有文件来伪装新身份。
- corpusChecksum 只摘要 chunks；它不能单独代表发布身份。文件摘要另行绑定完整 bytes。

下一实现切片要求：任务化语料生成支持显式成对的 releaseId/releaseVersion，校验与 Java 对齐（ID 最长 64、既有字符集；version 为正的 Java int）。未传入时保留现有冻结 benchmark 输出；这条兼容路径仍只承诺生成候选，不承诺可发布。

操作者选定新身份 → 生成新候选 → 用候选真实 checksum 创建 Java DRAFT，利用已有数据库唯一约束接纳或拒绝 → 再以来源任务 ID 构建索引。身份冲突必须在本流程的 Embedding 调用前发现；不得自动做不受锁保护的 max(version)+1。候选生成时的局部参数校验不声称预留了 Java 版本。Java 接入尚未实现前，Python 独立 rebuild 仍不具有这个跨服务预检保证。

例如已有 releaseVersion=1，选择新 ID 和 version=2；如果 version=2 已被其他人占用，保留失败证据并选择新的身份重新生成候选，不覆盖成功结果。DRAFT 创建后构建失败则保留 DRAFT 和失败任务，不发布。

## 3. 成组选择与持久化边界（计划中）

切换输入必须绑定：成功的 corpusBuildTaskId、成功的 rebuildTaskId、artifactId、releaseId/version/corpusChecksum，以及调用者预期的当前 release 和 artifact 身份。服务从配置的根目录解析任务和文件，不接受调用方的任意路径、provider 地址或密钥。

目标组包含不可变 corpus、匹配 artifact、来源任务及必要 provenance。验证必须读取被固定的 bytes，核对任务成功状态、文件摘要、语义摘要、artifact 完整性、逐行内容、provider/model/input format/dimension 和授权 scopes；不创建 provider，不隐式建库。B1 的 chunking.json/manifest.json 不是 `KnowledgeProvenance(schema_version=2)`；配置要求 provenance 时必须准备兼容且匹配的证明，不能靠清空配置绕过。该桥接仍待实现。

首次实现只支持一个受控操作进程、一套 Java/Python 实例。操作记录保存 operationId、前后组身份、阶段和校验摘要，不含正文或凭据；写入先 fsync 文件，再原子 rename，再 fsync 目录。记录必须先于任何激活写入持久化。Java 数据库 active 是发布事实；操作记录是恢复意图，不能拿它冒充数据库已提交。禁止混用独立旧脚本、reload 和 publish 写入；维护入口必须实际隔离这些写入，单靠操作文件锁不足以约束旧 HTTP 接口。

运行时、启动和恢复必须读取同一组选择。不能让 reload 使用新候选路径，而重启又回到旧 `KNOWLEDGE_PATH`。复用现有配置路径的首版应在维护窗口中保存/替换完整 corpus、provenance 和 active 指针，并记录每项摘要；它们不是一次文件系统原子写。持久化记录与阻断流量共同处理这个中间状态。

## 4. 正常切换顺序（计划中）

1. **PREPARED**：新候选与 artifact 已完整验证，Java 目标 DRAFT 已创建并按现有审核流程 APPROVED；旧组可重新加载且有不可变恢复副本。以完整元组区分旧组和新组，目标完全等于当前组时只核验，不产生重复发布事件。
2. **MAINTENANCE**：阻止知识搜索、工单分析和并发知识写入；等待在途分析完成，不能只等检索结束。维护状态跨进程重启保持关闭流量。未能排空或不能隔离管理写入时，不进入提交阶段。
3. **COMMITTING**：持久化包含前后组的恢复记录。持有管理互斥边界，重新检查 expected-current；数据库事务内同时检查 active 和目标行版本，执行既有发布/归档/审计语义。不能只在事务外检查 active。
4. **INSTALLING**：在流量仍关闭时安装目标 corpus/provenance 和匹配 active artifact。Python 加载并验证完整新快照；Java 搜索核对数据库与其配置 corpus。失败不放流量，不触发供应方请求。
5. **VERIFIED**：两个服务分别报告并核对 releaseId/version/checksum；Python 还核对实际已加载 artifactId。通过重启演练后，保存完成记录，再开放流量。

选择数据库先提交，是为了在数据库已提交但文件尚未安装时，恢复能根据数据库的明确目标补齐本地组。任何阶段都不声称跨服务原子提交或零停机。普通 readiness=up、active.json 指向新 artifact、单个 reload HTTP 200，都不足以进入 VERIFIED。

上述维护闸门、组记录、事务内 expected-current 保护和实际已加载 artifact 观测目前都不是完整成组功能，必须实现并演练后才能使用此顺序切换工作台。

## 5. 失败、重启与回滚（计划中）

| 中断位置 | 必须保留的行为 | 恢复依据 |
| --- | --- | --- |
| 预检/审核未通过 | 不改变 active、文件或运行快照；失败可追溯 | 保留候选、任务失败与旧组 |
| 维护/排空失败 | 不发布；核对仍为旧组后才解除维护 | 旧组摘要与数据库 active |
| Java 事务失败（含审计失败） | 数据库回滚；尚未替换文件 | 读取数据库确认旧组，不能只看网络错误 |
| publish 响应丢失或进程死亡 | 保持维护；不盲重试 publish | 直接读取数据库 active/目标状态与操作记录；Java 不能启动时需受控离线读取工具 |
| 数据库新、文件旧或仅部分文件新 | Java 可能拒绝启动，Python 可能仍持有旧快照；都不开放业务流量 | 校验不可变目标副本后补齐新组，再启动/验证两端 |
| 数据库旧、文件出现新组 | 不据操作阶段猜“已成功” | 恢复旧组并校验；不擅自发布目标 |
| 数据库是第三个 release | 视为并发/外部写入冲突，停止恢复 | 不覆盖第三方状态，人工核对操作所有权 |
| 目标或旧组副本损坏 | 保持维护并报告真实错误 | 不隐式重新 embedding，不挑目录时间最新的组 |
| 两端已一致，完成记录前死亡 | 恢复时重新校验并完成记录 | 同组恢复幂等，不重复创建发布审计 |

回滚是另一次显式成组操作：选择以前完整的 corpus+artifact+release，执行同样预检、维护、expected-current 检查与验证。Java 用现有 ARCHIVED → PUBLISHED 回滚语义，不能仅恢复 active.json。数据库已提交而安装失败时，优先完成已提交目标；目标无法恢复时保持维护，由操作者显式选择完整旧组回滚。不删除失败操作记录，不把“旧进程尚可用”记成持久化回滚成功。

## 6. 实现顺序和完成门槛

1. **下一切片：发布身份贯穿候选生成与索引。** 保持冻结默认 bytes；显式身份在 status/result/corpus/manifest/artifact 一致；错误 ID、缺一字段、非整数/溢出版本均在生成前拒绝。用合成源验证重复 Java 版本拒绝后没有进入 Embedding。
2. **后续切片：单实例成组切换与恢复。** 实现维护/排空、管理写入互斥、持久化前后组、事务内 expected-current、两端加载观测与离线恢复入口。覆盖上表每个提交边界的进程终止和重启，含发布响应丢失、并发陈旧请求、provenance 不匹配、旧在途请求和完整回滚。测试只用临时数据库与合成 provider。
3. **之后才接 Java/前端入口。** 展示准备、审核、切换、失败与人工恢复状态，不能将 SUCCEEDED 构建展示成已上线。

本轮完成门槛仅为：源码约束可定位、重复版本边界可执行验证、现有 reload 正常/失败路径复核、契约明确区分已有与计划。未选择分布式事务、双版本路由或新数据库；只有确需无停机/多副本时再另立决策。本轮不授权部署、激活真实知识库、模型调用或使用 holdout。
