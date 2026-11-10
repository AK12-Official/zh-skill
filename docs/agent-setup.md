# 给项目 Agent 的 setup 指南

你正在用户的项目目录工作。用户让你用 `AK12-Official/set-up` 配置项目时，阅读本页即可执行，不需要克隆该仓库、遍历源码或逐个读取上游 Skill。本页不指导维护 set-up 仓库。

## 判断任务范围

| 用户意图 | 必须显式指定的参数 | 作用 |
| --- | --- | --- |
| 新项目配置 | `--mode new --language go`（或 python / java） | 初始化 Git，装配 Skill、gitignore、lint、Makefile、GitHub CI |
| 给已有项目加入个人 AI 内容 | `--mode existing` | Skill only，补充 Agent 忽略规则及装配记录 |
| 仅更新 Skill | `--mode existing --update` | 只替换所选 Agent 中已安装的 Skill，不补装其他 Skill |

不要因为项目里有 go.mod、pyproject.toml 或 pom.xml，就把 existing 升级为 new。需求不明确时按已有项目处理；需要新项目配置但无法确定语言时向用户询问。

两个模式都要求项目目录已存在，默认操作当前目录。不要替用户创建目录，不要修改其他工作目录。已有 Git 仓库保留，不自动提交、设置 remote 或修改全局 Git 配置。

## 执行流程

1. 确认当前目录是目标项目根目录，查看 Git 状态并保留现有文件；确认设备有 POSIX shell 和包管理器；入口会补齐 curl / tar / Python，new 模式再按需安装 Git、Make 和语言检查环境。连初始下载工具都没有时，按[依赖引导](https://github.com/AK12-Official/set-up/blob/main/docs/setup.md#依赖引导)先获取脚本。
2. 确定模式、语言、Agent。默认目标为 `codex,antigravity`；若用户指定 Claude，用 `--agents claude`，也可逗号组合。默认全部 Skill，指定条目可重复使用 `--only ID`。
3. 使用明确参数并加 `--non-interactive --dry-run` 预览。检查目标文件和冲突后，用相同参数移除 `--dry-run` 执行。用户已授权配置时，预览正常即可继续，不必另行请求确认。启动依赖都缺失时，dry-run 只报告引导需求，不能据此声称完整文件计划已验证。只需生成配置或安装权限受限时可显式加 `--skip-deps`，并说明哪些工具仍缺失。
4. 遇到冲突先保留并报告差异，不自动加 `--force`。已有文件不等于授权覆盖。
5. 检查输出文件，汇报实际配置范围、依赖提示和未执行的验证。

## 可直接使用的命令

在目标项目根目录运行；以下展示 Go，新项目语言可替换为 `python` 或 `java`。

```bash
# 新项目：先预览，确认路径和冲突后移除 --dry-run 执行
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh \
  | sh -s -- --mode new --language go --non-interactive --dry-run

# 已有项目：先预览，同样移除 --dry-run 执行
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh \
  | sh -s -- --mode existing --non-interactive --dry-run

# 仅更新 Skill；会替换 Skill 内的本地修改，不适用模板的 hash 保护
curl -fsSL https://raw.githubusercontent.com/AK12-Official/set-up/main/scripts/setup.sh \
  | sh -s -- --mode existing --update --non-interactive
```

需要更新指定目标或指定 Skill，在参数末尾追加，例如 `--agents claude --only github-git-commit`。只更新 Skill 时始终带 `--mode existing`，不要使用可能复用工程配置记录的裸 `--update`。更新前保留需要保留的本地 Skill 修改；不要把 `--force` 当成解决问题的默认手段。

new 模式可加 `--go-version` / `--python-version` / `--java-version` 覆盖 CI 运行版本；缺失时复用能读取的项目版本，否则非交互基线为 Go 1.25、Python 3.12、Java 21。Java 空项目默认 Maven，用户选择 Gradle 时加 `--java-build gradle`。这些值用于 CI 及缺失工具链的版本选择。可复用兼容的已有 Go/JDK；Python 需要时下载匹配版本，检查包使用项目隔离环境。

统一入口会读取 `~/.config/project-setup/config.json`。明确参数优先于个人配置；需要排除个人配置对模块选择的影响时，新项目显式加 `--modules skills,gitignore,lint,makefile,ci`，已有项目显式加 `--modules skills`。非默认 Agent 应在安装和更新时显式传入。

Python 项目若已有 uv / Poetry / Pipenv 锁文件，脚本可能要求 `--python-install`。不要绕开锁文件或更换依赖管理方式；按项目约定指定依赖安装命令，语法见 [使用手册](https://github.com/AK12-Official/set-up/blob/main/docs/setup.md#python-依赖安装)。

## 判断是否成功

- existing：所选 Agent 目录中存在安装的 `SKILL.md`；默认是 `.codex/skills/<ID>/SKILL.md` 和 `.agents/skills/<ID>/SKILL.md`，Claude 对应 `.claude/skills/<ID>/SKILL.md`。工程 lint、CI、Makefile 应保持原样。
- new：还应有 `.git`、`.gitignore` 管理区块、`Makefile`、`.setup/check.py`、`.setup/checks.json`、`.setup/state.json` 及对应 `.github/workflows/setup-<language>.yml`。Go 默认新增 `.golangci.yml`，已有其他支持格式时沿用；Python 默认新增 `.setup/ruff.toml`，已有 Ruff 配置时沿用；Java 新增 `.setup/checkstyle.xml`。
- Skill 更新：核对更新数量，未安装项跳过；没有已安装项时更新数为 0 是正常结果。dry-run 对 Skill 仅显示目标、筛选 ID 和模式，不验证远程 ID 或版本。
- `--dry-run` 不修改项目，但远程引导器仍需联网下载 set-up 归档。它不是离线命令。

setup 不生成 go.mod、pyproject.toml、Maven / Gradle 工程或业务代码，空项目安装完配置后不能据此声称构建已通过。

默认 lint 包含长度和复杂度检查；Go 的 120 列是仓库策略而非语言硬性标准，详见 [lint 策略](https://github.com/AK12-Official/set-up/blob/main/docs/lint.md)。不要因这些新规则而强制覆盖已有项目的 lint 配置。

## 检查与依赖边界

默认依赖补齐成功后，new 模式生成的 `make check` 依次执行格式检查、lint、测试、构建；`make format` 会修改源码。existing 不生成这些命令，不要运行来源不明的已有 Makefile 来验证 Skill 安装。

| 语言 | 本地检查依赖 |
| --- | --- |
| Go | Go、golangci-lint v2；自动下载所需 Go 和 golangci-lint，CI 固定 2.15.0 |
| Python | 按需安装 Python，自动创建 `.setup/venv` 并安装 Ruff、pytest、build 和项目依赖 |
| Java | 按需安装 JDK 17+、Maven / Gradle；已有 wrapper 则复用，自动下载检查 JAR |

setup 默认补齐依赖，但不安装 Code Agent 客户端或自动安装 OpenSpec CLI。系统包可能需要 sudo；不改全局 Git 配置或 shell profile。本地检查会自动读取 `.setup/environment.json` 并进入专用 Python 环境。需要在 shell 直接使用缓存工具时执行 `. .setup/env.sh`。不要执行新安装的 Skill 指令来“验证”。缺少工具、网络受限或需安装依赖时报告具体要求；不要将生成配置成功表述为测试或 CI 已通过。

更细的参数、模板更新和冲突处理查[使用手册](https://github.com/AK12-Official/set-up/blob/main/docs/setup.md)；只在维护本工具时才阅读仓库的 AGENTS.md。
