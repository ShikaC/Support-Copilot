# 五条公开问题：AI 预标注

**状态：5 条 AI 预标注，0 条人工审核，0 次项目模型 API 调用。以下不是已评测模型输出，也不是标准答案。**

## 本轮要确认的标准

可答性分开描述：文档足以支持直接回答；只支持有限说明但不能核实旧版本行为；文档不能解释具体故障，需要补充上下文。合理补问不等于故障已经解决。人工可以修改候选答案和评分要点，不要求与 AI 建议文字相同。

本次先阅读第一条并确认；其余四条作为预备材料，不要求一次审核完。对第一条标准的认可仅记录相应范围，不自动完成来源忠实度、替代证据穷尽性或全部题目的审核。

## gh-public-375：无浏览器认证

[公开问题](https://github.com/cli/cli/issues/375)

原需求归纳：I run GitHub CLI on a remote machine over SSH without a browser. How can I authenticate in this environment?

**建议可答性：** ANSWERABLE_FOR_DOCUMENTED_VERSION

**限制：** 支持无浏览器认证方式，不证明令牌已创建、有效或有权访问目标资源。给出 GitHub.com 条件式示例即可；无需因为未指定 hostname 而完全拒答。

### 候选证据

[gh_auth_login，第 18–20 行](corpus/gh_auth_login.txt#L18)

```text
Alternatively, gh will use the authentication token found in environment variables.
This method is most suitable for "headless" use of gh such as in automation. See
`gh help environment` for more info.
```

[gh_help_environment，第 1–6 行](corpus/gh_help_environment.txt#L1)

```text
`GH_TOKEN`, `GITHUB_TOKEN` (in order of precedence): an authentication token that will be used when
a command targets either `github.com` or a subdomain of `ghe.com`. Setting this avoids being prompted to
authenticate and takes precedence over previously stored credentials.

`GH_ENTERPRISE_TOKEN`, `GITHUB_ENTERPRISE_TOKEN` (in order of precedence): an authentication
token that will be used when a command targets a GitHub Enterprise Server host.
```

[gh_auth_login，第 12–16 行](corpus/gh_auth_login.txt#L12)

```text
Alternatively, use `--with-token` to pass in a personal access token (classic) on standard input.
The minimum required scopes for the token are: `repo`, `read:org`, and `gist`.
Take care when passing a fine-grained personal access token to `--with-token`
as the inherent scoping to certain resources may cause confusing behaviour when interacting with other
resources. Favour setting `GH_TOKEN` for fine-grained personal access token usage.
```

### 候选回复（本会话 AI 拟定，未调用被测系统）

According to the GitHub CLI 2.100.0 help, token environment variables support headless authentication. For commands targeting github.com, supply an appropriate token through GH_TOKEN or GITHUB_TOKEN in the remote process environment; GH_TOKEN takes precedence if both are set. The CLI can use that credential without a local browser login prompt. This describes the frozen current-version documentation, not a verified reproduction of the original 2020 behaviour. Do not include the token value in a support ticket.

### 建议必须满足的条件

- 说明按固定的 GitHub CLI 2.100.0 文档回答，未验证原帖年代的实现。
- 说明可以通过令牌环境变量进行无浏览器认证。
- 若以 github.com 为例，正确识别 GH_TOKEN 或 GITHUB_TOKEN；只有讨论同时设置时才要求说明 GH_TOKEN 优先。
- 不把 SSH 连接到远程机器等同于已完成 GitHub API 身份认证。

### 不合格答案的特征

- 断言没有浏览器就无法使用 gh。
- 把 --web 作为唯一办法。
- 把 SSH 登录服务器当作 GitHub API 的身份凭据。
- 声称已为用户完成登录。
- 要求用户把实际令牌贴到工单或聊天中。

正常路径示例：识别 headless 环境并给出有来源、条件明确的令牌认证方式。

失败路径示例：命中 gh_auth_login，却只让用户执行 gh auth login --web。

**人工结论：待填写。**

## gh-public-1331：从文件读取 PR 正文

[公开问题](https://github.com/cli/cli/issues/1331)

原需求归纳：I am migrating a workflow from hub and need to create a pull request whose description comes from a large generated Markdown file. I can provide the title separately and cannot use commit autofill. How can I provide the body file?

**建议可答性：** ANSWERABLE_FOR_DOCUMENTED_VERSION

**限制：** 仅回答正文输入方式，不要求模型证明仓库权限、远端关系或实际创建成功。

### 候选证据

[gh_pr_create，第 61–61 行](corpus/gh_pr_create.txt#L61)

```text
  -F, --body-file file       Read body text from file (use "-" to read from standard input)
```

[gh_pr_create，第 76–76 行](corpus/gh_pr_create.txt#L76)

```text
  -t, --title string         Title for the pull request
```

[gh_pr_create，第 14–18 行](corpus/gh_pr_create.txt#L14)

```text
A prompt will also ask for the title and the body of the pull request. Use `--title` and
`--body` to skip this, or use `--fill` to autofill these values from git commits.
It's important to notice that if the `--title` and/or `--body` are also provided
alongside `--fill`, the values specified by `--title` and/or `--body` will
take precedence and overwrite any autofilled content.
```

### 候选回复（本会话 AI 拟定，未调用被测系统）

For GitHub CLI 2.100.0, use --body-file (or -F) to read the pull request description from your Markdown file, with --title for the separate title. For example: gh pr create --title "Example title" --body-file description.md. The --fill option instead derives text from commits. This is a current-version command example and has not been executed.

### 建议必须满足的条件

- 给出 --body-file 或 -F 从文件读取正文。
- 若给示例，标题可通过 --title 单独传入；路径与标题仅用占位值。
- 按 2.100.0 文档解释，不声称 2020 年已有该功能。

### 不合格答案的特征

- 声称 --body 参数把文件路径自动解释成文件内容。
- 把 --fill 当作读取用户指定 Markdown 文件的办法。
- 声称已创建或提交 PR。

正常路径示例：保留长文件输入和独立标题两个条件。

失败路径示例：建议 --body description.md 或仅用 --fill，未解释文件内容如何读取。

**人工结论：待填写。**

## gh-public-5100：关闭布尔功能开关

[公开问题](https://github.com/cli/cli/issues/5100)

原需求归纳：The gh repo edit help lists --enable-issues and similar flags. How can I use them to turn a repository feature off rather than on?

**建议可答性：** ANSWERABLE_FOR_DOCUMENTED_VERSION

**限制：** 语法可由文档直接判断；不执行修改仓库命令。

### 候选证据

[gh_repo_edit，第 1–3 行](corpus/gh_repo_edit.txt#L1)

```text
Edit repository settings.

To toggle a setting off, use the `--<flag>=false` syntax.
```

[gh_repo_edit，第 39–39 行](corpus/gh_repo_edit.txt#L39)

```text
      --enable-issues                            Enable issues in the repository
```

[gh_repo_edit，第 65–66 行](corpus/gh_repo_edit.txt#L65)

```text
  # Disable projects
  $ gh repo edit --enable-projects=false
```

### 候选回复（本会话 AI 拟定，未调用被测系统）

In the GitHub CLI 2.100.0 help, boolean settings are turned off with --<flag>=false. For Issues, the syntax is gh repo edit --enable-issues=false. This is an explanation of the documented command, not a change made to your repository.

### 建议必须满足的条件

- 使用 --<flag>=false 的语法，例如 --enable-issues=false。
- 区分解释命令与实际修改仓库；本题没有要求执行设置变更。
- 按固定版本文档说明，不把旧 issue 自带的不清楚之处当作当前功能缺失。

### 不合格答案的特征

- 发明 --no-enable-issues 等未被本次证据支持的 flags。
- 因为 flag 名含 enable 就断言不能关闭。
- 声称已关闭用户仓库的功能。

正常路径示例：从正文说明与具体 flag 合成有据答案。

失败路径示例：推荐 gh repo edit --enable-issues false，忽略文档明确的等号语法。

**人工结论：待填写。**

## gh-public-9457：下载中断是否可以续传

[公开问题](https://github.com/cli/cli/issues/9457)

原需求归纳：A gh release download operation left a partially downloaded file. I am using gh 2.49.2 and cannot find a resume flag in its help. Can I resume the download?

**建议可答性：** PARTIAL_DOCUMENTED_FACTS_HISTORICAL_SUPPORT_UNVERIFIED

**限制：** 这是部分可回答的版本/功能边界问题，不应强行归入“完整成功解答”或“完全无证据”。标准来源集合的缺失不等于产品永不支持。

### 候选证据

[gh_release_download，第 11–18 行](corpus/gh_release_download.txt#L11)

```text
FLAGS
      --allow-escape-sequences   Allow printing terminal escape sequences when writing an asset to standard output
  -A, --archive format           Download the source code archive in the specified format (zip or tar.gz)
      --clobber                  Overwrite existing files of the same name
  -D, --dir directory            The directory to download files into (default ".")
  -O, --output file              The file to write a single asset to (use "-" to write to standard output)
  -p, --pattern stringArray      Download only assets that match a glob pattern
      --skip-existing            Skip downloading when files of the same name exist
```

### 候选回复（本会话 AI 拟定，未调用被测系统）

The available snapshot is the GitHub CLI 2.100.0 help, so it does not establish the behaviour of your reported 2.49.2 version. Its listed options do not document a resume flag. --clobber overwrites an existing file, while --skip-existing skips a file with the same name; neither description is a promise to resume a partial download. Version-specific documentation or implementation evidence is needed to confirm resumability.

### 建议必须满足的条件

- 说明手中证据是 2.100.0 帮助，无法据此确认 2.49.2 的全部行为。
- 说明本次帮助未列出 resume 选项；不把未列出提升成所有版本绝对不支持的结论。
- 若提及 --clobber 或 --skip-existing，分别解释为覆盖同名文件和跳过同名文件，不能称为断点续传。
- 可以提供有限说明并指出需查对应版本实现或官方说明，不能捏造解决步骤。

### 不合格答案的特征

- 发明 --resume 参数。
- 声称 --skip-existing 会接着下载未完成部分。
- 声称 --clobber 会续传。
- 仅因当前帮助未列出就宣称旧版本不可能续传。

正常路径示例：准确说明已知选项和版本证据限制。

失败路径示例：匹配到 download 文档后编出 --resume 或把 skip 误读为续传。

**人工结论：待填写。**

## gh-public-5147：扩展升级失败

[公开问题](https://github.com/cli/cli/issues/5147)

原需求归纳：On Ubuntu 20.04 with gh 2.4.0, an installed extension reports an available upgrade, but gh extensions upgrade --all exits with status 1. Removing and installing it works. How can I resolve the upgrade failure?

**建议可答性：** NEEDS_DIAGNOSTIC_CONTEXT_WITH_PARTIAL_DOCUMENTATION

**限制：** 应允许有据的部分说明加补问成为合理支持行为，但不能把它标成已经找出根因或已解决故障。

### 候选证据

[gh_extension_upgrade，第 1–9 行](corpus/gh_extension_upgrade.txt#L1)

```text
Upgrade installed extensions

USAGE
  gh extension upgrade {<name> | --all} [flags]

FLAGS
  --all       Upgrade all extensions
  --dry-run   Only display upgrades
  --force     Force upgrade extension
```

### 候选回复（本会话 AI 拟定，未调用被测系统）

You have already attempted the upgrade, and exit status 1 alone does not identify its cause. The frozen 2.100.0 help documents upgrading one named extension or all extensions, but it does not explain this failure on 2.4.0. Please provide the complete error output with secrets and personal paths removed, the extension identifier and relevant reproduction conditions. These details are needed before attributing the failure or recommending a force upgrade.

### 建议必须满足的条件

- 承认用户已经执行升级并得到 exit status 1，不能只重复同一个命令就宣称解决。
- 说明当前帮助只提供升级命令及 flags，没有此历史失败的确定根因。
- 需要有针对性地补充脱敏的完整错误输出、扩展标识及复现条件；这些是诊断建议，不是文档已经证实的原因。
- 保留 gh 2.4.0 与当前文档版本差异，不保证升级客户端一定解决。

### 不合格答案的特征

- 断言是网络、权限或本地修改导致，但没有证据。
- 建议 --force 并保证解决或保证不丢失修改。
- 将 exit status 1 当作已知且唯一的故障原因。
- 把现有命令用法正确算成用户升级问题已解决。

正常路径示例：意识到用户已尝试的操作，并根据证据缺口补问。

失败路径示例：原样返回 gh extension upgrade --all 并声称一定能升级。

**人工结论：待填写。**

## 本轮证据边界

已验证案例 ID 存在、引用文件属于固定 corpus、正文 SHA 与 manifest 一致、行号区间有效；实际摘录及摘要见 annotation-evidence.json。此校验不证明语义正确。原 cases.json 中全部20条仍为 NOT_REVIEWED，accuracy=null。未执行登录、修改仓库、创建 PR、下载发布物或升级扩展。

HEAD 为 4df3bf44907c34318132496929bad4a3974ad88b，master，dirty；本轮只新增预标注和记录，不提交/推送/部署。可用于项目材料的是证据与语义标准的设计，不能写成人工标注已完成或真实 RAG 准确率。
