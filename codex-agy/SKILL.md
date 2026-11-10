---
name: codex-agy
description: 通过 Antigravity CLI（agy）及确定性包装器 agy-delegate 使用 AGY 作为 Codex 的实现 Subagent。利用 V8 内置 while 循环与 functions.wait 减少等待唤醒，由 AGY 自主完成阅读、编码与测试闭环。
---

# 调用 AGY

## 核心原则

**不要把 AGY 当傻子，Codex 不要过度限制，也不要过度指导；用确定性工具机制代替口头约定。**
本机 `~/.gemini/antigravity-cli/settings.json` 已全局配置完整权限（`"toolPermission": "always-proceed"`, `"allowNonWorkspaceAccess": true`, `"enableTerminalSandbox": false`），并安装了确定性包装器 `/Users/du/.local/bin/agy-delegate`。

- **委托前**：Codex 只明确**业务目标、必要设计、不可变边界和验收条件**。不替 AGY 全量预读源码，不在提示词里教 AGY 怎么调工具；无需手写脚本查项目 ID 或打快照（`agy-delegate` 会优先从 `~/.gemini/config/projects/*.json` 匹配当前仓库目录对应的 `--project <id>`，无匹配时省略 `--project` 回退归属至 `default-cli-project`；并在每次执行前自动捕获完整基线快照至 `/tmp/agy-snapshots/`，若基线捕获失败直接报错中止 `BASELINE_ERROR`，绝不无保护派发）。
- **执行中（V8 循环 + `functions.wait` 持续等待）**：
  - 单层直派单个 AGY 会话，由 AGY 自主完成阅读、编码、运行测试与局部纠错。
  - Codex 在 `functions.exec`（JavaScript V8 工具）中必须加首行 `// @exec: {"yield_time_ms": 300000}` 并使用 `while (res.session_id !== undefined)` 循环调用 `write_stdin`，在单个 V8 沙箱内持续阻塞等待（5 分钟内完成则 0 次中途唤醒）。
  - **超 5 分钟续等铁律**：当 `functions.exec` 满 5 分钟返回 `Script running with cell ID <cell_id>` 时，原 V8 循环仍在后台继续运行。此时**必须直接调用 `functions.wait({ cell_id: "<cell_id>", yield_time_ms: 300000, max_tokens: 10000 })` 等待原 `cell_id`**，严禁另开新的 `functions.exec` 再次对同一终端调用 `write_stdin`（避免双循环争用输出），严禁顺手跑 `git diff`/`status`、查内部日志或发催写指令。
- **交付后**：`agy-delegate` 会自动校验进程退出码、`status`、`denied_actions` 与 `error` 并输出结构化 JSON（若有软拒绝直接返回退出码 `2`）。Codex 核对返回的 JSON 后，集中审查 `git diff` 并做独立验证；若有遗漏问题，使用返回的 `conversation_id` 一次性汇总交回修复。
- **职责红线与精确回滚**：
  - **生产代码、测试代码与配置始终由 AGY 修改**：委托失败或遇环境阻塞时，Codex 排障或汇总问题后继续通过 `agy-delegate` 委托，**Codex 绝不亲自下场改业务代码**。
  - **AGY 不擅改方向**：AGY 遇到需变更技术方案或扩大范围的问题，交回 Codex 决策。
  - **精确状态回滚**：`agy-delegate` 快照同时记录 `head_commit`、Git 暂存区树（`index_tree` via `git write-tree`）及所有已修改/未跟踪文件的 SHA-256 备份。若需回滚某次委托修改，直接运行 `agy-delegate restore '<pre_snapshot_dir>'`（恢复后自动校验 `HEAD`、`index_tree`、文件列表与 SHA-256，任一不一致即返回 `"ok": false` 与退出码 `1`）。

---

## 标准调用方式

### 1. 派发实施（`agy-delegate run`）

收到用户确认后，在 Codex 的 `functions.exec` 工具中使用以下标准模板启动并等待完成：

```javascript
// @exec: {"yield_time_ms": 300000, "max_output_tokens": 10000}
const prompt = `目标：<要实现的业务目标与关键技术决策>
不可变边界：<必须保留的既有行为、接口与协议；禁止执行 git checkout/restore/reset/clean 丢弃未提交改动>
验收条件：<构建或测试通过标准>
请自主完成代码修改、测试编写与本地构建自检，修复发现的问题后返回改动摘要。`;
const q = s => "'" + s.replaceAll("'", "'\\''") + "'";
let res = await tools.exec_command({
  cmd: `agy-delegate run --model gemini-3.8-flash-high ${q(prompt)}`,
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

### 3. 续接返工（`agy-delegate resume`）

交付后若验证发现遗漏问题，使用上一轮 JSON 返回的 `conversation_id` 一次性交回修复（同样放在第 1 节的 V8 `while` 循环模板中执行）：

```bash
agy-delegate resume '<conversation_id>' --model gemini-3.8-flash-high '验证发现以下问题，请一并修复并重新自检通过：<问题列表>'
```

- **上下文切换**：不监控内部 token 计数；仅当多轮续接后出现明显上下文遗忘或重复报错打转时，改用 `agy-delegate run` 开启新会话并交接已完成改动与剩余问题。

### 4. 可行性评估（`agy-delegate review`，仅复杂方案按需触发）

常规任务直接进入实施。仅当涉及复杂架构、跨服务契约或状态机改造时，做单轮只读评估。`agy-delegate review` 内部显式设置 `allowNonWorkspaceAccess: false, enableTerminalSandbox: true, toolPermission: "request-review"` 并 `deny: ["write_file(*)", "command(*)", "mcp(*)", "read_url(*)"]`（禁止文件写入与一切终端命令，仅使用 AGY 原生文件读取与内置 `ripgrep` 搜索）：

```bash
agy-delegate review --model gemini-4-argon-medium '评估以下方案的可行性，对照现有代码指出潜在冲突、遗漏边界和修正建议：<方案摘要>'
```

### 5. 精确回滚（`agy-delegate restore`）

若需回滚某次委托修改，使用该次运行返回的 `pre_snapshot_dir` 还原到委托前的精确工作区状态（包含 `HEAD`、Git 暂存区 `index_tree` 与工作区未提交/未跟踪文件，并自动执行 SHA-256 完整性校验）：

```bash
agy-delegate restore '<pre_snapshot_dir>'
```

---

## 模型与额度选型

- 仅在当前对话首次使用 AGY 或遇到配额报错时查一次 `agy models` 与 `agy -p '/usage'`。
- 复杂方案只读评估优先选有额度的旗舰模型 Medium（默认 `gemini-4-argon-medium`）；实施与修复优先选中档模型 High（默认 `gemini-3.8-flash-high`）或旗舰 Medium。
