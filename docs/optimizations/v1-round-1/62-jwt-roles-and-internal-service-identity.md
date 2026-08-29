# 第 62 轮：实施 JWT 角色与内部服务身份

## 问题与风险

Java 原先对全部请求 `permitAll`，审核 actor 固定为演示用户；任何浏览器都能读写业务 API。Java 调用 Python 时也没有服务身份，直接请求 `/analyze` 会进入检索和模型工作流。

## 修改层与流程

- `demo`：业务 API 保持匿名，审核只使用明确的 `UNAUTHENTICATED_DEMO` actor；非 health actuator 不开放。
- `test`：使用显式合成 JWT decoder，但执行与 `local`/`pilot` 相同的 endpoint policy。
- `local`/`pilot`：启动前要求非空 `SUPPORT_COPILOT_INTERNAL_SERVICE_TOKEN`、`SUPPORT_COPILOT_JWT_ISSUER_URI` 和 `SUPPORT_COPILOT_JWT_AUDIENCE`；`SUPPORT_COPILOT_JWT_JWK_SET_URI` 可选，只指定直接 key-set 位置，不会关闭 issuer/audience claim 校验。缺失必需变量时在 datasource 创建前失败。
- JWT roles：agent/reviewer/admin 可访问 tickets、knowledge search 和 metrics；reviews 只允许 reviewer/admin；非 health actuator 只允许 admin。
- 审核 actor：安全 profile 只从 `JwtAuthenticationToken` subject 读取，不读取请求 header/body。
- Java-to-Python：Java 每次 `/analyze` 都发送 `X-Internal-Service-Token` 和原 `X-Trace-Id`；Python 使用 `secrets.compare_digest`，在 workflow/provider 前拒绝缺失或错误 token。
- Python 启动：FastAPI 应用构造要求内部 token 非空；缺失或空值时进程在开放 `/health` 前失败，错误只包含配置变量名，不包含凭据。
- 审核 subject：安全 profile 在持久化前拒绝缺失、空串或纯空白 JWT subject，返回稳定 403 且不回退到 demo actor。

401/403 和 Python 401 都返回稳定且不含凭据的 JSON。Python `/health` 与 Java `/actuator/health` 保持公开；Java health 只返回 `status`。

## 验证方式

```bash
cd services/support-copilot-api
./gradlew test --tests '*PilotSecurityContractTests' --tests '*AiServiceClientTests' --tests '*RuntimeProfileIntegrationTests' --no-daemon
./gradlew test --no-daemon

cd ../support-copilot-ai
.venv/bin/pytest -q tests/test_internal_auth.py
.venv/bin/pytest -q

cd ../..
./scripts/run-local-smoke.sh
```

自动化与手动证据记录在 `.omo/evidence/task-4-enterprise-minimum-pilot.md`。验证观察 HTTP status/body、持久化 actor、真实 outbound header、workflow side-effect counter、启动失败阶段和清理结果，不只依赖 mock bean 调用或成功输出。

## 当前限制

当前只证明本地 H2 `test` profile 的 pilot-equivalent policy 和合成签名 JWT。React 登录/token adapter 属于 Task 11；真实 OIDC issuer、MySQL、Compose 和 pilot parity 属于 Task 15。内部 token 是单机 pilot 的共享服务凭据，不是用户身份、mTLS 或生产密钥管理方案。
