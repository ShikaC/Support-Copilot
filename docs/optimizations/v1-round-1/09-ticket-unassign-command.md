# 优化 09：取消负责人使用明确命令和版本保护

## V1 的问题

原来的页面通过通用 PATCH 修改负责人：

```http
PATCH /api/tickets/{id}
```

```json
{"assigneeName": "演示管理员"}
```

这个接口不能清楚表达“取消负责人”这个业务动作，也没有要求前端带上它看到的工单版本。旧页面可能在新页面已经更新工单后，继续提交修改。

## 本轮修改

### 1. 增加明确的业务命令

```http
POST /api/tickets/{id}/unassign
```

请求体携带前端读取到的版本：

```json
{"expectedVersion": 3}
```

Controller 只接收命令，业务规则仍由 `TicketService` 处理。

### 2. 返回工单版本

`TicketResponse` 增加 `version`。React 请求真实工单时，可以把这个数字交给 Java，表示：

```text
“我是在看到第 3 版工单时点击取消的。”
```

### 3. 在事务内执行检查和修改

`TicketService.unassign()` 的顺序是：

```text
查询 Ticket
    ↓
比较 expectedVersion 和数据库 version
    ↓
已无负责人：直接返回，允许安全重试
    ↓
已关闭或已解决：返回 409
    ↓
清空负责人并保存
    ↓
flush，尽早发现并发版本冲突
    ↓
返回最新 Ticket
```

### 4. React 区分真实工单和演示工单

- 真实 Java 工单：必须等待 `unassign` 接口成功后再更新页面。
- 没有 `version` 的本地演示工单：只在本地演示，不声称已经保存到数据库。
- 真实接口返回错误：保留原负责人并提示错误，不把失败伪装成成功。

领取负责人也同步修正了同样的失败处理问题。

### 5. 请求期间锁定负责人操作

React 在领取、重新分配或取消负责人请求进行期间，会让对应按钮显示 loading 并禁用。这样快速连续点击不会并发提交同一个 `expectedVersion`，也不会出现一个请求成功、另一个请求再返回 409 的混乱提示。

## 相对 V1 的改进

```text
V1
页面直接 PATCH 负责人
请求失败也可能先修改页面
无法判断操作基于哪个工单版本

现在
明确 POST /unassign 命令
带 expectedVersion 做乐观并发保护
真实结果以后端响应为准
重复取消不会重复修改数据库
终态工单返回结构化 409
```

## 对应代码

- [TicketController.java](/Users/shika/Documents/Support-Copilot/services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketController.java:62)：取消负责人 HTTP 入口。
- [TicketService.java](/Users/shika/Documents/Support-Copilot/services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketService.java:84)：版本、终态、幂等和事务逻辑。
- [TicketDtos.java](/Users/shika/Documents/Support-Copilot/services/support-copilot-api/src/main/java/com/cyagent/supportcopilot/ticket/TicketDtos.java:35)：请求 DTO 和返回的 `version`。
- [api.ts](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/services/api.ts:88)：React 调用命令接口。
- [App.tsx](/Users/shika/Documents/Support-Copilot/apps/support-copilot-web/src/App.tsx:1328)：真实/演示工单的负责人取消处理。

## 测试

- `TicketUnassignServiceTests` 验证成功、重复请求、旧版本和终态冲突。
- `TicketAnalysisConflictApiTests` 验证 `/unassign` 路由可以接收版本并返回最新 Ticket。
- Java `./gradlew test` 通过。
- React `npm run build` 和 `npm run lint` 通过。
- 移动端 `390×844` 和桌面端截图检查通过，中文按钮、工单标题、负责人字段和客户问题没有重叠或裁切。

## 尚未完成

这不是完整的生产权限和审计实现：

- 当前 `SecurityConfig` 仍是 `permitAll()`，任何请求都可访问接口。
- `expectedVersion` 解决的是并发覆盖问题，不等于权限校验。
- 当前 `TicketEventResponse` 仍是临时响应数据，不是持久化审计事件。
- 真正的审计需要登录身份、操作原因、服务器时间、操作前后状态，并和 Ticket 更新放在同一事务中。
