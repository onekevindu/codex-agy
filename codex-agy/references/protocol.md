# 交接协议与调用方式

## 任务说明

任务说明使用 Markdown，按实际任务填写。短任务可合并段落，必须让 AGY 知道目标、批准方案和边界。

```text
本次任务标识及用途
项目绝对路径与适用项目规则
用户原始需求及本次目标
批准的方案和关键决定
验收条件与建议验证命令
允许修改的范围、已有改动及需保留的内容
必须上报并等待答复的问题
此前已完成的工作、相关调用目录、这次需要继续的部分
```

脚本自动追加执行边界与返回格式规则。`--mode plan` 用于分析，`--mode accept-edits` 用于实施。模式和提示中的范围须一致。脚本不提供文件范围沙箱，`plan` 也不作为操作系统级只读隔离的证明。对严格只读要求使用经过验证的 CLI 权限或隔离环境，并检查前后差异。

## 调用

在本次任务的可写目录保存任务说明与调用记录，避免将日志加入产品源码。将示例路径替换为已确认的绝对路径。

```bash
python3 /absolute/skill/codex-agy/scripts/run_agy.py \
  --cwd /absolute/project \
  --task-file /absolute/task/request.md \
  --output-dir /absolute/task/run-001 \
  --mode plan
```

实现时使用 `--mode accept-edits`。账户支持且符合授权时，可选择 `--mode auto`。本机测试账户提示 `auto` 不可用并回退到默认模式，因此必须检查 stderr 的模式降级提示。可选参数包括 `--project`、`--model`、`--effort`、`--settings-file` 和 `--timeout-seconds`。默认继承 AGY 模型配置，项目参数仅在用户或环境已指定项目时传入。任何命名项目都应核实其工作区与 `--cwd` 一致。超时默认为 0，按任务需要设置上限，Codex 负责持续监控。`--settings-file` 传入单次调用设置，按实际已授权动作配置。

CLI 参数已根据本机 `agy --help` 核对。升级后若参数发生变化，以本机帮助为准，先修复调用适配。

## 返回文件

- `request.md` 保存包含执行与回传规则的实际输入。
- `stdout.json` 保存 CLI 原始 JSON 信封，其中 `structured_output` 是 AGY 报告，`response` 是原始响应。
- `stderr.log` 保存诊断，包括权限拒绝。
- `run.json` 保存运行起止时间、工作区、命名项目、请求续接的会话 ID、进程退出码及超时或中断信息。

每次使用新结果目录，旧记录禁止覆盖。脚本在同一工作区的并发调用间使用 POSIX 文件锁。锁在临时目录按工作区真实路径标识，只协调本脚本实例。外部编辑器、其他脚本或其他工作区共享的数据库等资源需要 Codex 按实际任务协调。

AGY 按 [result.schema.json](result.schema.json) 返回结果。`status` 使用 `COMPLETED`、`NEED_CLARIFICATION`、`DESIGN_CONFLICT`、`BLOCKED`。附带摘要、已完成工作、改动文件、验证记录、未解决事项、需决定的问题和建议。数组无内容时返回空数组。验证记录包含命令、运行目录、结果及日志位置，明确哪些检查未运行。`COMPLETED` 仅针对本次委托。

脚本只执行一次调用并保存证据。Codex 阅读结果后自主决定是否再次调用。权限软拒绝可能伴随进程退出码 0，因此同时检查 stderr、报告及实际代码。本机实测还出现 CLI `status=SUCCESS`、空 `response` 和 `denied_actions` 包含 `write_file` 的组合，应视为执行受阻。此行为和 JSON 信封字段依据 AGY 官方说明。[Antigravity Headless mode](https://antigravity.google/docs/cli/headless)

## 续接与异常

首次委托和独立委托创建新会话。同一项委托需要澄清、续做或返工时，在下一次调用加上 `--resume-from /absolute/task/run-001`，并为本轮使用新的 `--output-dir`。脚本从上一轮的 `stdout.json` 读取 `conversation_id`，核对 `run.json` 中的目录和命名项目，再用 `agy --conversation` 续接。前几版记录没有 `project` 字段，只有能确认原调用未指定命名项目时才用它续接。[Antigravity CLI 续接文档](https://antigravity.google/docs/cli/headless#continue-a-conversation)

下一次任务说明写明新的解释或决定及剩余工作。核对返回的 `conversation_id` 与请求续接的 ID 一致。会话无法恢复时，检查现有改动和日志，汇总当前方案与进度后开启新会话。用户可在同一个 Codex 对话中完成整个交接。

若脚本进程被强制终止，`run.json` 可能停留在 `RUNNING`。先核对记录的进程与工作区活动，确认前次任务结束后再发出新委托。超时与正常取消会尝试终止本次 CLI 进程组，AGY 后台服务是否仍有工作需由 Codex 检查实际现场。

## 行为检查案例

- 批准方案指定 Redis 锁，AGY 建议换数据库锁。Codex 核实原因并明确决策后再委托。
- 方案明确要求添加数据库字段。AGY 可自行组织迁移和编码步骤，在范围内实施。
- AGY 因变量含义不清返回疑问。Codex 给出解释和剩余目标，再次调用。
- AGY 报告完成但 stderr 存在测试权限拒绝。Codex 补足必要验证后判断结果。
- AGY 调用超时但已修改文件。Codex 检查部分改动，针对剩余任务重新委托。
- 用户已有未提交改动。Codex 以调用前现场为基线审查，保护已有内容。

Skill 使用标准 `SKILL.md`、可选脚本和 UI 元数据结构。[OpenAI Skill 文档](https://learn.chatgpt.com/docs/build-skills)
