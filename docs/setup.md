# setup 使用手册

人类快速配置见 [README](../README.md)，其他项目中的 Agent 可只读[项目 Agent 指南](agent-setup.md)。本页记录参数和技术行为；维护本仓库的规则在 [AGENTS.md](../AGENTS.md)。

## 入口和运行环境

在已存在的项目根目录执行远程入口：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh | sh
```

需要 curl、tar、Python 3.11+。引导器下载 GitHub 归档到临时目录并调用 Python 入口，不执行 Git clone，不创建目标目录。终端交互使用标准输入或 `/dev/tty`；无交互终端且没有参数、配置记录指定模式时默认 existing。

本地未发布改动使用本地入口，`--project` 指向已存在的目标目录，不要误在工具仓库中执行初始化：

```bash
python3 /path/to/set-up/scripts/setup.py --project /path/to/project \
  --mode new --language go --non-interactive --dry-run
```

移除 `--dry-run` 执行。只有不选择 Skill 模块的本地 Python 入口才能完全离线；远程引导器和 Skill 安装都会下载归档。统一入口的 Skill dry-run 只列出目标和 ID，不拉取或核实远端 Skill。

## 模式和参数

| 参数 | 行为 |
| --- | --- |
| `--mode new` | 默认 `skills,gitignore,lint,makefile,ci`；首次执行可初始化 Git |
| `--mode existing` | 默认仅 `skills`；不允许指定工程配置模块，不初始化 Git |
| `--project DIR` | 目标目录，默认当前目录，必须已存在 |
| `--language go,python,java` | 显式选择语言，支持组合；配置文件对应键为 `languages` |
| `--agents codex,antigravity,claude` | Skill 目标，默认 Codex + Antigravity |
| `--only ID` | 筛选 Skill，可重复传入 |
| `--modules LIST` | 选择模块，可独立执行；已有工程仅需加 AI 时仍使用 existing |
| `--go-version` / `--python-version` / `--java-version` | 覆盖 CI 运行版本 |
| `--java-build maven` 或 `gradle` | 指定 Java 构建工具 |
| `--config FILE` | 指定个人 JSON 配置 |
| `--python-install COMMAND` | Python 依赖安装 argv 字符串，可重复传入，不经 shell 执行 |
| `--non-interactive` / `--interactive` | 禁止询问 / 显式从标准输入询问 |
| `--dry-run` | 显示文件计划、差异及 Skill 选择，不写项目文件或安装依赖 |
| `--update` | 更新已装配内容，详见下文；仅更新 Skill 时搭配 existing |
| `--force` | 显式覆盖冲突模板并备份；Skill 保持整目录替换语义 |
| `--repo URL` / `--ref REF` | 传给 Skill 安装器的 GitHub 来源，默认 set-up / main |

以 `python3 scripts/setup.py --help` 为完整参数入口。显式传 `--modules` 而未指定 mode 时，包含工程配置模块则视为 new；只有 skills 则视为 existing。

语言辅助识别使用项目根目录的 go.mod / go.work、Python 项目文件、pom.xml / build.gradle(.kts)。new 交互流程询问语言和缺失版本；非交互需传语言或存在可识别文件。不会生成语言项目骨架，也不安装工具链。

CI 版本优先取显式参数，其次读取 Go 的 go.work / go.mod、Python 的 `.python-version`、Java 的 `.java-version` 或 Maven 常见版本属性。new 引导流程缺失时使用 Go 1.25、Python 3.12、Java 21；独立指定 CI 模块而不能确定版本时会报错。Java 空项目默认 Maven；已有项目的构建工具不能明确判定时要求显式选择。

## 选择 Agent 和 Skill

```bash
# 给已有项目配置 Claude 的一个 Skill
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh \
  | sh -s -- --mode existing --agents claude --only github-git-commit

# 更新 Codex 和 Antigravity 已安装的 Skill
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh \
  | sh -s -- --mode existing --agents codex,antigravity --update
```

| Agent | 项目级目录 |
| --- | --- |
| Codex | `.codex/skills/<ID>/` |
| Antigravity | `.agents/skills/<ID>/` |
| Claude Code | `.claude/skills/<ID>/` |

安装目录名使用 `sources.toml` 的 ID，复制完整 Skill 目录和资源。外部索引不参与安装。Antigravity 目录依据[官方文档](https://antigravity.google/docs/skills)。

## 个人配置与来源固定

默认读取 `~/.config/project-setup/config.json`，优先级为：命令行 > 个人配置 > 更新时记录的选项 > 检测和默认值。

```json
{
  "mode": "new",
  "languages": ["go"],
  "modules": ["skills", "gitignore", "lint", "makefile", "ci"],
  "agents": ["codex", "antigravity"],
  "go_version": "1.25"
}
```

可配置键限于 mode、modules、languages、agents、java_build、三个 `*_version` 和 python_install。明确 existing 且没有显式指定 modules 时忽略配置文件中的工程模块选择；显式指定不兼容模块会报错。

远程引导器来源由 `SETUP_REPO=owner/repo` 和 `SETUP_REF=tag-or-commit` 控制。固定版本时，下载脚本的 URL 和 `SETUP_REF` 应选同一 ref：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/COMMIT/scripts/setup.sh \
  | SETUP_REF=COMMIT sh -s -- --mode existing
```

`--repo` / `--ref` 只控制 Skill 下载，不能替代引导器的来源变量。临时源码下载完成并执行后会清理。

## 生成文件与检查工具

| 模块 | 生成内容 |
| --- | --- |
| gitignore | `.gitignore` 管理区块，组合通用、语言和 Agent 目录规则 |
| lint | 共用检查入口、配置及语言 lint 配置 |
| makefile | 根目录 Makefile，调用共用检查入口 |
| ci | `.github/workflows/setup-<language>.yml`，在 push / pull_request 时检查，只读仓库权限 |

lint / makefile / ci 任一模块均会生成 `.setup/check.py`、`.setup/checks.json` 及所需检查配置。工程模板状态保存在 `.setup/state.json`。多次装配会累计记录模块和语言；不会自动删除旧生成文件。

| 语言 | 默认检查工具与配置 |
| --- | --- |
| Go | gofmt；golangci-lint 2.13.2，生成 `.golangci.yml`；测试和构建调用 Go |
| Python | Ruff 0.8.6、pytest 8.3.4、build 1.2.2.post1；无已有 Ruff 配置时生成 `.setup/ruff.toml` |
| Java | google-java-format 1.24.0、Checkstyle 10.20.2；生成 `.setup/checkstyle.xml`，复用 Maven / Gradle 构建 |

Go 默认启用 errcheck、govet、ineffassign、staticcheck、unused、bodyclose、errorlint、nolintlint。已有 `.golangci.yml` 按模板冲突规则处理；已有 `.golangci.yaml` / `.toml` / `.json` 时直接沿用。支持项目目录内的 go.work 模块，拒绝指向项目外部的模块。

## 本地检查

面向 Linux / macOS 与 Ubuntu CI，需要 Python 3.11+，使用 Makefile 时还需 Make。Java 检查工具要求 JDK 17+。

```bash
make help
make format                    # 修改源码格式
make check                     # 格式检查、lint、测试、构建
make check SETUP_LANGUAGE=go    # 多语言项目只检查一种
python3 .setup/check.py check   # 不使用 Make
```

Go 本地需安装 Go 和 golangci-lint v2，建议与 CI 的 2.13.2 一致，见[官方安装说明](https://golangci-lint.run/docs/welcome/install/local/)。CI 的官方 lint Action 仅安装工具，再交给共用命令执行检查。

Python 在项目选定环境中显式执行 `python3 .setup/check.py deps` 安装项目和检查依赖；无包元数据时跳过构建，无测试时保留 pytest 的非零退出码。

Java 显式执行 `python3 .setup/check.py tools`，将固定版本检查 JAR 下载到 `.setup/tools/`；构建优先用项目 wrapper，否则调用系统 mvn / gradle。不会重写 pom.xml 或 Gradle 构建文件。

统一 setup 不自动安装 OpenSpec CLI，相关 Skill 需要时按输出提示自行补装。安装成功不代表目标项目检查或远程 CI 已成功。

## Python 依赖安装

默认按 requirements.txt 或包元数据安装。检测到 uv / Poetry / Pipenv 锁文件时，要求显式提供与原有流程一致的安装命令；setup 不执行这些命令，只有生成的 `deps` 命令及 CI 会执行。

例如在 `--config` 文件中指定：

```json
{
  "mode": "new",
  "languages": ["python"],
  "python_version": "3.12",
  "python_install": [
    ["python3", "-m", "pip", "install", "uv"],
    ["uv", "export", "--frozen", "--no-dev", "--format", "requirements-txt", "--output-file", ".setup/requirements.txt"],
    ["python3", "-m", "pip", "install", "-r", ".setup/requirements.txt"]
  ]
}
```

也可重复传 `--python-install 'python3 -m pip install -r requirements.txt'`。argv 不经 shell，不能直接写管道或 shell 重定向。示例仅供适配项目约定，不替代用户选择依赖管理方式。

## 更新与冲突处理

**仅更新 Skill**：使用 README 的 `--mode existing --update`。只替换所选目标中已安装的条目，清除旧版本已删除的文件并覆盖本地 Skill 修改；未安装项跳过，0 项正常退出。不会改工程模板。

**更新工程模板**：显式选择工程模块，避免意外安装 Skill。例如在本地入口执行：

```bash
python3 /path/to/set-up/scripts/setup.py --project /path/to/project \
  --mode new --modules gitignore,lint,makefile,ci --language go \
  --non-interactive --update --dry-run
```

确认后移除 `--dry-run`。不指定 mode 和 modules 的裸 `--update` 会按个人配置及装配记录决定范围，可能包含 Skill 和工程模板；仅更新 Skill 时不要使用它。

- 模板已有内容不同则默认报冲突并显示差异；预检发现冲突时不写模板文件。
- `--update` 可替换 hash 与上次记录一致的模板，本地改动会被保护。不要删除 `.setup/state.json` 后期待自动识别所有权。
- `--force` 才覆盖冲突配置，原文件先备份到 `.setup/backups/`。Skill 的 force / update 目录替换不享有模板备份规则。
- `.gitignore` 只维护 `# BEGIN project-setup` 到 `# END project-setup` 区块；区块外内容保留，手动修改管理区块也会检测冲突。
- Skill only 安装时由独立安装器补充 Agent 忽略规则；组合安装时由 gitignore 模块管理。旧脚本写在区块外的规则不会自动删除。
- 更新不初始化 Git；没有自动提交、设置 remote 或全流程回滚。多个 Skill 安装失败前可能已有条目成功，按输出核对结果。

## 独立 Skill 安装器

保留原有免 Python 的 POSIX shell 入口，只安装 Skill，不配置工程模板：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/install-skills.sh \
  | sh -s -- --target codex,antigravity --only github-git-commit
```

`--update` 仅更新已安装项；`--target` 支持 codex、antigravity、claude 的逗号组合，默认 codex,antigravity。旧 `both` 始终表示 codex,claude；它不是当前默认组合。

单个 target 可搭配 `--dest-root DIR` 自定义路径。`--repo` / `--ref` 控制来源，`--only` 可重复，`--force` 覆盖已有目录，`--dry-run` 下载归档后预览但不修改目标项目。

与统一入口不同，独立安装器在实际安装 OpenSpec Skill 时默认尝试全局安装 OpenSpec CLI，可用 `--skip-openspec-cli` 关闭。独立安装器的更新不修改项目 `.gitignore`，不记录统一 setup 的状态。
