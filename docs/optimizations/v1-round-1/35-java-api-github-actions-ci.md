# 优化 35：使用 GitHub Actions 自动验证 Java 业务 API

## 原来的问题

第 34 轮只自动验证 Python AI 服务：

```text
Python CI 通过
        ↓
只能证明 Python 层通过
        ↓
Java 仍可能无法编译或业务测试失败
```

Support Copilot 的工单状态、分析持久化、版本冲突和 HTTP 业务接口主要由 Java 服务负责。缺少 Java CI 时，GitHub 无法自动发现这一层的回归。

## 本次如何修改

新增工作流：

```text
.github/workflows/java-api-ci.yml
```

它会在每次 `push` 和 Pull Request 时执行：

```text
下载仓库代码
-> 准备 Java 21
-> 验证 Gradle Wrapper 并恢复 Gradle 缓存
-> 执行 ./gradlew test --no-daemon
```

任意步骤失败，整个 `Java API CI` 任务都会失败。

## 为什么固定 Java 21

Java 项目的 `build.gradle.kts` 已经声明：

```kotlin
java {
    toolchain {
        languageVersion = JavaLanguageVersion.of(21)
    }
}
```

CI 使用 Eclipse Temurin Java 21，使远程环境与项目声明一致。准备 JDK 的官方 `actions/setup-java` 固定到已经核对的完整提交 SHA。

## 为什么使用 Gradle Wrapper

项目通过 `gradle-wrapper.properties` 固定 Gradle 9.5.1。CI 执行：

```bash
./gradlew test --no-daemon
```

而不是使用临时电脑中碰巧存在的 Gradle，从而避免不同 Gradle 版本带来的构建差异。

`--no-daemon` 表示构建使用的临时 Gradle 进程会在任务结束时停止，适合一次性的 CI 环境。

## Wrapper 验证和依赖缓存

工作流使用官方 `gradle/actions/setup-gradle`，它负责：

- 验证仓库中的 `gradle-wrapper.jar` 是否匹配 Gradle 官方发布校验值。
- 缓存 Gradle Wrapper、下载依赖和可复用构建状态。

如果 Wrapper JAR 来源未知，CI 会在执行它之前失败。缓存用于减少重复下载，但不会跳过 Java 编译和测试。

工作流中的第三方 Action 都固定为完整 Git 提交 SHA，并用注释记录对应发布版本。

## 为什么不启动 Python 或 MySQL

Java 测试使用 Spring 测试环境、Mockito mock 和内存 H2：

- `TicketAnalysisConflictApiTests` 用模拟 `AnalysisService` 检查结构化 `409`。
- 持久化和取消负责人测试使用 `jdbc:h2:mem:` 数据库。

因此 Java CI 能独立验证 Java 业务层，不需要提前启动 Python、React 或 MySQL。

## 安全与资源边界

工作流只拥有：

```yaml
permissions:
  contents: read
```

它只能读取仓库，不能修改代码或创建发布。任务同时设置 15 分钟超时，异常卡住时会被 GitHub 取消。

## 相对 V1 的改进

优化前：

```text
Java 测试依赖开发者手动运行
Python CI 绿色容易被误认为整个后端都正常
Gradle Wrapper 二进制没有远程自动校验
```

优化后：

```text
每次推送和 Pull Request 自动验证 Java 层
Java 与 Python 拥有各自独立的 CI 结果
Wrapper 来源、Java 版本、编译和业务测试都进入验收链路
```

## 自动化验证

- `actionlint v1.7.12`：Java 工作流语法和 Actions 结构检查通过。
- Java：OpenJDK 21.0.2。
- Gradle：通过 Wrapper 下载并使用 9.5.1。
- 本地干净构建：执行 `clean`、主代码编译、测试编译和测试任务。
- Java 测试：13 条执行，0 失败、0 错误、0 跳过。
- Gradle 结果：`BUILD SUCCESSFUL`。
- `git diff --check`：通过。

第一次普通本地验证显示 `test UP-TO-DATE`，说明它复用了仓库原有构建产物，不能作为真实执行证据。随后运行 `clean test --no-daemon` 清除构建产物并重新执行全部测试，上述 13 条结果来自第二次真实执行。

本地验证不能替代 GitHub 托管环境的运行结果。提交推送后，还需要确认 GitHub Linux 环境中的第一次 CI 状态。

## 涉及文件

- `.github/workflows/java-api-ci.yml`
- `README.md`
- `docs/optimizations/ROADMAP.md`
- `docs/optimizations/v1-round-1/README.md`
- `docs/optimizations/v1-round-1/34-python-ai-github-actions-ci.md`
- `docs/optimizations/v1-round-1/35-java-api-github-actions-ci.md`

## 当前边界

- React 前端已在后续第 36 轮接入独立 CI。
- 还没有把 `Java API CI`、`Python AI CI` 和 `React Web CI` 配置为 `master` 合并前的必需检查。
- 当前工作流不上传测试报告 artifact 或覆盖率报告。
- Java 测试仍使用内存 H2，不能替代未来 MySQL 集成测试。
