# set-up

我的个人项目初始化工具：新项目装配常用工程配置，已有项目只加入个人 AI Skill。

## 一键配置

先建好项目目录并进入其中；已有项目直接进入项目根目录。脚本会自动补齐缺少的启动依赖，新项目还会安装所选语言的工具链和检查工具；系统包安装可能需要 sudo。

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh
```

如果新设备连 curl 都没有，Debian / Ubuntu 可先执行下面这条完整引导命令（root 用户去掉 sudo）；其他系统见[依赖引导](docs/setup.md#依赖引导)：

```bash
sudo apt-get update && sudo apt-get install -y curl ca-certificates && curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh
```

按提示选择模式：

| 模式 | 会配置什么 |
| --- | --- |
| 新项目 | 选择 Go / Python / Java，初始化 Git，装配 Skill、gitignore、lint、Makefile 和 GitHub CI |
| 已有项目 | Skill only：安装 Skill，补充 Agent 忽略规则与装配记录；保留原有工程配置 |

默认给 **Codex 和 Antigravity** 安装全部已收录 Skill。需要 Claude 等其他目标时，见[进阶用法](docs/setup.md#选择-agent-和-skill)。

setup 配置当前目录，不创建项目目录或业务代码。新项目添加代码后可用 `make check`；Python 检查依赖使用项目隔离环境。只想生成配置时加 `--skip-deps`，详细行为见[依赖引导](docs/setup.md#依赖引导)。

## 不想交互选择

```bash
# 新 Go 项目（也可把 go 换成 python 或 java）
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --mode new --language go

# 已有项目，只加入个人 AI Skill
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --mode existing
```

可加 `--dry-run` 先预览。已有配置发生冲突时会保留原文件并显示差异。

## 更新 Skill

在项目根目录执行：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --mode existing --update
```

只更新所选 Agent 中已安装的 Skill，未安装项跳过。**更新会替换 Skill 目录中的本地修改**；有自定义内容请先备份。工程配置的更新方式见[更新与冲突处理](docs/setup.md#更新与冲突处理)。

## 更多说明

- [默认 lint 策略](docs/lint.md)：长度、复杂度检查及官方依据。
- [工作模型与流程图](docs/workflow.md)：完整的装配、依赖、更新和检查流程。
- [使用手册](docs/setup.md)：指定 Agent、参数、依赖、模板更新，以及免 Python 的 Skill 独立安装器。
- [项目 Agent 指南](docs/agent-setup.md)：交给其他项目中的 Agent，单独阅读即可代你完成 setup。
- [仓库维护指南](AGENTS.md)：面向修改本仓库的 Agent。
- [Skill 来源维护](docs/skills.md)：收录、同步、许可证审核与自动更新。
- [外部 Skill 索引](external-skills.md)：未镜像的项目及其官方安装方式。

## 已收录 Skill

<details>
<summary>展开查看 Skill ID、本地目录和许可证</summary>

| ID | 本地目录 | 许可证 |
| --- | --- | --- |
| `mattpocock-teach` | `skills/mattpocock/teach` | MIT |
| `mattpocock-handoff` | `skills/mattpocock/handoff` | MIT |
| `mattpocock-grill-me` | `skills/mattpocock/grill-me` | MIT |
| `mattpocock-grilling` | `skills/mattpocock/grilling` | MIT |
| `nextlevelbuilder-ui-ux-pro-max` | `skills/nextlevelbuilder/ui-ux-pro-max` | MIT |
| `fission-ai-openspec-propose` | `skills/fission-ai/openspec-propose` | MIT |
| `fission-ai-openspec-apply-change` | `skills/fission-ai/openspec-apply-change` | MIT |
| `fission-ai-openspec-archive-change` | `skills/fission-ai/openspec-archive-change` | MIT |
| `fission-ai-openspec-explore` | `skills/fission-ai/openspec-explore` | MIT |
| `slidevjs-slidev` | `skills/slidevjs/slidev` | MIT |
| `dreambigou-eli5` | `skills/dreambigou/eli5` | MIT |
| `cocoon-ai-architecture-diagram` | `skills/cocoon-ai/architecture-diagram` | MIT |
| `github-git-commit` | `skills/github/git-commit` | MIT |

</details>
