# 公开问题真实模型实验：逐题结果

本报告由冻结的真实 API 调用结果生成。20 道问题均归纳自公开 GitHub Issues；不是原始内部客服工单。全部输出尚未人工审核，准确率、Recall@K、事实正确率均未计算。

模型：gpt-5.6-luna；Embedding：Qwen/Qwen3-Embedding-0.6B；官方帮助版本：2.100.0。

复用项目生成与 Embedding provider；检索为隔离实验实现。未经过 Java、工单状态、风险策略和最终回复规则，不能当作整个平台的端到端评测。

| 方案 | 请求 | 结构合格返回 | 失败 | 模型自报证据充分 | 模型自报不足 | 生成 p50 | 生成 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 关键词 | 20 | 16 | 4 | 9 | 7 | 13.41s | 20.68s |
| 向量检索 | 20 | 17 | 3 | 9 | 8 | 10.69s | 20.01s |
| AI 候选证据对照 | 5 | 4 | 1 | 4 | 0 | 14.13s | 20.65s |

“结构合格返回”只代表完成结构化解析且引用序号合法；不代表内容正确。充分/不足是模型自己的判断，不能当作人工判断。p50/p95 使用 nearest-rank，包含失败请求耗时，不含远端 Embedding，不能称为用户端到端响应时间。5 题对照使用 AI 提议的文档原文，不包含候选答案，不是人工 gold。

文档与问题共 269 条向量，1024 维，批量向量化耗时 3.22s。费用与失败请求的缺失 usage 不补为 0。

每题下方保留模型英文原文、实际提供的证据位置与原始 JSON。证据列表是输入给模型的上下文；只有标为“模型引用”的条目才被模型选用。

纯导航片段检查：只包含 LEARN MORE、通用 help/manual/exit-codes/accessibility 导航行与空行的片段。按实际提供位置计数，不去重；它只是可核验的上下文噪声诊断，不是召回率。

- BM25 关键词：0/60 个上下文位置为纯导航。
- 向量检索：7/60 个上下文位置为纯导航。
- AI 候选证据对照：0/11 个上下文位置为纯导航。

## gh-public-10301：How to get iteration-id

[公开问题来源](https://github.com/cli/cli/issues/10301)

I want to set a project item's iteration using gh project item-edit, but cannot find the required iteration ID. The item list does not provide it, and a suggested API endpoint returns 404. How should I obtain the ID?

### BM25 关键词

状态：COMPLETED；生成耗时 8.11s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-10301-bm25.json)

> The supplied GitHub CLI 2.100.0 documentation only confirms that `gh project item-edit` requires an iteration value ID via `--iteration-id`; it does not document how to obtain that ID. Therefore, I cannot safely provide a retrieval procedure based on the available documentation. The reported 404 endpoint is not addressed in these materials.

- 1. [gh_project_item-edit L21–44](../public-rag-pilot-2026-09-10/corpus/gh_project_item-edit.txt)（未引用）
- 2. [gh_project_item-edit L41–62](../public-rag-pilot-2026-09-10/corpus/gh_project_item-edit.txt)（未引用）
- 3. [gh_project L1–24](../public-rag-pilot-2026-09-10/corpus/gh_project.txt)（未引用）

### 向量检索

状态：COMPLETED；生成耗时 14.86s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-10301-vector.json)

> In the GitHub CLI 2.100.0 documentation, the usual approach is to select the project item and field by name, using the project number, `--owner`, the issue or pull request `--url`, and `--field`. For single-select fields, the documented value is the option name passed with `--value`.
> 
> For scripted use, `gh project item-edit` also accepts GraphQL node IDs through `--id`, `--field-id`, and `--project-id`. However, the supplied 2.100.0 documentation does not explain how to retrieve an iteration ID, nor does it document the endpoint you tried. Therefore, I cannot provide a documented iteration-ID retrieval procedure from this material. Use the documented name-based form where applicable, or obtain the required node IDs through your organization’s supported GitHub API documentation before using the ID-based form.

- 1. [gh_project_item-archive L21–28](../public-rag-pilot-2026-09-10/corpus/gh_project_item-archive.txt)（未引用）
- 2. [gh_project_item-edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_project_item-edit.txt)（模型引用）
- 3. [gh_project_item-edit L41–62](../public-rag-pilot-2026-09-10/corpus/gh_project_item-edit.txt)（模型引用）

## gh-public-9763：How to create a PR when only forking a branch?

[公开问题来源](https://github.com/cli/cli/issues/9763)

I copied a branch between two repositories that are not forks. I want to open a pull request from my repository to the other one, where I lack write access, without forking it. Is that workflow supported?

### 向量检索

状态：COMPLETED；生成耗时 16.92s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9763-vector.json)

> According to the GitHub CLI 2.100.0 documentation, use `--head <user>:<branch>` to explicitly select a head repository and branch, which skips the CLI's automatic forking or pushing behavior. For example:
> 
> ```bash
> gh pr create --head YOUR-USERNAME:YOUR-BRANCH --base BASE-BRANCH
> ```
> 
> However, the documented behavior does not explicitly confirm that the head repository may be an unrelated, non-fork repository. Therefore, the documentation supports selecting your repository as the head repository, but it does not establish that your exact non-fork workflow is supported. This answer reflects the GitHub CLI 2.100.0 documentation only; historical versions were not verified.

- 1. [gh_pr_create L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
- 2. [gh_pr_create L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）
- 3. [gh_pr_create L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 11.44s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9763-bm25.json)

> Yes. In the documented GitHub CLI 2.100.0 behavior, use `--head <user>:<branch>` with `gh pr create` to select the branch in your repository as the pull request head. The `--head` option explicitly skips the automatic forking or pushing behavior, so this workflow does not require forking the base repository.
> 
> For example:
> 
> ```bash
> gh pr create --base <base-branch> --head <your-user>:<your-branch>
> ```
> 
> This describes the current 2.100.0 documentation; historical versions have not been verified. Note that using an organization as `<user>` for `--head` is currently unsupported.

- 1. [gh_pr_create L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
- 2. [gh_pr_create L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）
- 3. [gh_pr_create L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）

## gh-public-9718：How gh manage multiple ssh accounts?

[公开问题来源](https://github.com/cli/cli/issues/9718)

I use separate SSH host aliases and keys for personal and work GitHub accounts. Passing an SSH alias to gh auth login as the hostname fails, while ordinary login leads to permission problems. How should I configure these accounts?

### BM25 关键词

状态：COMPLETED；生成耗时 19.22s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9718-bm25.json)

> According to the GitHub CLI 2.100.0 documentation, `gh auth login` authenticates against a GitHub host, defaulting to `github.com` or using the value supplied to `--hostname`. Although login is for a single account on a host, the selected Git protocol applies to all users on that host. The documented login flow does not describe SSH aliases as separate `gh` hosts or provide a mapping for multiple accounts on the same GitHub host.
> 
> Therefore, the documented configuration does not establish separate personal and work accounts by passing SSH aliases to `gh auth login`. Use the actual GitHub host name for authentication, such as `github.com`, and do not treat an SSH alias as a separately documented GitHub host. `gh auth setup-git` can configure GitHub CLI as Git’s credential helper for all authenticated hosts or for one specified authenticated host, but the supplied documentation does not explain how it selects between multiple accounts on the same host.
> 
> The 2.100.0 documentation is insufficient to provide a supported per-account SSH-alias configuration. It also does not verify behavior in historical or later versions.

- 1. [gh_auth_setup-git L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_setup-git.txt)（模型引用）
- 2. [gh_auth_login L21–44](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（模型引用）
- 3. [gh_auth_login L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（模型引用）

### 向量检索

状态：COMPLETED；生成耗时 13.20s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9718-vector.json)

> According to the supplied GitHub CLI 2.100.0 documentation, `gh auth login --hostname` selects the GitHub host or GitHub Enterprise instance being authenticated against; the documented example uses `enterprise.internal`. The documentation also states that login is for a single account on a host, while the selected Git protocol applies to all users on that host.
> 
> Therefore, the documented behavior does not provide a supported configuration for treating separate SSH host aliases as separate `gh` hosts or for configuring two accounts on `github.com` through `gh auth login`. Use the actual GitHub host with `--hostname` and select SSH with `--git-protocol ssh`; however, the provided documentation does not specify how to map multiple SSH aliases and keys to separate `gh` accounts or resolve the resulting permission conflict. It would be unsafe to claim a more specific configuration from these excerpts.

- 1. [gh_auth_login L61–70](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 2. [gh_auth_login L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（模型引用）
- 3. [gh_auth_login L21–44](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（模型引用）

## gh-public-9474：How can I get and change environment variables' value in Windows Powershell

[公开问题来源](https://github.com/cli/cli/issues/9474)

On Windows PowerShell, how can I inspect and change the environment variables documented for gh? I found the variable list but not the steps for setting their values.

### 向量检索

状态：COMPLETED；生成耗时 7.16s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-9474-vector.json)

> The provided GitHub CLI 2.100.0 documentation lists the supported environment variables and their behavior, but it does not include the Windows PowerShell steps for inspecting or changing their values. I cannot safely provide those commands from the available documentation.

- 1. [gh_completion L41–64](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）
- 2. [gh_help_environment L1–24](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）
- 3. [gh_help_environment L41–64](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 10.81s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-9474-bm25.json)

> The provided GitHub CLI 2.100.0 excerpts do not include the Windows PowerShell steps for inspecting or changing environment variables. They only state that gh can use authentication tokens from environment variables and refer to `gh help environment`. I cannot verify the requested PowerShell commands from the supplied documentation.

- 1. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）
- 2. [gh_auth_login L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 3. [gh_pr_edit L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_edit.txt)（未引用）

## gh-public-9457：how to resume broken download

[公开问题来源](https://github.com/cli/cli/issues/9457)

A gh release download operation left a partially downloaded file. I am using gh 2.49.2 and cannot find a resume flag in its help. Can I resume the download?

### BM25 关键词

状态：COMPLETED；生成耗时 9.34s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9457-bm25.json)

> The current documented behavior for GitHub CLI 2.100.0 does not include a resume flag for `gh release download`. Its documented flags include options such as `--clobber`, `--output`, `--pattern`, and `--skip-existing`, but not resume support. This documentation does not verify the behavior of your installed version, gh 2.49.2, so I cannot confirm whether that version supports resuming. Based on the current documentation, a partially downloaded file is not documented as resumable by `gh release download`.

- 1. [gh_release_download L1–24](../public-rag-pilot-2026-09-10/corpus/gh_release_download.txt)（模型引用）
- 2. [gh_release_download L21–42](../public-rag-pilot-2026-09-10/corpus/gh_release_download.txt)（模型引用）
- 3. [gh_extension_install L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_install.txt)（未引用）

### 向量检索

状态：COMPLETED；生成耗时 12.35s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-9457-vector.json)

> The available documentation is for GitHub CLI 2.100.0 and does not verify behavior in version 2.49.2. The provided excerpt does not document a resume procedure or resume option, so I cannot confirm that the partial download can be resumed. Please consult the documentation or help output for the specific version you are running.

- 1. [gh_release_upload L21–25](../public-rag-pilot-2026-09-10/corpus/gh_release_upload.txt)（未引用）
- 2. [gh_repo L41–46](../public-rag-pilot-2026-09-10/corpus/gh_repo.txt)（未引用）
- 3. [gh_release_download L21–42](../public-rag-pilot-2026-09-10/corpus/gh_release_download.txt)（未引用）

### AI 候选证据对照

状态：COMPLETED；生成耗时 11.01s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-9457-proposed_evidence.json)

> In the current GitHub CLI 2.100.0 documentation, `gh release download` does not list a resume option. The documented choices for an existing file are `--skip-existing`, which skips downloading when a same-named file exists, and `--clobber`, which overwrites it. The provided documentation does not verify the behavior of gh 2.49.2, so I cannot confirm whether that version supports resuming this partial download.

- 1. [gh_release_download L11–18](../public-rag-pilot-2026-09-10/corpus/gh_release_download.txt)（模型引用）

## gh-public-8972：How does gh pr comment process special chars in text files?

[公开问题来源](https://github.com/cli/cli/issues/8972)

I pass Terraform output to gh pr comment through --body-file, but the resulting comment renders special characters badly. Can the CLI preserve coloured output without me preprocessing the file?

### 向量检索

状态：COMPLETED；生成耗时 8.21s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-8972-vector.json)

> The provided GitHub CLI 2.100.0 documentation does not establish how `gh pr comment --body-file` processes special characters or whether it preserves colored Terraform output. Therefore, I cannot safely confirm that the CLI will preserve the colors without preprocessing the file. The documented excerpts only cover attachments and template formatting.

- 1. [gh_pr_comment L41–51](../public-rag-pilot-2026-09-10/corpus/gh_pr_comment.txt)（未引用）
- 2. [gh_help_formatting L121–144](../public-rag-pilot-2026-09-10/corpus/gh_help_formatting.txt)（未引用）
- 3. [gh_issue_comment L41–51](../public-rag-pilot-2026-09-10/corpus/gh_issue_comment.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 10.90s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-8972-bm25.json)

> The provided GitHub CLI 2.100.0 documentation does not specify how `gh pr comment --body-file` handles special characters or ANSI-colored output. Therefore, it does not establish whether colored Terraform output can be preserved without preprocessing, and I cannot confirm that behavior from the documented material.

- 1. [gh_pr_comment L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_comment.txt)（未引用）
- 2. [gh_issue_comment L1–24](../public-rag-pilot-2026-09-10/corpus/gh_issue_comment.txt)（未引用）
- 3. [gh_issue_create L1–24](../public-rag-pilot-2026-09-10/corpus/gh_issue_create.txt)（未引用）

## gh-public-8790：How can I disable the "set as the default repository" message after `gh repo clone`?

[公开问题来源](https://github.com/cli/cli/issues/8790)

After gh repo clone, the CLI prints a notice that the upstream repository was set as the default. Can I suppress only this notice?

### BM25 关键词

状态：COMPLETED；生成耗时 9.99s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-8790-bm25.json)

> In the GitHub CLI 2.100.0 documentation, there is no documented option to suppress only this notice.
> 
> For a fork, `gh repo clone` adds the parent repository as an `upstream` remote and sets it as the default remote. The documented `--no-upstream` option skips that behavior entirely:
> 
> ```bash
> gh repo clone OWNER/REPO --no-upstream
> ```
> 
> Therefore, `--no-upstream` is not a notice-only suppression; it also prevents the upstream remote from being added and the parent repository from being set as the default remote. The documentation is limited to GitHub CLI 2.100.0; this does not verify behavior in historical versions.

- 1. [gh_repo_fork L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_fork.txt)（未引用）
- 2. [gh_repo_clone L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_clone.txt)（模型引用）
- 3. [gh_repo_clone L21–44](../public-rag-pilot-2026-09-10/corpus/gh_repo_clone.txt)（模型引用）

### 向量检索

状态：COMPLETED；生成耗时 7.98s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-8790-vector.json)

> The provided GitHub CLI 2.100.0 documentation does not establish whether the default-repository notice can be suppressed independently. It documents `gh repo clone --no-upstream` for avoiding an upstream remote when cloning a fork, but that is not documented as a notice-suppression option. I cannot confirm a supported way to hide only this message from the supplied documentation.

- 1. [gh_repo_set-default L21–44](../public-rag-pilot-2026-09-10/corpus/gh_repo_set-default.txt)（未引用）
- 2. [gh_repo_clone L41–55](../public-rag-pilot-2026-09-10/corpus/gh_repo_clone.txt)（未引用）
- 3. [gh_repo_set-default L41–45](../public-rag-pilot-2026-09-10/corpus/gh_repo_set-default.txt)（未引用）

## gh-public-8295：How can I get the pull request template from cli command?

[公开问题来源](https://github.com/cli/cli/issues/8295)

I am writing a reusable shell workflow and need to obtain a repository's pull request template as text or a file. Is there a gh command to fetch that template?

### 向量检索

状态：COMPLETED；生成耗时 9.27s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-8295-vector.json)

> The provided GitHub CLI 2.100.0 documentation does not establish a command for fetching a repository's pull request template as text or as a file. It only shows a --template option for supplying a template when running gh pr create. I cannot confirm a retrieval command from the available documentation without making an unsupported claim.

- 1. [gh_pr_view L21–39](../public-rag-pilot-2026-09-10/corpus/gh_pr_view.txt)（未引用）
- 2. [gh_pr_status L21–38](../public-rag-pilot-2026-09-10/corpus/gh_pr_status.txt)（未引用）
- 3. [gh_pr_create L81–97](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 10.51s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-8295-bm25.json)

> The provided GitHub CLI 2.100.0 documentation shows that `gh pr create --template <file>` uses a local file as the starting body text. The supplied documentation does not describe a command for retrieving a repository's pull request template as text or as a file, so I cannot confirm such a fetch command from the available evidence.

- 1. [gh_pr_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_edit.txt)（未引用）
- 2. [gh_pr_create L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）
- 3. [gh_pr_create L61–84](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）

## gh-public-6526：How to find a pull request linked with an issue  from an issue id

[公开问题来源](https://github.com/cli/cli/issues/6526)

Given an issue ID, how can I find its linked pull request? An assistant suggested gh pr list with a linked:issue search, but that search syntax is unsupported.

### BM25 关键词

状态：COMPLETED；生成耗时 12.99s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-6526-bm25.json)

> The supplied GitHub CLI 2.100.0 documentation does not establish a supported way to find a pull request linked to an issue by issue ID. It confirms that `gh pr list --search` accepts supported issue and pull-request search syntax, but it does not document a linked-issue query or an equivalent command. Therefore, I cannot provide a verified command for this task from the available documentation.

- 1. [gh_pr_list L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（未引用）
- 2. [gh_pr_list L61–72](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（未引用）
- 3. [gh_pr_list L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（未引用）

### 向量检索

状态：COMPLETED；生成耗时 10.56s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-6526-vector.json)

> In GitHub CLI 2.100.0, query the issue with the documented `closedByPullRequestsReferences` JSON field:
> 
> ```bash
> gh issue view ISSUE_ID --repo OWNER/REPO --json closedByPullRequestsReferences
> ```
> 
> The returned field contains references to pull requests that closed the issue. The documented information supports this approach; `linked:issue` search syntax is not documented here, so it should not be relied on.

- 1. [gh_issue_view L21–32](../public-rag-pilot-2026-09-10/corpus/gh_issue_view.txt)（模型引用）
- 2. [gh_issue_pin L21–28](../public-rag-pilot-2026-09-10/corpus/gh_issue_pin.txt)（未引用）
- 3. [gh_issue_unpin L21–28](../public-rag-pilot-2026-09-10/corpus/gh_issue_unpin.txt)（未引用）

## gh-public-6330：`gh repo rename --help` does not show how to name an existing repo

[公开问题来源](https://github.com/cli/cli/issues/6330)

The gh repo rename help says I can rename a specified repository, but its usage shows only the new name. Where do I specify the existing target repository? The reported version is 2.16.0.

### 向量检索

状态：COMPLETED；生成耗时 8.07s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-6330-vector.json)

> In the current GitHub CLI 2.100.0 documentation, the existing repository is specified with the `--repo` (or `-R`) flag. The new name remains the positional argument:
> 
> ```sh
> gh repo rename -R OWNER/EXISTING-REPO NEW-NAME
> ```
> 
> For example:
> 
> ```sh
> gh repo rename -R qux/quux baz
> ```
> 
> Without `-R`, the current repository is renamed. The documentation describes the current 2.100.0 behavior; it does not verify the behavior or help text of version 2.16.0.

- 1. [gh_repo_rename L21–37](../public-rag-pilot-2026-09-10/corpus/gh_repo_rename.txt)（模型引用）
- 2. [gh_repo_rename L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_rename.txt)（模型引用）
- 3. [gh_release L21–31](../public-rag-pilot-2026-09-10/corpus/gh_release.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 13.65s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-6330-bm25.json)

> In the documented GitHub CLI 2.100.0 behavior, specify the new name as the positional argument and select the existing repository with `--repo` (or `-R`):
> 
> ```bash
> gh repo rename NEW_NAME --repo OWNER/REPO
> ```
> 
> For example:
> 
> ```bash
> gh repo rename new-repository-name -R octo-org/old-repository-name
> ```
> 
> If you omit `--repo`, the current repository is renamed. The `--repo` value uses the `[HOST/]OWNER/REPO` format. The supplied documentation is for version 2.100.0; it does not verify the behavior of the reported 2.16.0 version.

- 1. [gh_repo_fork L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_fork.txt)（未引用）
- 2. [gh_repo_rename L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_rename.txt)（模型引用）
- 3. [gh_repo_clone L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_clone.txt)（未引用）

## gh-public-6089：Explain how to use `git pr list --template` feature, or at least give some hints and an example

[公开问题来源](https://github.com/cli/cli/issues/6089)

I want to use gh pr list --template but do not know Go templates. The short flag description is not enough. Where can I find an explanation and a minimal example?

### BM25 关键词

状态：COMPLETED；生成耗时 17.86s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-6089-bm25.json)

> For the documented GitHub CLI 2.100.0 behavior, see the GitHub CLI formatting documentation (`gh_help_formatting`). The key points are:
> 
> - `--template` requires `--json` and a comma-separated list of fields.
> - The template must use Go template syntax.
> - To discover the fields supported by a command, run that command with `--json` without a field list.
> 
> For pull requests, start by discovering the available fields with:
> 
> ```sh
> gh pr list --json
> ```
> 
> Then provide the fields you want and format the resulting JSON with `--template`.
> 
> The supplied documentation excerpt explains the required flags and syntax, but it does not include a concrete `gh pr list` field selection or minimal Go-template example. Therefore, I cannot safely provide a verified command example from the available documentation without inventing details.

- 1. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）
- 2. [gh_help_environment L61–84](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）
- 3. [gh_help_formatting L1–24](../public-rag-pilot-2026-09-10/corpus/gh_help_formatting.txt)（模型引用）

### 向量检索

状态：COMPLETED；生成耗时 14.76s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-6089-vector.json)

> In the documented GitHub CLI 2.100.0 behavior, `--template` formats JSON output using Go template syntax. You must provide `--json` with the fields you want to fetch before using `--template`.
> 
> A minimal example is:
> 
> ```sh
> gh pr list --json number,title --template '{{range .}}#{{.number}} {{.title}}{{"\\n"}}{{end}}'
> ```
> 
> Here, `.number` and `.title` refer to the fields requested by `--json`, and `range` iterates over the pull requests. `{{"\\n"}}` adds a newline after each result.
> 
> The official formatting documentation also includes this example using helpers such as `tablerow`, `printf`, `autocolor`, and `timeago`:
> 
> ```sh
> gh pr list --json number,title,headRefName,updatedAt --template \
>   '{{range .}}{{tablerow (printf "#%v" .number | autocolor "green") .title .headRefName (timeago .updatedAt)}}{{end}}'
> ```
> 
> For more information, see the Go templates documentation: https://golang.org/pkg/text/template/ and the Sprig library documentation: https://masterminds.github.io/sprig/.

- 1. [gh_help_formatting L41–64](../public-rag-pilot-2026-09-10/corpus/gh_help_formatting.txt)（模型引用）
- 2. [gh_help_formatting L121–144](../public-rag-pilot-2026-09-10/corpus/gh_help_formatting.txt)（模型引用）
- 3. [gh_help_formatting L1–24](../public-rag-pilot-2026-09-10/corpus/gh_help_formatting.txt)（模型引用）

## gh-public-5147：How to upgrade an extension?

[公开问题来源](https://github.com/cli/cli/issues/5147)

On Ubuntu 20.04 with gh 2.4.0, an installed extension reports an available upgrade, but gh extensions upgrade --all exits with status 1. Removing and installing it works. How can I resolve the upgrade failure?

### 向量检索

状态：COMPLETED；生成耗时 15.97s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-5147-vector.json)

> The current documentation describes `gh extension upgrade {<name> | --all}` and lists `--dry-run` and `--force`, but it does not document the cause or resolution of an upgrade failure with exit status 1. Therefore, the available documentation is insufficient to determine why this occurs or to confirm that reinstalling or any specific workaround resolves it. The documented behavior is based on GitHub CLI 2.100.0; historical behavior for gh 2.4.0 has not been verified.

- 1. [gh_extension_upgrade L1–19](../public-rag-pilot-2026-09-10/corpus/gh_extension_upgrade.txt)（未引用）
- 2. [gh_extension L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension.txt)（未引用）
- 3. [gh_extension_install L41–57](../public-rag-pilot-2026-09-10/corpus/gh_extension_install.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 13.41s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-5147-bm25.json)

> The current documentation confirms that `gh extension upgrade` is the command for upgrading installed extensions, but it does not document a resolution for an upgrade failure or verify behavior in gh 2.4.0. Because the available documentation is frozen at GitHub CLI 2.100.0, I cannot safely identify the cause or recommend a specific fix without claiming unverified historical behavior. Please consult the command-specific help and the GitHub CLI manual for troubleshooting details.

- 1. [gh_extension L21–44](../public-rag-pilot-2026-09-10/corpus/gh_extension.txt)（未引用）
- 2. [gh_extension L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension.txt)（未引用）
- 3. [gh_extension_search L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_search.txt)（未引用）

### AI 候选证据对照

状态：COMPLETED；生成耗时 19.56s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-5147-proposed_evidence.json)

> The current GitHub CLI 2.100.0 documentation supports these commands:
> 
> - Upgrade all installed extensions: `gh extension upgrade --all`
> - Force an extension upgrade: `gh extension upgrade <name> --force`
> - Force upgrades for all extensions: `gh extension upgrade --all --force`
> - Preview available upgrades without changing anything: `gh extension upgrade --all --dry-run`
> 
> Because the available documentation is for GitHub CLI 2.100.0, it does not establish the cause of the status-1 failure in gh 2.4.0, and I cannot claim that behavior was verified for that historical version. The documented next step is to retry the affected extension with `--force`; use `--dry-run` first if you want to preview the upgrades.

- 1. [gh_extension_upgrade L1–9](../public-rag-pilot-2026-09-10/corpus/gh_extension_upgrade.txt)（模型引用）

## gh-public-5100：gh repo edit: not clear how to invert --enable-issues

[公开问题来源](https://github.com/cli/cli/issues/5100)

The gh repo edit help lists --enable-issues and similar flags. How can I use them to turn a repository feature off rather than on?

### BM25 关键词

状态：COMPLETED；生成耗时 8.47s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-5100-bm25.json)

> In the GitHub CLI 2.100.0 documentation, append `=false` to the flag:
> 
> ```sh
> gh repo edit OWNER/REPO --enable-issues=false
> ```
> 
> The same syntax applies to the other boolean `--enable-*` settings. This answer reflects the documented behavior for GitHub CLI 2.100.0; historical versions were not verified.

- 1. [gh_repo_edit L41–64](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）
- 2. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）
- 3. [gh_repo_edit L21–44](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）

### 向量检索

状态：COMPLETED；生成耗时 9.37s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-5100-vector.json)

> In GitHub CLI 2.100.0, turn an enabled repository feature off by adding `=false` to the flag:
> 
> ```bash
> gh repo edit --enable-issues=false
> ```
> 
> The general syntax is `--<flag>=false`. For example, the documentation shows `gh repo edit --enable-projects=false` for disabling projects. You can also provide the repository as an argument, such as `OWNER/REPO`.

- 1. [gh_repo_edit L61–73](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）
- 2. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）
- 3. [gh_repo_edit L41–64](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）

### AI 候选证据对照

状态：COMPLETED；生成耗时 14.13s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-5100-proposed_evidence.json)

> In the GitHub CLI 2.100.0 documentation, append `=false` to the flag to turn the feature off. For example:
> 
> ```bash
> gh repo edit --enable-issues=false
> ```
> 
> The same syntax applies to similar enable flags, such as `--enable-projects=false`.

- 1. [gh_repo_edit L1–3](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）
- 2. [gh_repo_edit L39–39](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）
- 3. [gh_repo_edit L65–66](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（模型引用）

## gh-public-4783：How can define completion for gh extension

[公开问题来源](https://github.com/cli/cli/issues/4783)

I wrote a zsh completion for a custom gh extension, but the #compdef approach does not work for its subcommand. How should I configure completion for the extension?

### 向量检索

状态：COMPLETED；生成耗时 8.11s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-4783-vector.json)

> The available GitHub CLI 2.100.0 documentation only covers the main `gh` completion script. It does not explain the configuration required for a custom extension's subcommand or the behavior of a separate zsh `#compdef` function. Therefore, I cannot safely provide the extension-specific configuration from the available documentation. The documented setup is to generate `_gh`, place it in `$fpath`, and ensure `autoload -U compinit` and `compinit -i` are present in `~/.zshrc`.

- 1. [gh_completion L21–44](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）
- 2. [gh_completion L1–24](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）
- 3. [gh_completion L41–64](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）

### BM25 关键词

状态：PROVIDER_ERROR；生成耗时 20.02s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-4783-bm25.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_completion L21–44](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）
- 2. [gh_completion L1–24](../public-rag-pilot-2026-09-10/corpus/gh_completion.txt)（未引用）
- 3. [gh_extension_search L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_search.txt)（未引用）

## gh-public-4129：How to uninstall?

[公开问题来源](https://github.com/cli/cli/issues/4129)

How do I uninstall GitHub CLI? I can find installation instructions but not the corresponding uninstall instructions.

### BM25 关键词

状态：PROVIDER_ERROR；生成耗时 20.68s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-4129-bm25.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_extension_remove L1–17](../public-rag-pilot-2026-09-10/corpus/gh_extension_remove.txt)（未引用）
- 2. [gh_help_environment L61–84](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）
- 3. [gh_extension_search L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_search.txt)（未引用）

### 向量检索

状态：COMPLETED；生成耗时 10.69s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-4129-vector.json)

> The provided GitHub CLI 2.100.0 documentation excerpts do not include uninstall instructions. They only document repository deletion, project deletion, and authentication logout, so I cannot safely provide the current uninstall procedure from this evidence.

- 1. [gh_repo_delete L21–27](../public-rag-pilot-2026-09-10/corpus/gh_repo_delete.txt)（未引用）
- 2. [gh_project_delete L21–26](../public-rag-pilot-2026-09-10/corpus/gh_project_delete.txt)（未引用）
- 3. [gh_auth_logout L41–45](../public-rag-pilot-2026-09-10/corpus/gh_auth_logout.txt)（未引用）

## gh-public-375：How to authorise cli without a browser?

[公开问题来源](https://github.com/cli/cli/issues/375)

I run GitHub CLI on a remote machine over SSH without a browser. How can I authenticate in this environment?

### 向量检索

状态：PROVIDER_ERROR；生成耗时 20.01s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-375-vector.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_auth_login L61–70](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 2. [gh_auth_login L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 3. [gh_auth_login L41–64](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）

### BM25 关键词

状态：PROVIDER_ERROR；生成耗时 20.72s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-375-bm25.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_auth_login L41–64](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 2. [gh_auth_login L21–44](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 3. [gh_help_environment L1–24](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）

### AI 候选证据对照

状态：PROVIDER_ERROR；生成耗时 20.65s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-375-proposed_evidence.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_auth_login L18–20](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）
- 2. [gh_help_environment L1–6](../public-rag-pilot-2026-09-10/corpus/gh_help_environment.txt)（未引用）
- 3. [gh_auth_login L12–16](../public-rag-pilot-2026-09-10/corpus/gh_auth_login.txt)（未引用）

## gh-public-2751：how can i attach multiple files eith gh release create?

[公开问题来源](https://github.com/cli/cli/issues/2751)

How can I attach several files when creating a release with gh release create? The example I found only showed one file.

### BM25 关键词

状态：COMPLETED；生成耗时 15.01s；模型自报证据充分：false。

[原始记录](run-1/trials/gh-public-2751-bm25.json)

> The provided GitHub CLI 2.100.0 documentation does not include the `gh release create` command or document how it accepts multiple files. I can’t safely confirm the current documented behavior from these excerpts without relying on unverified information.

- 1. [gh_issue_comment L21–44](../public-rag-pilot-2026-09-10/corpus/gh_issue_comment.txt)（未引用）
- 2. [gh_pr_comment L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_comment.txt)（未引用）
- 3. [gh_extension_install L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_install.txt)（未引用）

### 向量检索

状态：COMPLETED；生成耗时 10.36s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-2751-vector.json)

> In the documented GitHub CLI 2.100.0 behavior, pass multiple asset files after the tag as positional arguments, or use a file pattern. For example:
> 
> ```bash
> gh release create v1.2.3 ./dist/file1.zip ./dist/file2.zip ./dist/checksums.txt
> ```
> 
> To upload all matching tarballs in a directory:
> 
> ```bash
> gh release create v1.2.3 ./dist/*.tgz
> ```
> 
> The command syntax is `gh release create [<tag>] [<filename>... | <pattern>...]`. This answer is based on the GitHub CLI 2.100.0 documentation; it does not verify historical versions.

- 1. [gh_release_create L81–104](../public-rag-pilot-2026-09-10/corpus/gh_release_create.txt)（模型引用）
- 2. [gh_release_create L21–44](../public-rag-pilot-2026-09-10/corpus/gh_release_create.txt)（模型引用）
- 3. [gh_release_create L1–24](../public-rag-pilot-2026-09-10/corpus/gh_release_create.txt)（模型引用）

## gh-public-2081：Question: How to search all PRs based on author and status in repo

[公开问题来源](https://github.com/cli/cli/issues/2081)

How can I list pull requests in a repository filtered by author and status? Fetching a very large list and filtering it locally is too slow.

### 向量检索

状态：COMPLETED；生成耗时 14.64s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-2081-vector.json)

> In the documented GitHub CLI 2.100.0 behavior, use `--author` together with `--state` or `--search`:
> 
> ```bash
> # Pull requests by an author; open PRs are listed by default
> gh pr list --author USERNAME
> 
> # Pull requests by an author in a specific state
> gh pr list --author USERNAME --state merged
> 
> # Pull requests by an author with a check-status search filter
> gh pr list --author USERNAME --search "status:success"
> ```
> 
> `--author` filters by PR author. The default state is open, and the documentation shows `--state merged` for merged PRs. The `--search` value supports advanced issue and pull-request search syntax on supported GitHub hosts, including status filters such as `status:success`.
> 
> This uses the CLI's documented filters instead of fetching a very large unfiltered list for local filtering.

- 1. [gh_pr_list L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（模型引用）
- 2. [gh_pr_list L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（模型引用）
- 3. [gh_pr_list L61–72](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（模型引用）

### BM25 关键词

状态：PROVIDER_ERROR；生成耗时 20.01s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-2081-bm25.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_pr_list L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_list.txt)（未引用）
- 2. [gh_issue_list L1–24](../public-rag-pilot-2026-09-10/corpus/gh_issue_list.txt)（未引用）
- 3. [gh_extension_install L1–24](../public-rag-pilot-2026-09-10/corpus/gh_extension_install.txt)（未引用）

## gh-public-1530：How to commit or push or both?

[公开问题来源](https://github.com/cli/cli/issues/1530)

I previously used git commit and git push to send changes to a repository. What are the corresponding operations when using GitHub CLI?

### BM25 关键词

状态：COMPLETED；生成耗时 18.46s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-1530-bm25.json)

> In the provided GitHub CLI 2.100.0 documentation, `gh pr create` can handle pushing the current branch: if the branch is not fully pushed to a Git remote, it prompts you to choose where to push it. Use `--head` to explicitly skip pushing or forking behavior.
> 
> The supplied documentation does not specify a GitHub CLI command corresponding to `git commit`, so I cannot confirm a documented commit operation from this material.

- 1. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）
- 2. [gh_auth_switch L1–24](../public-rag-pilot-2026-09-10/corpus/gh_auth_switch.txt)（未引用）
- 3. [gh_pr_create L1–24](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）

### 向量检索

状态：PROVIDER_ERROR；生成耗时 20.01s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-1530-vector.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_pr_update-branch L21–30](../public-rag-pilot-2026-09-10/corpus/gh_pr_update-branch.txt)（未引用）
- 2. [gh_repo_clone L41–55](../public-rag-pilot-2026-09-10/corpus/gh_repo_clone.txt)（未引用）
- 3. [gh_release_upload L21–25](../public-rag-pilot-2026-09-10/corpus/gh_release_upload.txt)（未引用）

## gh-public-1331：Migrating from `hub`: how to provide "pr create" body via file?

[公开问题来源](https://github.com/cli/cli/issues/1331)

I am migrating a workflow from hub and need to create a pull request whose description comes from a large generated Markdown file. I can provide the title separately and cannot use commit autofill. How can I provide the body file?

### 向量检索

状态：PROVIDER_ERROR；生成耗时 20.79s；模型自报证据充分：无输出。

[原始记录](run-1/trials/gh-public-1331-vector.json)

失败：structured_generation_response_timeout；诊断：{"sdk_error_kind":"APITimeoutError","transport_cause_kind":"ReadTimeout","http_status":"none"}。

- 1. [gh_pr_create L21–44](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（未引用）
- 2. [gh_pr_comment L41–51](../public-rag-pilot-2026-09-10/corpus/gh_pr_comment.txt)（未引用）
- 3. [gh_pr_edit L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_edit.txt)（未引用）

### BM25 关键词

状态：COMPLETED；生成耗时 13.83s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-1331-bm25.json)

> With the documented GitHub CLI 2.100.0 behavior, provide the title with `--title` and the generated Markdown file with `--body-file`:
> 
> ```bash
> gh pr create --title "Your pull request title" --body-file path/to/generated-body.md
> ```
> 
> This does not use commit autofill. The `--body-file` option reads the body text from the specified file. You can also use `--body-file -` to read the body from standard input.

- 1. [gh_pr_create L61–84](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
- 2. [gh_repo_edit L1–24](../public-rag-pilot-2026-09-10/corpus/gh_repo_edit.txt)（未引用）
- 3. [gh_pr_edit L41–64](../public-rag-pilot-2026-09-10/corpus/gh_pr_edit.txt)（未引用）

### AI 候选证据对照

状态：COMPLETED；生成耗时 8.78s；模型自报证据充分：true。

[原始记录](run-1/trials/gh-public-1331-proposed_evidence.json)

> For the documented GitHub CLI 2.100.0 behavior, provide the generated Markdown file with `--body-file` and specify the title with `--title`:
> 
> ```bash
> gh pr create --title "Your pull request title" --body-file path/to/generated-body.md
> ```
> 
> You can also use `--body-file -` to read the body from standard input. Since you are providing the title and body explicitly, you do not need `--fill`. This answer is based on the GitHub CLI 2.100.0 documentation; historical versions were not verified.

- 1. [gh_pr_create L61–61](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
- 2. [gh_pr_create L76–76](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
- 3. [gh_pr_create L14–18](../public-rag-pilot-2026-09-10/corpus/gh_pr_create.txt)（模型引用）
