---
name: codex-agy
description: 通过原生 Antigravity CLI 调用个人账户 agy（默认）或 GCP Vertex AI ADC 通道 agy-gcp 作为 Codex 的实现 Subagent。零外部脚本强依赖、开箱即用，固化双通道环境隔离与分通道主力/旗舰模型选型，利用 Codex V8 内置 while 循环与 functions.wait 消除等待轮询，由 AGY 自主完成阅读、编码与测试闭环。
---

# 调用 AGY（支持 `agy` 个人通道与 `agy-gcp` GCP 通道）

## 核心原则

**不要把 AGY 当傻子，Codex 不要过度限制，也不要过度指导。**
Codex 的职责是讲清楚**要实现什么目标、不能破坏什么边界、怎么算验收通过**，把执行自主权交给 AGY，并管住自己的唤醒消耗：

- **委托前**：
  - Codex 明确业务目标、必要设计、不可变边界和验收条件，不替 AGY 全量预读源码，不在提示词里教 AGY 怎么调工具。
  - **基线快照保护**：若工作区存在未提交改动，委托前先做好快照备份；后续若需回滚，**只能依据委托前快照恢复**（并核对恢复退出码与文件状态），严禁直接执行 `git checkout/restore/reset/clean` 恢复到 `git HEAD` 而误删前序未提交成果。
- **执行中（V8 循环 + `functions.wait` 持续等待，严禁短 `--print-timeout`）**：
  - 单层直派单个 `agy` 或 `agy-gcp` 会话，由 AGY 自主完成阅读、编码、运行构建/测试与编译报错自修复。
  - **严禁附加短 `--print-timeout`（如 `40s`/`90s`）**：保持原生默认 `0s`（等待本轮自然完成）。`agy-gcp` 冷启动需经历 ADC OAuth 换票及插件 MCP/Hook 初始化（约 `8s~22s`），且 Vertex AI `gemini-4-carbon-*` 首包排队或经代理遇 `unexpected EOF` / `TLS handshake timeout` 自动重试时单轮可达 `75s~160s`；加短 `--print-timeout` 会在流式首包落盘前直接触发 `finished_reason: "print_timeout"`（退出码 `3`、空回复）误杀正常调用。
  - Codex 在 `functions.exec`（JavaScript V8 工具）中必须加首行 `// @exec: {"yield_time_ms": 300000}` 并使用 `while (res.session_id !== undefined)` 循环调用 `write_stdin`，在单个 V8 沙箱内持续阻塞等待（5 分钟内完成则 0 次中途唤醒）。
  - **超 5 分钟续等铁律**：当 `functions.exec` 满 5 分钟返回 `Script running with cell ID <cell_id>` 时，原 V8 循环仍在后台继续运行。此时**必须直接调用 `functions.wait({ cell_id: "<cell_id>", yield_time_ms: 300000, max_tokens: 10000 })` 等待原 `cell_id`**，严禁另开新的 `functions.exec` 再次对同一终端调用 `write_stdin`（避免双循环争用输出），严禁顺手跑 `git diff`/`status`、查内部日志或发催写指令。
- **交付后（完成判定与集中终验）**：
  - 从 `--output-format json` 返回结果中提取并保存 `conversation_id`，同时检查进程退出码、`status`、`stderr` 及 `denied_actions`（不能仅凭退出码 `0` 认定完成）。
  - AGY 自测通过返回后，Codex 集中审查 `git diff` 并做独立验证；若仍有遗漏问题，**使用同一通道**一次性汇总交回 AGY。
- **职责红线与阻塞处理**：
  - **生产代码、测试代码与配置始终由 AGY 修改**：委托失败或遇环境阻塞时，Codex 排障或汇总问题后继续委托 AGY，**Codex 绝不亲自下场改业务代码**（仅纯文档拼写或单行常量微调除外）。
  - **AGY 不擅改方向**：AGY 遇到需变更技术方案或扩大范围的问题，交回 Codex 决策。

---

## 双通道选择与模型选型规范（`agy` vs `agy-gcp`）

### 1. 通道选择与非交互 Shell 固化调用

本机通常同时存在两套认证通道，且共用 `~/.gemini/antigravity-cli/settings.json`：

- **默认通道：`agy`（个人 Google Pro / Keyring 账户）**
  - 当用户未显式点名通道且目标项目 `AGENTS.md` 未特殊声明时，**默认一律使用个人通道 `agy`**。
  - **防串号铁律**：调用个人通道 `agy` 时，必须通过 `env -u AGY_ADC_AUTH -u GOOGLE_APPLICATION_CREDENTIALS -u CLOUDSDK_CORE_PROJECT -u GOOGLE_CLOUD_PROJECT agy ...` 显式剥离 GCP ADC 环境变量，防止继承父终端环境变量而误走 GCP 计费。
- **按需切换通道：`agy-gcp`（GCP Vertex AI ADC 账户）**
  - **触发条件**：仅当**用户在当前对话中明确要求使用 `agy-gcp` / `GCP` / `Carbon`**，或**目标项目 `AGENTS.md` 明确指定使用 `agy-gcp`** 时切换至 `agy-gcp`。
  - **非交互 Shell 固化调用铁律**：Codex `tools.exec_command` 默认运行在 `/bin/zsh -lc`（非交互登录 Shell），不加载 `~/.zshrc` 中定义的交互函数 `agy-gcp`。因此调用 `agy-gcp` 必须使用以下自适配启动器：
    1. 若 `command -v agy-gcp` 可见或 `$HOME/.local/bin/agy-gcp` 可执行脚本存在，直接调用该可执行脚本（零交互启动开销）；
    2. 否则自动回退至 `SHELL_SESSIONS_DISABLE=1 /bin/zsh -ic 'agy-gcp "$@"' zsh <参数...>`。**必须通过 `zsh "$@"` 位置参数透传全部参数**（防止多行 `-p` 提示词与 `--settings` JSON 在 `-ic` 字符串中被二次引号展开破坏，同时 `SHELL_SESSIONS_DISABLE=1` 屏蔽 macOS 交互式 Zsh 退出时的 `Saving session...` 污染 JSON 输出）。
- **会话通道一致性**：续接 `--conversation '<conversation_id>'` 时，必须沿用创建该会话时的同一通道（`agy` 或 `agy-gcp`）。

### 2. 分通道模型矩阵与配额防爆锁

两套通道的后端模型池不同，且共享 `settings.json` 默认值缓存，**每次 CLI 调用必须显式传入 `--model '<精确模型ID>'`**：

| 模型角色 | `agy`（个人 Google Pro，默认通道） | `agy-gcp`（GCP Vertex AI ADC 通道） | 适用场景与说明 |
| :--- | :--- | :--- | :--- |
| **日常主力（默认）** | `gemini-3.8-flash-high` | `gemini-3.8-flash-high` | 实施、修复、单测、写文档及常规只读评估默认强制使用；首包快、额度充裕 |
| **最新旗舰（仅用户明确要求）** | **`gemini-4-argon-medium`**（或用户指定的 `low` / `high`；**个人通道无 `carbon` 系列**） | **`gemini-4-carbon-medium`**（或用户指定的 `low` / `high`；**GCP 通道中 `carbon` 才是最新旗舰**，`argon` 为次旗舰） | 仅在用户明确要求“用旗舰 / Carbon / Argon / Medium”时启用；严禁混淆两端旗舰代号 |
| **其他点名模型** | 以个人通道 `models` 输出为准（含 Argon / Flash 3.8 / Claude 5.5 等） | 以 GCP 通道 `models` 输出为准（含 Carbon / Argon / Flash 3.5~3.8 / Claude 5.5 等） | 用户点名特定模型或遇模型名不确定时，先用对应通道跑一次 `models` 子命令核实精确 ID |

- **配额防爆四铁律**：
  1. **日常默认锁死主力 Flash**：未经用户明确要求特定其他模型，实施、调试、单测、修 Bug、写文档默认使用 `gemini-3.8-flash-high`。
  2. **硬性封锁旗舰的自发升配**：无论主力 Flash 遇到何种超时、复杂逻辑或构建报错，Codex 只能汇总具体问题交回主力模型定向修复或重开会话，**严禁 Codex 自主决定升配至 `argon` 或 `carbon` 旗舰**！只有用户在对话中明确要求使用旗舰或点名具体旗舰模型时方可调用。
  3. **严禁将 Flash 长会话喂给旗舰模型**：即使用户明确授权使用旗舰模型（如个人通道 `gemini-4-argon-*` 或 GCP 通道 `gemini-4-carbon-*`），**也必须开启全新的会话**（传入 `--project` 而非 `--conversation`），由 Codex 提炼当前基线状态与目标交接给新会话，严禁在已有数百步历史的旧会话上直接切旗舰。
  4. **旗舰额度不足或不可用自动降级**：若按用户要求调用旗舰模型时遇到配额不足/耗尽或端点持续不可用报错，**立即无缝降级使用同通道 `gemini-3.8-flash-high` 继续执行**，不阻塞流程。

---

## 标准调用方式（双通道自适应，零外部强依赖）

### 1. 派发实施

收到用户确认后，按通道规则设置 `channel`（默认 `"agy"`，按需 `"agy-gcp"`）与匹配的 `model`，使用 `--mode accept-edits --disable-slash-commands --dangerously-skip-permissions` 配合 `--settings` 显式拦截破坏性 Git 回滚命令（**切勿添加短 `--print-timeout`**），在 Codex 的 `functions.exec` 工具中运行以下 V8 循环模板：

```javascript
// @exec: {"yield_time_ms": 300000, "max_output_tokens": 10000}
const channel = "agy"; // 默认 "agy"（个人账户）；仅在用户或项目 AGENTS.md 明确要求 GCP/Carbon 时设为 "agy-gcp"
const model = "gemini-3.8-flash-high"; // 默认主力；用户明确要求最新旗舰时：agy 用 "gemini-4-argon-medium"，agy-gcp 用 "gemini-4-carbon-medium"
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
const runner = channel === "agy-gcp"
  ? `if command -v agy-gcp >/dev/null 2>&1; then agy-gcp "$@"; elif [ -x "$HOME/.local/bin/agy-gcp" ]; then "$HOME/.local/bin/agy-gcp" "$@"; else SHELL_SESSIONS_DISABLE=1 /bin/zsh -ic 'agy-gcp "$@"' zsh "$@"; fi`
  : `env -u AGY_ADC_AUTH -u GOOGLE_APPLICATION_CREDENTIALS -u CLOUDSDK_CORE_PROJECT -u GOOGLE_CLOUD_PROJECT agy "$@"`;
const args = [
  "--project", "<项目ID或名称>",
  "--model", model,
  "--mode", "accept-edits",
  "--disable-slash-commands",
  "--dangerously-skip-permissions",
  "--settings", settings,
  "--output-format", "json",
  "-p", prompt
].map(q).join(" ");
let res = await tools.exec_command({
  cmd: `sh -c ${q(runner)} sh ${args}`,
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

交付后若验证发现遗漏问题，沿用**同一 `channel`** 与上一轮 JSON 返回的 `conversation_id` 一次性交回修复（只需将第 1 节模板中的 `args` 替换为以下参数数组，默认保持 `gemini-3.8-flash-high`）：

```javascript
const args = [
  "--conversation", "<conversation_id>",
  "--model", model,
  "--mode", "accept-edits",
  "--disable-slash-commands",
  "--dangerously-skip-permissions",
  "--settings", settings,
  "--output-format", "json",
  "-p", `验证发现以下问题，请一并修复并重新自检通过：<问题列表>`
].map(q).join(" ");
```

- **上下文重置**：不监控内部 token 计数；若多轮续接后会话步数过多（出现上下文遗忘或超时中断），开启全新会话并使用主力 `gemini-3.8-flash-high`，把当前基线成果与剩余问题交接给新会话。
- **微小修补禁止外包**：若仅为极小范围的文档拼写校正、路径修正或单行常量调整，由 Codex 直接修改并验证，严禁拉起 AGY 产生多余开销。

### 4. 可行性评估与模型列表实时查询（按需触发）

- **查验通道可用模型 ID**：当用户点名模糊模型（如“用旗舰”、“用 Carbon Low”）需确认精确 ID 时，复用第 1 节 `runner` 执行单次快速查询：
  ```javascript
  // channel = "agy" 或 "agy-gcp"
  cmd: `sh -c ${q(runner)} sh models`
  ```
- **复杂方案只读可行性评估**：常规任务直接实施；仅当涉及复杂架构、跨服务契约或状态机改造时，做单轮只读评估（禁止文件写入与一切终端命令，仅使用 AGY 原生文件读取与内置 `ripgrep` 搜索）。默认仍使用主力 `gemini-3.8-flash-high`；仅在用户明确要求使用旗舰时，按通道选用对应最新旗舰（`agy` 用 `gemini-4-argon-medium`，`agy-gcp` 用 `gemini-4-carbon-medium`）：
  ```javascript
  const evalSettings = JSON.stringify({
    allowNonWorkspaceAccess: false,
    enableTerminalSandbox: true,
    toolPermission: "request-review",
    permissions: {
      deny: ["write_file(*)", "command(*)", "mcp(*)", "read_url(*)"]
    }
  });
  const args = [
    "--project", "<项目ID或名称>",
    "--model", model,
    "--mode", "accept-edits",
    "--disable-slash-commands",
    "--sandbox",
    "--settings", evalSettings,
    "--output-format", "json",
    "-p", `评估以下方案的可行性，对照现有代码指出潜在冲突、遗漏边界和修正建议：<方案摘要>`
  ].map(q).join(" ");
  ```

---

## 项目归属约定

始终在目标仓库根目录启动 `agy` / `agy-gcp`：
- 优先从 `~/.gemini/config/projects/*.json` 查找 `folderUri` 匹配当前仓库根目录的项目 `id` 传入 `--project '<项目ID>'`；
- 若无匹配项目，可传 `--new-project '<仓库目录名>'` 创建对应项目，或省略 `--project`（省略时会话归属至 `default-cli-project`）。
