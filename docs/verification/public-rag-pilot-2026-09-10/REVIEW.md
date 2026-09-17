# 人工试标注工作表

状态：0/20 已审核；候选文档由 AI 提出，不是标准答案。先核对归纳是否忠实，再判断文档适用版本与证据；不得直接批准所有候选。所有案例均为开发试标注，没有模型回答需要打分。

每例请填写：归纳是否忠实、按 2.100.0 文档能否回答（可答/需补问/无证据/需授权或升级）、准确原文文件及行号、必要要点、禁止承诺、审核人、UTC 时间及依据。保留原版本问题的条件；若只能提供当前版本建议，要在判断中明确。

## gh-public-10301

[原问题：How to get iteration-id](https://github.com/cli/cli/issues/10301)

**待核对的英文归纳：** I want to set a project item's iteration using gh project item-edit, but cannot find the required iteration ID. The item list does not provide it, and a suggested API endpoint returns 404. How should I obtain the ID?

**风险提示：** The manual may not contain the required GraphQL schema; do not invent an endpoint.

候选资料：[gh_project_item-edit](corpus/gh_project_item-edit.txt)、[gh_project_field-list](corpus/gh_project_field-list.txt)、[gh_project_item-list](corpus/gh_project_item-list.txt)、[gh_api](corpus/gh_api.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-9763

[原问题：How to create a PR when only forking a branch?](https://github.com/cli/cli/issues/9763)

**待核对的英文归纳：** I copied a branch between two repositories that are not forks. I want to open a pull request from my repository to the other one, where I lack write access, without forking it. Is that workflow supported?

**风险提示：** Support depends on repository relationships, not just command syntax.

候选资料：[gh_pr_create](corpus/gh_pr_create.txt)、[gh_repo_fork](corpus/gh_repo_fork.txt)、[gh_repo_set-default](corpus/gh_repo_set-default.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-9718

[原问题：How gh manage multiple ssh accounts?](https://github.com/cli/cli/issues/9718)

**待核对的英文归纳：** I use separate SSH host aliases and keys for personal and work GitHub accounts. Passing an SSH alias to gh auth login as the hostname fails, while ordinary login leads to permission problems. How should I configure these accounts?

**风险提示：** Git SSH identity and API account selection differ; migrated discussion 9078 must stay in this group.

候选资料：[gh_auth_login](corpus/gh_auth_login.txt)、[gh_auth_switch](corpus/gh_auth_switch.txt)、[gh_auth_setup-git](corpus/gh_auth_setup-git.txt)、[gh_help_environment](corpus/gh_help_environment.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-9474

[原问题：How can I get and change environment variables' value in Windows Powershell](https://github.com/cli/cli/issues/9474)

**待核对的英文归纳：** On Windows PowerShell, how can I inspect and change the environment variables documented for gh? I found the variable list but not the steps for setting their values.

**风险提示：** Shell-specific operations may require PowerShell documentation outside this corpus; linked discussion 9473 is the same case.

候选资料：[gh_help_environment](corpus/gh_help_environment.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-9457

[原问题：how to resume broken download](https://github.com/cli/cli/issues/9457)

**待核对的英文归纳：** A gh release download operation left a partially downloaded file. I am using gh 2.49.2 and cannot find a resume flag in its help. Can I resume the download?

**风险提示：** Explicit old-version question; current manual cannot prove historical behaviour or equate overwrite with resume.

候选资料：[gh_release_download](corpus/gh_release_download.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-8972

[原问题：How does gh pr comment process special chars in text files?](https://github.com/cli/cli/issues/8972)

**待核对的英文归纳：** I pass Terraform output to gh pr comment through --body-file, but the resulting comment renders special characters badly. Can the CLI preserve coloured output without me preprocessing the file?

**风险提示：** The source screenshot is excluded; visible text alone may not establish the exact encoding problem.

候选资料：[gh_pr_comment](corpus/gh_pr_comment.txt)、[gh_help_formatting](corpus/gh_help_formatting.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-8790

[原问题：How can I disable the "set as the default repository" message after `gh repo clone`?](https://github.com/cli/cli/issues/8790)

**待核对的英文归纳：** After gh repo clone, the CLI prints a notice that the upstream repository was set as the default. Can I suppress only this notice?

**风险提示：** Do not infer that disabling a different notification suppresses this message.

候选资料：[gh_repo_clone](corpus/gh_repo_clone.txt)、[gh_repo_set-default](corpus/gh_repo_set-default.txt)、[gh_help_environment](corpus/gh_help_environment.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-8295

[原问题：How can I get the pull request template from cli command?](https://github.com/cli/cli/issues/8295)

**待核对的英文归纳：** I am writing a reusable shell workflow and need to obtain a repository's pull request template as text or a file. Is there a gh command to fetch that template?

**风险提示：** Selecting a template when creating a PR is different from retrieving template contents.

候选资料：[gh_pr_create](corpus/gh_pr_create.txt)、[gh_api](corpus/gh_api.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-6526

[原问题：How to find a pull request linked with an issue  from an issue id](https://github.com/cli/cli/issues/6526)

**待核对的英文归纳：** Given an issue ID, how can I find its linked pull request? An assistant suggested gh pr list with a linked:issue search, but that search syntax is unsupported.

**风险提示：** Do not repeat the unsupported syntax; linking semantics may require additional API reference.

候选资料：[gh_pr_list](corpus/gh_pr_list.txt)、[gh_issue_view](corpus/gh_issue_view.txt)、[gh_api](corpus/gh_api.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-6330

[原问题：`gh repo rename --help` does not show how to name an existing repo](https://github.com/cli/cli/issues/6330)

**待核对的英文归纳：** The gh repo rename help says I can rename a specified repository, but its usage shows only the new name. Where do I specify the existing target repository? The reported version is 2.16.0.

**风险提示：** Keep the reported version visible; distinguish current help from a historical reproduction.

候选资料：[gh_repo_rename](corpus/gh_repo_rename.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-6089

[原问题：Explain how to use `git pr list --template` feature, or at least give some hints and an example](https://github.com/cli/cli/issues/6089)

**待核对的英文归纳：** I want to use gh pr list --template but do not know Go templates. The short flag description is not enough. Where can I find an explanation and a minimal example?

**风险提示：** Clarify the JSON output prerequisite; do not treat wording similarity as answer correctness.

候选资料：[gh_help_formatting](corpus/gh_help_formatting.txt)、[gh_pr_list](corpus/gh_pr_list.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-5147

[原问题：How to upgrade an extension?](https://github.com/cli/cli/issues/5147)

**待核对的英文归纳：** On Ubuntu 20.04 with gh 2.4.0, an installed extension reports an available upgrade, but gh extensions upgrade --all exits with status 1. Removing and installing it works. How can I resolve the upgrade failure?

**风险提示：** A command recipe alone does not diagnose the reported failure; more logs or extension details may be required.

候选资料：[gh_extension_upgrade](corpus/gh_extension_upgrade.txt)、[gh_extension_list](corpus/gh_extension_list.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-5100

[原问题：gh repo edit: not clear how to invert --enable-issues](https://github.com/cli/cli/issues/5100)

**待核对的英文归纳：** The gh repo edit help lists --enable-issues and similar flags. How can I use them to turn a repository feature off rather than on?

**风险提示：** Related issue 2901 belongs to this group; avoid splitting near-duplicate boolean flag questions.

候选资料：[gh_repo_edit](corpus/gh_repo_edit.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-4783

[原问题：How can define completion for gh extension](https://github.com/cli/cli/issues/4783)

**待核对的英文归纳：** I wrote a zsh completion for a custom gh extension, but the #compdef approach does not work for its subcommand. How should I configure completion for the extension?

**风险提示：** Main CLI completion does not necessarily document extension-specific completion registration.

候选资料：[gh_completion](corpus/gh_completion.txt)、[gh_extension_create](corpus/gh_extension_create.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-4129

[原问题：How to uninstall?](https://github.com/cli/cli/issues/4129)

**待核对的英文归纳：** How do I uninstall GitHub CLI? I can find installation instructions but not the corresponding uninstall instructions.

**风险提示：** Operating system and installation method are missing; avoid guessing package-manager commands.

候选资料：[gh_help_reference](corpus/gh_help_reference.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-375

[原问题：How to authorise cli without a browser?](https://github.com/cli/cli/issues/375)

**待核对的英文归纳：** I run GitHub CLI on a remote machine over SSH without a browser. How can I authenticate in this environment?

**风险提示：** The source predates the frozen manual; provide current-version advice without claiming to reproduce its original behaviour.

候选资料：[gh_auth_login](corpus/gh_auth_login.txt)、[gh_help_environment](corpus/gh_help_environment.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-2751

[原问题：how can i attach multiple files eith gh release create?](https://github.com/cli/cli/issues/2751)

**待核对的英文归纳：** How can I attach several files when creating a release with gh release create? The example I found only showed one file.

**风险提示：** Linked discussion 2747 is the same source question, not an additional independent example.

候选资料：[gh_release_create](corpus/gh_release_create.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-2081

[原问题：Question: How to search all PRs based on author and status in repo](https://github.com/cli/cli/issues/2081)

**待核对的英文归纳：** How can I list pull requests in a repository filtered by author and status? Fetching a very large list and filtering it locally is too slow.

**风险提示：** Author and state filters should be distinguished from pagination limits.

候选资料：[gh_pr_list](corpus/gh_pr_list.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-1530

[原问题：How to commit or push or both?](https://github.com/cli/cli/issues/1530)

**待核对的英文归纳：** I previously used git commit and git push to send changes to a repository. What are the corresponding operations when using GitHub CLI?

**风险提示：** A missing gh subcommand is not proof of unsupported Git operations; may need separate Git documentation.

候选资料：[gh_help_reference](corpus/gh_help_reference.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写

## gh-public-1331

[原问题：Migrating from `hub`: how to provide "pr create" body via file?](https://github.com/cli/cli/issues/1331)

**待核对的英文归纳：** I am migrating a workflow from hub and need to create a pull request whose description comes from a large generated Markdown file. I can provide the title separately and cannot use commit autofill. How can I provide the body file?

**风险提示：** Preserve distinction between a body file and using commit messages; current support may postdate the original report.

候选资料：[gh_pr_create](corpus/gh_pr_create.txt)

- 忠实性审核：NOT_REVIEWED
- 可答性：待判断
- 证据文件与行号：待填写
- 必须回答的要点：待填写
- 禁止承诺或缺失信息：待填写
- 审核人 / UTC 时间 / 判断依据：待填写
