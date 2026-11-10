---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。Codex 只讲清楚目标、边界和验收条件，由 AGY 自主完成阅读、编码与测试闭环，Codex 静默等待并集中终验。
---

# 调用 AGY

## 核心原则

**不要把 AGY 当傻子，Codex 不要过度限制，也不要过度指导。**
本机 `~/.gemini/antigravity-cli/settings.json` 已全局配置完整权限（`"toolPermission": "always-proceed"`, `"allowNonWorkspaceAccess": true`, `"enableTerminalSandbox": false`）。Codex 的职责是讲清楚**要实现什么目标、不能破坏什么边界、怎么算验收通过**，把执行自主权交给 AGY，并管住自己的唤醒消耗：

- **委托前**：
  - Codex 明确业务目标、必要设计、不可变边界和验收条件，不替 AGY 全量预读源码，也不在提示词里教 AGY 怎么调工具。
  - **基线快照保护**：若工作区存在未提交改动，委托前先做好快照备份；后续若需回滚，**只能依据委托前快照恢复**，严禁直接执行 `git checkout/restore/reset/clean` 恢复到 `git HEAD` 而误删前序未提交成果。
- **执行中（严控 Codex 唤醒）**：
  - 单层直派单个 AGY 会话，由 AGY 自主完成阅读、编码、运行构建/测试与编译报错自修复。
  - **长等待与纯续等铁律**：启动 `agy` 及后续 `write_stdin` 均拉满工具侧等待上限（`yield_time_ms`）。若单次等待达上限时进程仍未退出，**下一轮只允许纯粹继续等待原进程**，严禁在等待中途顺手执行 `git diff`/`git status`、严禁读取 `~/.gemini/` 内部日志、严禁按读取次数或耗时发消息催写。
- **交付后（完成判定与集中终验）**：
  - 从 `--output-format json` 返回结果中提取并保存 `conversation_id`，同时检查进程退出码、`status`、`stderr` 及 `denied_actions`（不能仅凭退出码 `0` 认定完成）。
  - AGY 自测通过返回后，Codex 集中审查 `git diff` 并做独立验证；若仍有遗漏问题，一次性汇总交回 AGY。
- **职责红线与阻塞处理**：
  - **生产代码、测试代码与实现配置始终由 AGY 修改**：若验证失败或遇到环境阻塞，Codex 负责排查外部阻塞或汇总问题后继续委托 AGY，**Codex 绝不亲自下场改业务代码**。
  - **AGY 不擅改方向**：AGY 遇到需变更技术方案、突破不可变边界或扩大修改范围的问题时，停止试错并交回 Codex 决策。

---

## 流程与命令

### 1. 可行性评估（仅复杂方案按需触发）

常规任务或边界清晰的需求，确认目标后直接进入实施。仅当涉及复杂架构、跨服务契约或状态机改造时，请 AGY 做单轮只读评估。

- `agy` 的 `--mode plan` 在底层会自动注入 `/plan` 宏，因此只读评估统一使用 `--mode accept-edits --disable-slash-commands`，并仅通过 `--settings` 禁止文件写入与破坏性命令（保留完整的代码读取、内置 `ripgrep` 搜索与只读 Git 检索能力）：

```bash
agy --project '<项目ID>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands \
  --settings '{"permissions":{"deny":["write_file(*)","command(rm*)","command(git reset*)","command(git checkout*)","command(git restore*)","command(git clean*)","command(git commit*)","command(git push*)"]}}' \
  --output-format json \
  -p '评估以下方案的可行性，对照现有代码指出潜在冲突、遗漏边界和修正建议。'
```

Codex 核实评估意见后向用户汇报方案，确认后进入实施，不进行多轮文字辩论。

### 2. 派发实施（复用全局完整权限，极简调用）

收到用户确认后，直接派发单个 AGY 会话（无需传 `--sandbox` 或冗长的 `--settings` 白名单，直接继承本机 `settings.json` 的完整权限）：

```bash
agy --project '<项目ID>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands \
  --output-format json \
  -p '目标：<要实现的业务目标与关键技术决策>
不可变边界：<必须保留的既有行为、接口与协议；禁止执行 git checkout/restore/reset/clean 丢弃未提交改动>
验收条件：<构建或测试通过标准>
请自主完成代码修改、测试编写与本地构建自检，修复发现的问题后返回改动摘要。'
```

### 3. 续接与集中返工

交付后若验证发现遗漏问题，用保存的 `conversation_id` 一次性汇总交回原会话修复：

```bash
agy --conversation '<conversation_id>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands \
  --output-format json \
  -p '验证发现以下问题，请一并修复并重新自检通过：<问题列表>'
```

- **上下文切换**：不监控内部 token 计数；仅当多轮续接后出现明显上下文遗忘或重复报错打转时，开启新会话并明确交接当前已完成改动与剩余问题。

---

## 项目与模型选型

1. **项目归属**：始终在目标仓库根目录启动 `agy`。首次调用时查阅 `~/.gemini/config/projects/*.json`：
   - 若存在 `folderUri` 匹配当前仓库根目录的项目，复用 `--project '<项目ID>'`；
   - 若不存在匹配项目或目录不一致，直接省略 `--project` 参数（由 `agy` 在当前工作区根目录自动映射）。
2. **模型与额度**：仅在当前对话首次使用 AGY 或遇到配额报错时查一次 `agy models` 与 `agy -p '/usage'`。复杂方案评估优先选有额度的旗舰模型 Medium（如 `gemini-4-argon-medium`）；实施与修复优先选中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
