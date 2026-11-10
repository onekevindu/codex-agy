---
name: codex-agy
description: 通过原生 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。零外部脚本依赖、开箱即用，利用 Codex V8 内置 while 循环与 functions.wait 消除等待轮询，由 AGY 自主完成阅读、编码与测试闭环。
---

# 调用 AGY

## 核心原则

**不要把 AGY 当傻子，Codex 不要过度限制，也不要过度指导。**
Codex 的职责是讲清楚**要实现什么目标、不能破坏什么边界、怎么算验收通过**，把执行自主权交给 AGY，并管住自己的唤醒消耗：

- **委托前**：
  - Codex 明确业务目标、必要设计、不可变边界和验收条件，不替 AGY 全量预读源码，不在提示词里教 AGY 怎么调工具。
  - **基线快照保护**：若工作区存在未提交改动，委托前先做好快照备份；后续若需回滚，**只能依据委托前快照恢复**（并核对恢复退出码与文件状态），严禁直接执行 `git checkout/restore/reset/clean` 恢复到 `git HEAD` 而误删前序未提交成果。
- **执行中（V8 循环 + `functions.wait` 持续等待）**：
  - 单层直派单个原生 `agy` 会话，由 AGY 自主完成阅读、编码、运行构建/测试与编译报错自修复。
  - Codex 在 `functions.exec`（JavaScript V8 工具）中必须加首行 `// @exec: {"yield_time_ms": 300000}` 并使用 `while (res.session_id !== undefined)` 循环调用 `write_stdin`，在单个 V8 沙箱内持续阻塞等待（5 分钟内完成则 0 次中途唤醒）。
  - **超 5 分钟续等铁律**：当 `functions.exec` 满 5 分钟返回 `Script running with cell ID <cell_id>` 时，原 V8 循环仍在后台继续运行。此时**必须直接调用 `functions.wait({ cell_id: "<cell_id>", yield_time_ms: 300000, max_tokens: 10000 })` 等待原 `cell_id`**，严禁另开新的 `functions.exec` 再次对同一终端调用 `write_stdin`（避免双循环争用输出），严禁顺手跑 `git diff`/`status`、查内部日志或发催写指令。
- **交付后（完成判定与集中终验）**：
  - 从 `--output-format json` 返回结果中提取并保存 `conversation_id`，同时检查进程退出码、`status`、`stderr` 及 `denied_actions`（不能仅凭退出码 `0` 认定完成）。
  - AGY 自测通过返回后，Codex 集中审查 `git diff` 并做独立验证；若仍有遗漏问题，一次性汇总交回 AGY。
- **职责红线与阻塞处理**：
  - **生产代码、测试代码与配置始终由 AGY 修改**：委托失败或遇环境阻塞时，Codex 排障或汇总问题后继续委托 AGY，**Codex 绝不亲自下场改业务代码**。
  - **AGY 不擅改方向**：AGY 遇到需变更技术方案或扩大范围的问题，交回 Codex 决策。

---

## 标准调用方式（纯原生 `agy`，零外部依赖）

### 1. 派发实施

收到用户确认后，使用原生 `agy --mode accept-edits --disable-slash-commands --dangerously-skip-permissions` 赋予完整读写与构建执行权限（同时通过 `--settings` 显式禁止破坏性 Git 回滚命令，开箱即用，无需换机预配 `settings.json`），并在 Codex 的 `functions.exec` 工具中使用以下 V8 循环模板等待完成：

```javascript
// @exec: {"yield_time_ms": 300000, "max_output_tokens": 10000}
const prompt = `目标：<要实现的业务目标与关键技术决策>
不可变边界：<必须保留的既有行为、接口与协议；禁止执行 git checkout/restore/reset/clean 丢弃未提交改动>
验收条件：<构建或测试通过标准>
请自主完成代码修改、测试编写与本地构建自检，修复发现的问题后返回改动摘要。`;
const settings = JSON.stringify({
  permissions: {
    deny: [
      "command(git reset)",
      "command(git checkout)",
      "command(git restore)",
      "command(git clean)"
    ]
  }
});
const q = s => "'" + s.replaceAll("'", "'\\''") + "'";
let res = await tools.exec_command({
  cmd: `agy --project '<项目ID或名称>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --dangerously-skip-permissions --settings ${q(settings)} --output-format json -p ${q(prompt)}`,
  yield_time_ms: 30000,
  max_output_tokens: 10000
});
let out = res.output || "";
while (res.session_id !== undefined) {
  res = await tools.write_stdin({
    session_id: res.session_id,
    chars: "",
    yield_time_ms: 300000,
    max_output_tokens: 10000
  });
  out += res.output || "";
}
text(out);
```

### 2. 超过 5 分钟时的纯续等（调用 `functions.wait`）

若上述 `functions.exec` 返回 `Script running with cell ID <cell_id>`，说明原 V8 `while` 循环仍在运行中：
- **唯一允许的操作**：直接调用 `functions.wait` 工具等待该 `cell_id`：
  ```json
  {
    "cell_id": "<cell_id>",
    "yield_time_ms": 300000,
    "max_tokens": 10000
  }
  ```
- **严禁**：另开新的 `functions.exec` 去调 `write_stdin`，或在续等期间夹带任何检查命令。

### 3. 续接返工

交付后若验证发现遗漏问题，使用上一轮 JSON 返回的 `conversation_id` 一次性交回修复（同样放在第 1 节的 V8 `while` 循环模板中执行）：

```bash
agy --conversation '<conversation_id>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --dangerously-skip-permissions \
  --settings '{"permissions":{"deny":["command(git reset)","command(git checkout)","command(git restore)","command(git clean)"]}}' \
  --output-format json \
  -p '验证发现以下问题，请一并修复并重新自检通过：<问题列表>'
```

- **上下文切换**：不监控内部 token 计数；仅当多轮续接后出现明显上下文遗忘或重复报错打转时，开启新会话并交接已完成改动与剩余问题。

### 4. 可行性评估（仅复杂方案按需触发）

常规任务直接进入实施。仅当涉及复杂架构、跨服务契约或状态机改造时，做单轮只读评估（禁止文件写入与一切终端命令，仅使用 AGY 原生文件读取与内置 `ripgrep` 搜索）：

```bash
agy --project '<项目ID或名称>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands --sandbox \
  --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"deny":["write_file(*)","command(*)","mcp(*)","read_url(*)"]}}' \
  --output-format json \
  -p '评估以下方案的可行性，对照现有代码指出潜在冲突、遗漏边界和修正建议：<方案摘要>'
```

---

## 项目与模型选型

1. **项目归属**：始终在目标仓库根目录启动 `agy`。
   - 优先从 `~/.gemini/config/projects/*.json` 查找 `folderUri` 匹配当前仓库根目录的项目 `id` 传入 `--project '<项目ID>'`；
   - 若无匹配项目，可传 `--new-project '<仓库目录名>'` 创建对应项目，或省略 `--project`（省略时会话归属至 `default-cli-project`）。
2. **模型与额度**：仅在当前对话首次使用 AGY 或遇到配额报错时查一次 `agy models` 与 `agy -p '/usage'`。复杂方案只读评估优先选有额度的旗舰模型 Medium（如 `gemini-4-argon-medium`）；实施与修复优先选中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
