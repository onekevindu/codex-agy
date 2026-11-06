---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。用于委托可行性分析、编码、测试或修复，以及续接同一项委托。Codex 保留技术决策和验收权。
---

# 直接调用 AGY

## 先查本机帮助

当前 Codex 对话首次使用 AGY 时，先运行 `command -v agy` 和 `agy --help`，再选择调用方式。使用不熟悉的子命令时，先运行 `agy <子命令> --help`。遇到参数报错、CLI 升级或发现文档与本机行为有差异时，重新查对应帮助后再重试。需要交互式斜杠命令时，另外核对该命令是否支持当前的交互或 headless 模式。

## 委托前检查模型和额度

在选模型前由 Codex 运行以下命令。进入下一阶段前刷新额度，并把实际选用的模型和对应模型组的剩余额度简要告诉用户。

```bash
agy models
agy -p '/usage'
```

查询额度时保留 CLI 的斜杠命令处理，避免给 `/usage` 加 `--disable-slash-commands`。

> 先查看 AGY 当前可用模型和剩余额度。可行性分析用当前可用且有额度的最高能力模型（如 Pro 或同档旗舰），推理强度用 Medium。实施、测试和修复用有额度的中档模型（如 Flash），推理强度用 High。

按 CLI 实际返回的模型 ID 和额度选型，检查适用的短时、周度及模型专属额度。优先使用列表中已经包含推理档位的模型 ID。若使用基础模型 ID，则用 `--effort medium` 或 `--effort high` 显式指定档位。首选组合不可用时，选同档且支持所需推理强度的模型并说明。查询失败时报告额度未知。没有符合条件的组合时向用户说明限制。按阶段传入模型参数，续接会话时也显式选型。[AGY 模型与推理参数](https://antigravity.google/docs/cli/reference/) · [AGY 模型额度](https://antigravity.google/docs/cli/commands/usage)

## 命令

以当前 Codex 对话的工作区目录为准，用它的绝对路径作为 Shell 调用的工作目录。若 Codex 当前就在 Git 工作树中，AGY 使用同一个工作树。比较路径时解析符号链接，例如用 `pwd -P` 确认实际目录。

Codex 项目中的新委托归档到同名 AGY 项目。以 Codex 中显示的项目名称为准，分别确认名称和实际工作区。复用已有项目时，核对项目配置包含目标目录且范围适合本次委托，再用 `--project '<项目 ID>'` 启动。遇到同名但目录不匹配的项目，先解决归属再委托。

没有同名项目时，创建与 Codex 项目同名、绑定目标工作区的 AGY 项目。本机 CLI 的 `--new-project` 默认用启动目录的名称建项目，只有目录名与 Codex 项目名一致时才直接使用该参数，否则在 AGY 项目界面指定名称和目录。当前本机版本可从 `~/.gemini/config/projects/<项目 ID>.json` 核对 `name`、`id` 和 `projectResources.resources[]` 中的 `folderUri` 或 `gitFolder.folderUri`。如果当前对话没有 Codex 项目，或用户明确要求使用默认 CLI 项目，可省略 `--project`。[AGY 项目文档](https://antigravity.google/docs/projects?tab=cli)

```bash
agy --project '<项目 ID>' --model '<旗舰 Medium 模型 ID>' --mode plan --output-format json -p '评估这项方案的可行性，指出风险和待决问题。只读分析。'
agy --project '<项目 ID>' --model '<中档 High 模型 ID>' --mode accept-edits --output-format json -p '按已批准的方案文件实施，执行约定的测试并报告结果。'
```

将示例提示替换为实际目标、已确定的方案、允许范围和验收条件。较长的内容或关键方案放在 AGY 可读取的项目文件中，在提示里给出路径。可用自然语言要求 AGY 说明改动、测试结果和待决问题。

## 读取结果与续接

`--output-format json` 返回 CLI 原生 JSON。读取 stdout 的 `response`，结合进程退出码、`status`、`error`、出现时的 `denied_actions` 和 stderr 判断实际执行情况。即使 CLI 返回成功，也要以实际改动与验证结果为准。无需续接时也可直接读默认文本输出。

同一项委托需要澄清、续做或返工时，记下上一轮 JSON 的 `conversation_id`，并确认原会话的工作区仍对应 Codex 当前任务。`--conversation` 会沿用原会话的项目归属。若几轮调用都在同一工作目录顺序执行，且能确认目标会话是该目录最近使用的 AGY 会话，可用 `--continue`（`-c`）。CLI 根据工作目录选择最近使用的会话。即使复用同一个终端，每次 `agy -p` 也会启动新进程。若有其他委托、并行调用，或不能确认最近使用的会话，使用 `--conversation <会话 ID>` 精确续接。两种参数择一。

```bash
agy --conversation '<conversation_id>' --model '<中档 High 模型 ID>' --mode accept-edits --output-format json \
  -p '按更新后的方案文件和下面的验收要求继续。'

agy --continue --model '<旗舰 Medium 模型 ID>' --mode plan --output-format json \
  -p '继续只读分析，补充上一轮的待决问题。'
```

核对返回的会话 ID。独立委托按上面的项目归档规则开启新会话，省略 `--conversation` 和 `--continue`。旧会话不可用或属于其他工作区时，先核对已发生的改动，再把当前方案和剩余工作交给从当前工作区启动的新会话。续接时仍应引用关键方案文件，以应对上下文压缩。[AGY 会话工作区](https://antigravity.google/docs/cli/conversations) · [AGY Headless 文档](https://antigravity.google/docs/cli/headless#continue-a-conversation)

## 权限

`plan` 用于分析，`accept-edits` 用于已授权的实现。执行模式和提示词都不能替代权限隔离。按任务使用 Codex 的宿主权限和 AGY 的会话设置（`--settings`）。`--sandbox` 限制 AGY 执行的终端命令。严格只读时，确认文件工具和终端都受只读权限约束。禁止生产操作时，隔离生产凭据与网络访问。记录 Git 基线以保护已有未提交改动。需要隔离时，先让 Codex 在隔离工作树中开展任务，并从该工作树启动 AGY。需要命名项目时，核对其范围指向该工作树。遇到权限拒绝时，检查 stderr 和实际改动，再决定如何继续。[AGY 权限文档](https://antigravity.google/docs/permissions?tab=cli)
