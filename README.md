# 个人项目 setup（set-up）

为个人新项目和已有项目装配常用配置，目前覆盖 Skill、gitignore、Go / Python / Java 的 lint、Makefile 和 GitHub Actions CI。各模块可单独使用，保留原有 Skill 收集、分发和更新能力。

## 统一 setup

推荐像原来一样使用一键入口：先创建并进入项目目录，然后执行下面这一条命令，无需克隆本仓库或指定本地脚本路径：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh
```

在交互终端中会询问新项目 / 已有项目模式，新项目再选择语言。脚本从 `/dev/tty` 获取交互输入，因此可用于 `curl | sh`。

也可一条命令明确指定模式，或更新已装配内容：

```bash
# 新 Go 项目配置
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --mode new --language go

# 已有项目，只加入个人 AI 内容
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --mode existing

# 更新
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh -s -- --update
```

一键入口需要 curl、tar 和 Python 3.11+，新项目初始化 Git 还需要 Git；缺少依赖会提示，不自动安装系统软件。远程命令使用 GitHub 对应分支的内容，尚未发布的本地改动可用下面的本地入口验证。

需要 Python 3.11+。交互运行时先选择模式：

1. **创建新项目（new）**：选择 Go / Python / Java，配置 Skill、gitignore、lint、Makefile 和 CI。先手动创建项目目录并进入其中运行 setup，脚本在当前目录执行 `git init`；已有 `.git`（含 worktree 文件）则保留。不会自动提交、设置远程仓库或修改全局 Git 配置。当前初始化的是项目配置，不生成业务代码、go.mod、pyproject.toml 或 Maven / Gradle 项目骨架，添加实际代码与项目元数据后再运行检查。
2. **加入已有项目（existing）**：只装配个人 AI Skill、对应 Agent 的忽略项及 setup 状态记录，保留项目原有 lint、CI、Makefile。默认目标为 Codex + Antigravity。

先创建项目目录并进入，再调用本地仓库的入口，按提示选择：

```bash
mkdir my-project
cd my-project
python3 /path/to/set-up/scripts/setup.py
```

也可以明确指定模式，先预览再执行：

```bash
python3 /path/to/set-up/scripts/setup.py --mode new --language go --dry-run
python3 /path/to/set-up/scripts/setup.py --mode new --language go

# 已有项目，只加入个人 AI Skill
python3 /path/to/set-up/scripts/setup.py --mode existing
```

也可以显式指定目标和模块，例如 Go 项目：

```bash
python3 scripts/setup.py --project /path/to/project \
  --modules gitignore,lint,makefile,ci --language go --go-version 1.25 --dry-run
```

确认后去掉 `--dry-run`。其他示例：

```bash
# Python；没有准确版本文件时显式指定 CI 版本
python3 scripts/setup.py --project /path/to/project \
  --modules gitignore,lint,makefile,ci --language python --python-version 3.12

# Java，已有 pom.xml / build.gradle 时可识别构建工具
python3 scripts/setup.py --project /path/to/project \
  --modules gitignore,lint,makefile,ci --language java --java-build maven --java-version 21

# 只装配 Skill，选择其他 Agent 或指定 ID
python3 scripts/setup.py --project /path/to/project \
  --modules skills --agents claude --only github-git-commit
```

提供免克隆入口（使用远程仓库对应 ref 的实现；本地未发布改动请使用上面的 Python 入口）：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh
```

引导脚本通过归档下载本仓库，要求 curl、tar、Python 3.11+，不会执行 Git clone。
可通过环境变量 `SETUP_REPO=owner/repo`、`SETUP_REF=commit` 固定来源；参数可通过 `sh -s -- ...` 传入。

Antigravity CLI 的项目目录使用官方支持的 `.agents/skills`，见 [官方 Skill 文档](https://antigravity.google/docs/skills)。

### 默认行为和选项

- 默认操作当前目录：先手动创建并进入项目目录，再运行 setup。两个模式都不创建目标目录；`--project` 仅可指定其他已存在的目录。
- `--mode new` 默认启用 `skills,gitignore,lint,makefile,ci`；`--mode existing` 仅启用 `skills`，不因检测到项目语言而加入工程配置。
- 不指定模式且存在交互终端时询问模式；无交互终端默认 existing。`--interactive` 可显式从标准输入询问，`--non-interactive` 禁止询问，适合自动化。
- `--mode new` 在交互时询问语言和缺失的 CI 版本；非交互时需提供 `--language` 或可识别的项目文件，缺失版本使用明确的模板默认值：Go 1.25、Python 3.12、Java 21。Java 空项目的构建工具默认 Maven，可选择 Gradle。
- 显式传 `--modules` 可单独运行模块；未指定 mode 时，包含工程配置模块视为 new。显式 existing 模式拒绝工程配置模块，保证不误改已有项目。
- 依据项目根目录的 `go.mod` / `go.work`、Python 项目文件、`pom.xml` / `build.gradle(.kts)` 辅助识别；`--language go,python` 可显式组合。不会创建业务代码、初始化语言模块或安装工具链。
- Skill 默认目标为 `codex,antigravity`；`--agents` 支持逗号分隔的 `codex,antigravity,claude`。
- CI 需要准确运行版本：Go 从 go.work / go.mod 读取，Python 从 `.python-version` 读取，Java 从 `.java-version` 或 Maven 的常见版本属性读取；可用 `--go-version`、`--python-version`、`--java-version` 覆盖。在显式 new 引导流程中，缺失值可询问或使用上述默认值；直接单独安装 CI 模块时，不能确定版本会报错并保留文件。
- Java 检查工具要求 JDK 17+；Python 检查入口要求 Python 3.11+。当前模板面向 Linux / macOS 和 GitHub 托管的 Ubuntu runner，Makefile 需要 Make。
- `--dry-run` 展示文件计划和差异，不写文件、不安装依赖。Skill 仅显示目标、ID 和更新模式，不联网获取上游或验证远端 ID。
- 不传 `skills` 模块时配置生成完全离线。统一入口调用 Skill 安装器时默认关闭 OpenSpec CLI 自动安装，按提示自行补装；独立 Skill 安装器保留原有行为。

### 配置文件

默认读取 `~/.config/project-setup/config.json`，也可用 `--config /path/to/config.json` 指定。示例：

```json
{
  "mode": "new",
  "modules": ["skills", "gitignore", "lint", "makefile", "ci"],
  "languages": ["python"],
  "agents": ["codex", "antigravity"],
  "python_version": "3.12"
}
```

优先级为：命令行 > 个人配置文件 > 更新时记录的选项 > 自动检测与默认值。
可配置键见 `python3 scripts/setup.py --help` 对应的 `mode`、`modules`、`languages`、`agents`、`java_build`、三个 `*_version` 和 `python_install`。

### 生成内容与执行检查

| 模块 | 生成内容 / 默认工具 |
| --- | --- |
| gitignore | `.gitignore` 管理区块，组合通用、语言及所选 Agent 规则 |
| lint | `.setup/check.py` 与检查配置；Go 使用 gofmt / golangci-lint v2（生成 `.golangci.yml`），Python 使用 Ruff，Java 使用 google-java-format / Checkstyle |
| makefile | `Makefile`，提供 help、format、format-check、lint、test、build、check |
| ci | `.github/workflows/setup-<language>.yml`，push / pull_request 触发，只读仓库权限 |

选择 lint、Makefile 或 CI 中任一模块都会生成共用检查入口及必要配置；CI 单独安装时也能执行。本地和 CI 共用命令，`check` 依次检查格式、lint、测试和构建，修改源码请使用 `format`。

```bash
make help
make check
make check SETUP_LANGUAGE=go  # 多语言项目仅检查一种语言
# 不使用 Make 时直接运行
python3 .setup/check.py check
```

Go 使用已安装的 Go 工具链与 golangci-lint v2，支持项目内模块组成的 go.work。`make lint` 运行 `golangci-lint run`，默认启用 errcheck、govet、ineffassign、staticcheck、unused、bodyclose、errorlint、nolintlint；gofmt 保持独立。CI 通过官方 Action 安装固定版本 2.13.2 后复用本地检查命令。setup 不安装此工具，请按[官方安装说明](https://golangci-lint.run/docs/welcome/install/local/)安装 2.13.2 并加入 PATH。已有 `.golangci.yml` 遵循冲突保护和更新规则；已有其他支持格式的配置时直接沿用，不生成额外的 `.golangci.yml`。Python 使用当前解释器下的 Ruff、pytest、build；无包元数据时跳过构建，无测试时 pytest 的非零退出码会如实保留。Java 使用现有 Maven / Gradle wrapper，缺少 wrapper 时调用系统 mvn / gradle；不会重写 pom.xml 或 Gradle 构建文件。

setup 只生成文件。以下命令会显式下载 / 安装检查依赖，应在选定的环境中执行，CI 也会执行对应步骤：

```bash
# Python：建议在项目虚拟环境中执行
python3 .setup/check.py deps
# Java：下载固定版本的检查 JAR 到 .setup/tools，需要联网
python3 .setup/check.py tools
```

Python 的默认检查工具固定为 Ruff 0.8.6、pytest 8.3.4、build 1.2.2.post1；已有 Ruff 配置会沿用，否则生成 `.setup/ruff.toml`。Java 使用 google-java-format 1.24.0、Checkstyle 10.20.2，提供基础检查规则，不替代项目自身的所有静态分析。

Python 默认按 requirements.txt 或项目元数据安装项目依赖。检测到 uv / Poetry / Pipenv 锁文件时要求显式提供安装命令，避免绕开已有依赖流程。`python_install` 支持 argv 列表，例如：

```json
{
  "modules": ["lint", "makefile", "ci"],
  "languages": ["python"],
  "python_version": "3.12",
  "python_install": [
    ["python3", "-m", "pip", "install", "uv"],
    ["uv", "export", "--frozen", "--no-dev", "--format", "requirements-txt", "--output-file", ".setup/requirements.txt"],
    ["python3", "-m", "pip", "install", "-r", ".setup/requirements.txt"]
  ]
}
```

也可重复传 `--python-install 'python3 -m pip install -r requirements.txt'`。命令按 argv 执行，不通过 shell；安装命令必须由你提供并与项目流程一致。

### 配置保护和更新

- 已有文件默认保留；有冲突时先显示差异并退出，不写任何模板文件。Skill 安装器自身不提供跨 Skill 的整体回滚。
- `.gitignore` 只维护 `# BEGIN project-setup` 到 `# END project-setup` 的区块，保留区块外内容。管理区块被手动修改时会保护并报告冲突。
- `.setup/state.json` 记录已安装的模块、语言、配置选择、生成文件的 hash 和模板版本；应保留以支持后续更新。
- 已安装模块可通过同样的入口加 `--update` 更新；没有额外选项时复用记录的选择；分次装配的模块与语言会累计保留，避免新增模块破坏已有工作流。模板仅在内容符合上次记录时自动更新；本地改动会显示差异并保留。
- `--force` 显式覆盖冲突配置，原文件先备份到 `.setup/backups/`。模板不会自动删除旧的生成文件；切换语言或模块后不再需要的文件需自行审阅清理。
- Skill 的 `--update` 保留原有整目录替换语义，会覆盖 Skill 内的本地修改，并只处理已安装项；与配置模板保护规则不同。
- gitignore 模块与 Skill 安装器统一忽略所选 Agent 目录；仅安装 Skill 时由独立安装器管理，组合安装时由 gitignore 模块管理。不会删除旧脚本已追加到管理区块外的规则。

本轮未包含编辑规范、开发环境约定、Agent 项目指令、Git hooks、容器与发布流程。


本仓库由 Agent 维护；来源收录、同步、审核和文档更新的规则见
[`AGENTS.md`](AGENTS.md)。本页面向使用者，说明项目 setup 与 Skill 安装方式。

## 收录与更新

每个已镜像的 Skill 都在 [`sources.toml`](sources.toml) 中声明上游来源和本地目录。
同步后实际使用的 commit 或 hash 记录在 [`sources.lock.json`](sources.lock.json)，便于
审核和复现。

如果希望收录新的 Skill，请提供其官方来源链接；维护 Agent 会完成来源核验、同步和安全审核。

## 已收录 Skill

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

因许可证或分发条件无法镜像的推荐项目及其官方安装方式，统一维护在
[`external-skills.md`](external-skills.md)。这些条目不参与本仓库的快速安装、
同步或自动更新。

## 快速开始

在项目根目录执行下面的单行命令，无需克隆本仓库，也无需 Python。安装器会把全部已收录 Skill 分别复制到当前项目的 `.codex/skills` 和 `.agents/skills`：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/install-skills.sh | sh
```

安装器会检查项目根目录的 `.gitignore`：文件不存在时自动创建，并按安装目标补充 `.codex/`、`.agents/`；已有正确规则时不会重复追加。

## 安装选项

免克隆模式可以用 `--only` 只复制指定 Skill：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/install-skills.sh \
  | sh -s -- \
  --repo https://github.com/AK12-Official/set-up \
  --target both --only mattpocock-teach --force
```

免克隆模式默认复制文件，并以 `sources.toml` 中的 Skill ID 作为安装目录名，避免不同来源的同名 Skill 冲突。

`--target` 支持逗号分隔的 `codex`、`antigravity`、`claude`，默认 `codex,antigravity`；旧的 `both` 仍表示 `codex,claude`。使用单个 target 时，还可以通过 `--dest-root` 指定其他安装目录。如果你担心直接执行远程脚本，可以先把 URL 下载到本地，检查后再运行；生产环境还可以把 `main` 换成固定 commit。

openspec 系列 Skill（`fission-ai-openspec-*`）依赖 `openspec` CLI。安装器会在选中这些 Skill 时自动一并安装 CLI：优先使用 `npm`，其次 `pnpm`、`bun`、`yarn` 全局安装 `@fission-ai/openspec`；若 `openspec` 已在 `PATH` 中则跳过。不需要自动安装时可用 `--skip-openspec-cli` 关闭，此时若检测不到 CLI，脚本会提示手动补装：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/install-skills.sh \
  | sh -s -- --skip-openspec-cli
```

## 更新已安装 Skill

在目标项目根目录运行独立更新模式：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/install-skills.sh \
  | sh -s -- --update
```

`--update` 只替换所选目标中已经存在的 Skill 目录，未安装的会跳过；不需要额外传入
`--force`。默认分别检查 Codex 和 Antigravity 的安装目录，因此只安装在一侧的 Skill
不会被自动安装到另一侧。没有已安装项时正常退出并报告更新数为 0。

可组合 `--only ID`（可重复）、`--target`、`--dest-root`、`--repo` 和 `--ref`：

```bash
sh scripts/install-skills.sh --update --target codex --only github-git-commit
```

更新以指定仓库和 ref 的完整目录为准，会覆盖本地修改并清除旧版本已删除的文件；
如需保留自定义内容，请先备份。脚本先复制新文件，再替换原目录；更新模式不会修改
项目 `.gitignore`。仅实际安装或更新 openspec Skill 时才检查其 CLI 依赖。

## 仓库自动同步

`.github/workflows/update-skills.yml` 每周运行一次，也可以手动触发。它会在有变化时创建 Pull Request；工作流不会直接推送到主分支。

## 安全提示

Skill 中的 `SKILL.md` 可能包含会被 Agent 执行的指令。请把新来源视为不可信代码，审核内容、安装脚本和权限要求后再使用。
