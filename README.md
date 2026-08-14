# zh-skill

收集并分发来自不同来源的 Agent Skills。

本仓库由 Agent 维护；来源收录、同步、审核和文档更新的规则见
[`AGENTS.md`](AGENTS.md)。本页面向使用者，说明已收录内容和安装方式。

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
| `samber-golang-benchmark` | `skills/samber/golang-benchmark` | MIT |
| `samber-golang-cli` | `skills/samber/golang-cli` | MIT |
| `samber-golang-code-style` | `skills/samber/golang-code-style` | MIT |
| `samber-golang-concurrency` | `skills/samber/golang-concurrency` | MIT |
| `samber-golang-context` | `skills/samber/golang-context` | MIT |
| `samber-golang-continuous-integration` | `skills/samber/golang-continuous-integration` | MIT |
| `samber-golang-data-structures` | `skills/samber/golang-data-structures` | MIT |
| `samber-golang-database` | `skills/samber/golang-database` | MIT |
| `samber-golang-dependency-injection` | `skills/samber/golang-dependency-injection` | MIT |
| `samber-golang-dependency-management` | `skills/samber/golang-dependency-management` | MIT |
| `samber-golang-design-patterns` | `skills/samber/golang-design-patterns` | MIT |
| `samber-golang-documentation` | `skills/samber/golang-documentation` | MIT |
| `samber-golang-error-handling` | `skills/samber/golang-error-handling` | MIT |
| `samber-golang-gopls` | `skills/samber/golang-gopls` | MIT |
| `samber-golang-how-to` | `skills/samber/golang-how-to` | MIT |
| `samber-golang-lint` | `skills/samber/golang-lint` | MIT |
| `samber-golang-modernize` | `skills/samber/golang-modernize` | MIT |
| `samber-golang-naming` | `skills/samber/golang-naming` | MIT |
| `samber-golang-observability` | `skills/samber/golang-observability` | MIT |
| `samber-golang-performance` | `skills/samber/golang-performance` | MIT |
| `samber-golang-pkg-go-dev` | `skills/samber/golang-pkg-go-dev` | MIT |
| `samber-golang-popular-libraries` | `skills/samber/golang-popular-libraries` | MIT |
| `samber-golang-project-layout` | `skills/samber/golang-project-layout` | MIT |
| `samber-golang-refactoring` | `skills/samber/golang-refactoring` | MIT |
| `samber-golang-safety` | `skills/samber/golang-safety` | MIT |
| `samber-golang-security` | `skills/samber/golang-security` | MIT |
| `samber-golang-structs-interfaces` | `skills/samber/golang-structs-interfaces` | MIT |
| `samber-golang-testing` | `skills/samber/golang-testing` | MIT |
| `samber-golang-troubleshooting` | `skills/samber/golang-troubleshooting` | MIT |
| `samber-golang-stay-updated` | `skills/samber/golang-stay-updated` | MIT |

因许可证或分发条件无法镜像的推荐项目及其官方安装方式，统一维护在
[`external-skills.md`](external-skills.md)。这些条目不参与本仓库的快速安装、
同步或自动更新。

## 快速开始

在项目根目录执行下面的单行命令，无需克隆本仓库，也无需 Python。安装器会把全部已收录 Skill 分别复制到当前项目的 `.codex/skills` 和 `.claude/skills`：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.sh | sh
```

安装器会检查项目根目录的 `.gitignore`：文件不存在时自动创建，并按安装目标补充 `.codex/`、`.claude/`；已有正确规则时不会重复追加。

## 安装选项

免克隆模式可以用 `--only` 只复制指定 Skill：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.sh \
  | sh -s -- \
  --repo https://github.com/AK12-Official/zh-skill \
  --target both --only mattpocock-teach --force
```

免克隆模式默认复制文件，并以 `sources.toml` 中的 Skill ID 作为安装目录名，避免不同来源的同名 Skill 冲突。

`--target` 可设为 `codex`、`claude` 或 `both`。使用单个 target 时，还可以通过 `--dest-root` 指定其他安装目录。如果你担心直接执行远程脚本，可以先把 URL 下载到本地，检查后再运行；生产环境还可以把 `main` 换成固定 commit。

openspec 系列 Skill（`fission-ai-openspec-*`）依赖 `openspec` CLI。安装器会在选中这些 Skill 时自动一并安装 CLI：优先使用 `npm`，其次 `pnpm`、`bun`、`yarn` 全局安装 `@fission-ai/openspec`；若 `openspec` 已在 `PATH` 中则跳过。不需要自动安装时可用 `--skip-openspec-cli` 关闭，此时若检测不到 CLI，脚本会提示手动补装：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.sh \
  | sh -s -- --skip-openspec-cli
```

## 自动更新

`.github/workflows/update-skills.yml` 每周运行一次，也可以手动触发。它会在有变化时创建 Pull Request；工作流不会直接推送到主分支。

## 安全提示

Skill 中的 `SKILL.md` 可能包含会被 Agent 执行的指令。请把新来源视为不可信代码，审核内容、安装脚本和权限要求后再使用。
