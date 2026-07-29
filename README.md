# zh-skill

收集、同步和审核来自不同来源的 Agent Skills。

仓库默认由 Agent 代为维护。Agent 的完整操作流程见 [`AGENTS.md`](AGENTS.md)。

## 工作方式

每个外部 Skill 都在 [`sources.toml`](sources.toml) 中声明来源和目标目录。运行同步脚本时：

1. 拉取上游 Git 仓库，或下载 ZIP 文件；
2. 只导入声明的目录；
3. 将实际 commit/hash 写入 [`sources.lock.json`](sources.lock.json)；
4. 把同步结果作为普通 Git diff 审核后提交。

同步得到的目录是生成内容，请不要直接在 `skills/` 下修改上游文件。需要本地调整时，把补丁放在 `patches/`，或者新增一个自己的来源条目。

## 已收录 Skill

| ID | 本地目录 | 许可证 |
| --- | --- | --- |
| `mattpocock-teach` | `skills/mattpocock/teach` | MIT |
| `mattpocock-handoff` | `skills/mattpocock/handoff` | MIT |
| `sanyuan0704-code-review-expert` | `skills/sanyuan0704/code-review-expert` | MIT |
| `nextlevelbuilder-ui-ux-pro-max` | `skills/nextlevelbuilder/ui-ux-pro-max` | MIT |
| `chyiiiiiiiiiiii-openspec-proposal` | `skills/chyiiiiiiiiiiii/openspec-proposal` | MIT |
| `chyiiiiiiiiiiii-openspec-apply` | `skills/chyiiiiiiiiiiii/openspec-apply` | MIT |
| `chyiiiiiiiiiiii-openspec-archive` | `skills/chyiiiiiiiiiiii/openspec-archive` | MIT |

## 快速开始

在项目根目录执行下面的单行命令，无需克隆本仓库。安装器会把全部 Skill 分别复制到当前项目的 `.codex/skills` 和 `.claude/skills`：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.py | python3 - --repo https://github.com/AK12-Official/zh-skill --target both --force
```

安装器会检查项目根目录的 `.gitignore`：文件不存在时自动创建，并按安装目标补充 `.codex/`、`.claude/`；已有正确规则时不会重复追加。

## 安装选项

本机已经克隆这个仓库时，在目标项目根目录执行安装器。默认把 Skill 链接到该项目的 `.codex/skills` 和 `.claude/skills`：

```bash
python3 /path/to/zh-skill/scripts/install-skills.py \
  --target both --only mattpocock-teach --force
```

本地模式默认使用符号链接，因此更新本仓库后，项目会看到新版本。若系统不适合使用符号链接，改用复制：

```bash
python3 /path/to/zh-skill/scripts/install-skills.py \
  --target both --mode copy --force
```

免克隆模式可以用 `--only` 只复制指定 Skill：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.py \
  | python3 - \
  --repo https://github.com/AK12-Official/zh-skill \
  --target both --only mattpocock-teach --force
```

没有 Python 时，使用行为一致的纯 shell 安装器：

```bash
curl -fsSL https://raw.githubusercontent.com/AK12-Official/zh-skill/main/scripts/install-skills.sh \
  | sh -s -- --repo https://github.com/AK12-Official/zh-skill \
  --target both --only mattpocock-teach --force
```

免克隆模式默认复制文件，并以 `sources.toml` 中的 Skill ID 作为安装目录名，避免不同来源的同名 Skill 冲突。

`--target` 可设为 `codex`、`claude` 或 `both`。使用单个 target 时，还可以通过 `--dest-root` 指定其他安装目录。如果你担心直接执行远程脚本，可以先把 URL 下载到本地，检查后再运行；生产环境还可以把 `main` 换成固定 commit。

也可以只同步一个来源：

```bash
python3 scripts/sync-skills.py --only mattpocock-teach
```

脚本默认只更新 `skills/` 下由来源清单管理的目录，并会拒绝越出仓库根目录的路径。

## 添加来源

编辑 `sources.toml`。Git 来源示例：

```toml
[[sources]]
id = "publisher-skill"
kind = "git"
repo = "https://github.com/publisher/repository.git"
ref = "main"
path = "skills/example"
dest = "skills/publisher/example"
license = "Apache-2.0"
```

ZIP 来源示例：

```toml
[[sources]]
id = "downloaded-skill"
kind = "zip"
url = "https://example.com/skill.zip"
sha256 = "<64 位十六进制 SHA-256>"
path = "skill"
dest = "skills/vendor/downloaded-skill"
license = "MIT"
```

提交来源时请同时记录许可证和原始地址。更新上游后，先查看 diff，再提交新的 lock 文件。

## 自动更新

`.github/workflows/update-skills.yml` 每周运行一次，也可以手动触发。它会在有变化时创建 Pull Request；工作流不会直接推送到主分支。

## 安全提示

Skill 中的 `SKILL.md` 可能包含会被 Agent 执行的指令。请把新来源视为不可信代码，审核内容、安装脚本和权限要求后再使用。
