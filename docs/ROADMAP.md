# Support Copilot 后续三个里程碑

更新时间：2026-09-10。已完成的工单工作台与运行加固归入 [当前状态](STATUS.md)，具体证据见 [验收记录](enterprise-workspace/VERIFICATION.md)。本文仅记录未来工作，不把计划写成当前能力。

## M1 固定真实 RAG 质量基线

状态：partial。已完成来源绑定回复规则、证据充分性契约、语言与违规模式门禁、真实候选记录和安全故障诊断；详见 [当前状态](STATUS.md)。最终冻结评估仍有连接/读取超时，人工审核未完成，不进入 OpenRAG 比较或发布结论。

目标：query前180字符截断已经[修复并完成离线回归](verification/query-context-fix-2026-09-10/README.md)，下一步在diff审阅后冻结新的development比较方案、源码与预算，测量真实检索、生成、耗时和失败。旧13题已见过输出，只可作为development复测，不能冒充盲测或删除失败；holdout在比较方案确定前不用于调参。输入参考与模型输出仍需真人审核，才能发布语义评分。没有供应端日志时只报告本地超时类别，不猜远端原因。

影响范围：评测数据/脚本与必要的 Python 检索观察；具体离线验收命令和下一实验预算以新报告为准。真实测量后分别报告有证据完成请求、正确补问、知识库外安全行为、正常模型产出、超时/降级和保存结果；模型调用成功不能替代语义评分。如需修改重试预算，联合检查 Java/Python 截止时间并记录尝试次数、延迟与成本。保留全部计划、失败和未执行行，绑定 dataset/corpus/artifact/model/protocol/schema/config/Git/dirty 摘要；人工未完成时质量结论保持 partial，不能重跑择优或用 AI 代填真人标签。

## M2 接通企业身份与协作目录

状态：计划中。目标是把当前 JWT 服务端权限与前端 token adapter 接到一个明确选定的真实企业身份系统，完成登录、退出、令牌续期与组织成员选择，取代负责人自由文本。

依赖确认身份提供方、成员与角色映射、受保护范围，以及外部配置授权。影响 React auth/负责人交互、Java trusted actor 与访问控制，不改 AI 对外响应契约。验收包括真实登录闭环、权限拒绝、失效/续期、成员停用和前后端身份一致；保留现有 401/403 回归并补供应方集成证据。未选择供应方前不凭名称建立 Adapter，不把 test-only issuer 当作真实 SSO。

## M3 冻结并验收单租户 Pilot 发布物

状态：partial。目标是在同一不可变源码与镜像集合上完成部署、健康、认证、核心流程、数据库重启、fresh-volume 恢复和回滚。当前文件 H2 恢复及 MySQL Testcontainers 已验证；完整 Compose 运维与严格镜像发布安全结论仍独立保留。

依赖用户审核当前 diff 并确定提交边界、可用磁盘、明确资源所有权和通过的镜像安全扫描。影响 `infra/`、Pilot 备份恢复脚本和发布证据；验证使用 `scripts/verify-pilot-operations.sh`、`scripts/verify-mysql-persistence.sh` 与既有扫描门禁。验收必须逐项记录失败与成功，不能把本地文件 H2 快照恢复替代 MySQL fresh-volume 或跨版本回滚，也不能把测试覆盖率当作容量/高可用证据。

OpenRAG 仍是待确认输入。只有项目、版本、许可证、职责与比较基线明确，并在 M1 同一 corpus/评估集下证明收益后，才考虑引入。当前没有 Redis、消息队列、Kubernetes 或多租户的已量化容量需求。
