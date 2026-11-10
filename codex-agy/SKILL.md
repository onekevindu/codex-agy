---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。Codex 只讲清楚目标、边界和验收条件，由 AGY 自主完成阅读、编码与测试闭环，Codex 静默等待并集中终验。
---

# 调用 AGY

## 核心原则

**不要把 AGY 当傻子，Codex 不要过度限制，也不要过度指导。**
Codex 的职责是讲清楚**要实现什么目标、不能破坏什么边界、怎么算验收通过**，然后把执行过程的自主权真正交给 AGY：

- **委托前**：Codex 明确目标、必要设计、不可变边界和验收条件。若工作区有未提交改动，先做好基线备份（避免回滚时误用 `git checkout HEAD` 清空未提交成果）。不要替 AGY 全量扫库，不要写多份冗长的委托文档，也不要在提示词里教 AGY 怎么调工具、一次读几行或用哪个编辑函数。
- **执行中**：AGY 自主阅读、编码、运行测试和局部纠错；Codex 在工具侧持续等待结果（拉满 `yield_time_ms`），不频繁唤醒模型空轮询，不读取 AGY 内部状态库，不按读取次数和耗时催写。
- **交付后**：Codex 集中审查 `git diff`、执行独立验证，把实际问题一次性交回 AGY。
- **出现阻塞时**：针对具体阻塞点定向处理，避免重新调查整个任务。

---

## 流程与命令

### 1. 可行性评估（仅复杂方案按需触发）

常规任务或边界清晰的需求，Codex 与用户确认目标后直接进入实施。仅当涉及复杂架构、跨服务契约或事务/状态机改造时，请 AGY 做一次单轮只读评估：

- 注意：`agy` 的 `--mode plan` 在底层会自动注入 `/plan` 宏（触发生成计划文档的长流程），因此只读评估统一使用 `--mode accept-edits --disable-slash-commands` 搭配 `--settings` 禁止写入和命令执行：

```bash
agy --project '<项目ID>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands \
  --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)"],"deny":["write_file(*)","command(*)","mcp(*)","read_url(*)"]}}' \
  --output-format json \
  -p '评估以下方案的可行性，对照现有代码指出潜在冲突、遗漏边界和修正建议。'
```

Codex 核实评估意见后向用户汇报方案，确认后进入实施，不进行多轮文字辩论。

### 2. 派发实施（单层直派，赋予完整自治权）

收到用户确认后，直接派发单个 AGY 会话（无需额外套一层“AGY 负责人”进程传话）。给予整个工作区的读写权限与沙箱内命令执行权限（`proceed-in-sandbox`），不要做碎片化的单文件白名单限制，也不要硬性指定构建日志落盘路径：

```bash
agy --project '<项目ID>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --sandbox \
  --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"proceed-in-sandbox","permissions":{"allow":["read_file(/绝对路径/工作区根目录)","write_file(/绝对路径/工作区根目录)","command(env)","command(mvn)","command(git status)","command(git diff)"],"deny":["unsandboxed(*)","command(git checkout)","command(git reset)","command(git clean)","command(git commit)","command(git push)","mcp(*)","read_url(*)"]}}' \
  --output-format json \
  -p '目标：<讲清楚要实现的业务目标与关键技术决策>
不可变边界：<必须保留的既有行为、接口与协议>
验收条件：<构建或测试通过标准>
请自主完成代码修改、测试编写与本地构建自检，修复发现的问题后返回改动摘要。'
```

（若目标项目使用 Gradle、pytest、npm 等其他构建工具，将 `command(mvn)` 替换为对应工具命令即可。）

### 3. 续接与集中返工

交付后 Codex 集中审查 `git diff` 并做验证。若存在遗漏问题，一次性汇总交给原会话修复：

```bash
agy --conversation '<conversation_id>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --sandbox \
  --settings '<同上会话权限 JSON>' --output-format json \
  -p '验证发现以下问题，请一并修复并重新自检通过：<问题列表>'
```

若会话历经多轮后触发上下文自动压缩（~256K tokens）且出现细节遗忘，基于当前 Git 状态开启新会话处理剩余问题。

---

## 项目与模型选型

1. **项目归属**：在目标仓库根目录启动 `agy`。首次调用时从 `~/.gemini/config/projects/*.json` 选取绑定当前仓库的同名项目 `id`，后续复用 `--project '<项目ID>'`。
2. **模型与额度**：仅在当前对话首次使用 AGY 或遇到配额报错时查一次 `agy models` 与 `agy -p '/usage'`。复杂方案评估优先选有额度的旗舰模型 Medium（如 `gemini-4-argon-medium`）；实施与修复优先选中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
