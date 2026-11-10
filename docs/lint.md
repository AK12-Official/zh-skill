# 默认 lint 规则与取值依据

本文记录新装配的 Go / Python / Java 检查基线。工具的官方默认值、维护者建议和本仓库的选择是不同层次：启用某项规则不代表它是语言强制标准，也不代表官方建议把所有 linter 全部开启。

规则直接写在 `templates/lint/` 中，由 setup 装配；本地 `make lint` 与 CI 使用同一配置。格式检查与 lint 分开，`make format` 不保证能自动修复长度或复杂度问题。

## Go：长度、复杂度和可读性

保留正确性基线 errcheck、govet、ineffassign、staticcheck、unused、bodyclose、errorlint，并补充下列检查：

| 规则 | 当前设置 | 依据与含义 |
| --- | --- | --- |
| `funlen` | 60 行、40 条语句，忽略注释 | 使用 golangci-lint 文档列出的默认阈值；行数与语句数分别检查，注释不计入行数不代表空行都被忽略 |
| `lll` | 120 列，tab 宽度 1 | 使用该 linter 的默认值，属于仓库行长策略，不是 Go 语言的硬性限制 |
| `gocyclo` | `min-complexity: 15` | 圈复杂度；在工具文档建议的 10–20 区间内选取 15，主要识别路径过多的函数 |
| `gocognit` | `min-complexity: 20` | 认知复杂度；在工具建议的 10–20 区间内选取 20，关注嵌套等理解成本 |
| `nestif` | `min-complexity: 5` | 使用工具默认值，检查 if 嵌套的复杂度分值；**不是简单的“最多五层嵌套”** |
| `nakedret` | `max-func-lines: 30` | 使用工具默认值，超过此长度的函数应显式返回结果，避免长函数中的裸 `return` |
| `nolintlint` | 必须写规则名和原因，不允许无效豁免 | 让例外可审查，不用无差别忽略绕过新规则；具体开关是本仓库选择 |

复杂度取值是对应工具的报告阈值，实际计数按各 linter 定义；圈复杂度、认知复杂度和嵌套复杂度不是同一个指标。

[Go 官方 Code Review Comments](https://go.dev/wiki/CodeReviewComments#line-length) 明确没有硬性行长限制，强调按语义和可读性组织代码，避免为了行宽机械换行。因此 120 列是本仓库方便自动检查的基线，确需长行时应说明语义原因，而不是把 120 宣称为 Go 官方标准。

各项默认值和复杂度推荐区间见 golangci-lint 官方设置页：[funlen](https://golangci-lint.run/docs/linters/configuration/#funlen)、[lll](https://golangci-lint.run/docs/linters/configuration/#lll)、[gocyclo](https://golangci-lint.run/docs/linters/configuration/#gocyclo)、[gocognit](https://golangci-lint.run/docs/linters/configuration/#gocognit)、[nestif](https://golangci-lint.run/docs/linters/configuration/#nestif)、[nakedret](https://golangci-lint.run/docs/linters/configuration/#nakedret)。

### 例外应当局部且可解释

优先拆分职责、用提前返回降低嵌套、按语义组织长表达式。不要为了绕开 funlen 把大量语句挤在一行，也不要为了减少语句数引入更难读的表达式。

协议文本、测试表等确实需要保留时，可以针对具体语句或函数使用局部豁免，例如：

```go
func ProtocolText() string {
    return "...fixed protocol text..." //nolint:lll // Protocol requires a single unbroken line.
}
```

上例展示写法，只有真实超过行长限制时才需要该豁免；否则 `nolintlint` 会报告未生效的指令。不接受省略具体规则的 `//nolint`，也不接受没有原因的 `//nolint:lll`。细节见 [nolintlint 官方说明](https://golangci-lint.run/docs/linters/configuration/#nolintlint)。

当前没有按 `_test.go` 整文件关闭这些新规则，也没有无差别开启全部 linter。测试数据或生成代码的特殊情形，按工具本身的处理规则和必要的局部豁免判断。

## Python：真正检查长行和大函数

| 规则 | 当前设置 | 含义 |
| --- | --- | --- |
| `E501` | 88 字符 | 启用超长行检查，与已有 Ruff formatter 的 88 字符目标一致 |
| `PLR0915` | 50 条语句 | 约束函数 / 方法的语句数；这不是物理行数限制 |
| `C901` | 圈复杂度 10 | 检查分支路径造成的复杂度 |
| `PLR0912` | 12 个分支 | 检查函数分支数量，包括 if / elif / else 等结构 |

保留原有 E4、E7、E9、F、I 检查。88 是 Ruff 为兼容 Black / formatter 采用的默认值，不是把 PEP 8 的 79 字符建议改写为 88。E501 会按工具规则豁免单个不可拆分的词、符合条件的 URL 等，不是所有字符串都一定会被自动截断。

物理行数很长但语句数少的 Python 函数，不会仅因 PLR0915 就被拦截；不能把此规则描述为“函数最多 50 行”。

依据见 Ruff 官方：[E501](https://docs.astral.sh/ruff/rules/line-too-long/)、[PLR0915](https://docs.astral.sh/ruff/rules/too-many-statements/)、[C901](https://docs.astral.sh/ruff/rules/complex-structure/)、[PLR0912](https://docs.astral.sh/ruff/rules/too-many-branches/)。

## Java：补齐尺寸与结构检查

| Checkstyle 检查 | 当前设置 | 依据与选择 |
| --- | --- | --- |
| `LineLength` | 100 字符，忽略 package / import 声明 | 与当前 google-java-format 和 Google Java Style 的列宽基线一致；不是 Checkstyle 默认的 80 |
| `MethodLength` | 150 行，`countEmpty=false` | 150 采用工具默认值；不计空行和注释是仓库选择，覆盖方法及构造器 |
| `CyclomaticComplexity` | 10 | 使用工具默认上限，复杂度反映测试路径数量，不能单凭分值判断全部代码质量 |
| `NestedIfDepth` | 3 | 仓库选择，避免默认深度 1 对普通分支过严；它不同于 Go nestif 的复杂度分数 |

保留 AvoidStarImport、EmptyStatement、EqualsHashCode、OneStatementPerLine。LineLength 必须位于 Checker 下，方法长度、复杂度和嵌套深度位于 TreeWalker 下。

这是一套基线，不是完整实现 Google Java Style 的每一个例外：例如某些长 URL 或不可拆分文本仍可能需要项目级调整，formatter 也不保证消除所有 LineLength 报告。

依据见 [Google Java Style 列宽](https://google.github.io/styleguide/javaguide.html#s4.4-column-limit) 和 Checkstyle 官方：[LineLength](https://checkstyle.org/checks/sizes/linelength.html)、[MethodLength](https://checkstyle.org/checks/sizes/methodlength.html)、[CyclomaticComplexity](https://checkstyle.org/checks/metrics/cyclomaticcomplexity.html)、[NestedIfDepth](https://checkstyle.org/checks/coding/nestedifdepth.html)。

## 安装、更新与已有配置

- 新项目选择 lint、Makefile 或 CI 任一检查模块时，按语言装配所需配置；不用单独再开启这些规则。
- 已有项目模式仍是 Skill only，本次调整不会让它自动生成工程 lint。
- 已有 Ruff 配置和其他支持格式的 golangci-lint 配置仍按原逻辑沿用，不把仓库规则强塞进用户自己的配置。
- 已经由 set-up 管理的模板，使用工程模板 `--update` 迁移；本地已修改的配置仍受 hash 保护，不自动强制覆盖。用法见[更新与冲突处理](setup.md#更新与冲突处理)。
- 当前模板版本为 4。修改策略时应同步文档和行为验证；改变阈值不需要换一个语言运行时，也不应无故升级全部检查工具。

## 验证方式

`tests/test_lint_templates.py` 在临时项目中调用 setup 生成实际配置，用可读示例验证成功，并用超长行、超长函数 / 语句过多、复杂分支和深层嵌套示例验证非零退出及对应规则报告。Go 还验证带理由的局部豁免能通过，无理由的豁免不能通过。

测试需要 Go / golangci-lint、Ruff 0.8.6、Java 和 Checkstyle 10.20.2。可通过 `SETUP_TEST_RUFF` 指定 Ruff 可执行文件，通过 `SETUP_TEST_CHECKSTYLE_JAR` 指定检查 JAR。缺少工具时相关测试跳过；仓库 CI 显式准备这些工具，不能把本地跳过表述为规则已运行通过。
