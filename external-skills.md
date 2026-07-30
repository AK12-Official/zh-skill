# 外部 Skill 索引

本文件登记值得关注、但因许可证或分发条件不适合镜像到本仓库的
Skill。这里的条目仅用于来源发现：

- 不写入 `sources.toml`；
- 不参与同步、安装或自动更新；
- 不在本仓库保存 `SKILL.md`、ZIP、Git submodule 或其他上游副本；
- 每个条目应提供上游官方安装命令；没有官方安装方式时须明确说明；
- 使用前请自行阅读并遵守上游的最新许可证和服务条款。

## Anthropic PPTX

| 项目 | 内容 |
| --- | --- |
| 名称 | `pptx` |
| 官方仓库 | <https://github.com/anthropics/skills> |
| 来源目录 | <https://github.com/anthropics/skills/tree/main/skills/pptx> |
| 默认分支 | `main` |
| 许可证文件 | <https://github.com/anthropics/skills/blob/main/skills/pptx/LICENSE.txt> |
| 收录状态 | 仅外部索引，不镜像 |
| 最后核验 | 2026-07-30 |

### 未镜像原因

该目录使用 Anthropic 专属许可，而不是仓库中部分示例 Skill 使用的
Apache-2.0。许可证包含禁止在 Anthropic 服务外保留副本、复制、创建衍生作品
和向第三方分发等限制，因此本仓库不下载、同步或重新分发该目录。

如需使用，请通过 Anthropic 提供的官方渠道，并以许可证文件和适用的
Anthropic 服务协议的最新版本为准。

### 官方安装方式

在 Claude Code 中执行：

```text
/plugin marketplace add anthropics/skills
/plugin install document-skills@anthropic-agent-skills
```

该命令安装 Anthropic 官方的 `document-skills` 插件组，其中包含 `pptx`，
而不是通过本仓库单独下载或分发该 Skill。
