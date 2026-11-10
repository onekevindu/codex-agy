# Changelog

## [2.3.0] - 2026-11-10 — 用代码机制替代口头约定：V8 内置 `while` 零唤醒循环 + `agy-delegate` 确定性包装器

深入排查 Codex 底层 `rollout-2026-11-09T09-53-04.jsonl` 的 `additional_tools` 声明与 205 次 `exec` 调用源码后，定位到 Codex 频繁唤醒的物理根因，并用确定性代码机制彻底替代软性文字叮嘱：

1. **V8 `exec` 内置 `while` 循环，彻底消灭 30 秒空轮询唤醒**：
   - **底层根因**：Codex 的 `tools.exec_command` 单次等待物理上限仅为 `30000 ms`（30 秒），外层 `exec`（JavaScript V8 沙箱）默认 `yield_time_ms` 也是 `30000 ms`，而 `tools.write_stdin` 空轮询最高支持 `300000 ms`（5 分钟）。此前 Codex 每次只写单行 `write_stdin(30000)` 甚至设置 `// @exec: {"yield_time_ms": 1000}`，导致每 30 秒必退回大模型重跑一次完整上下文。
   - **机制根治**：在 `SKILL.md` 中固化带 `// @exec: {"yield_time_ms": 300000}` 头部的 V8 `while (res.session_id !== undefined)` 标准循环模板。`exec_command` 满 30 秒返回 `session_id` 后直接在 V8 内部无缝切入 `write_stdin(300000)`，**5 分钟内的任务实现 0 次模型中途唤醒**。
2. **新增 `/Users/du/.local/bin/agy-delegate`（[bin/agy-delegate](bin/agy-delegate)）确定性包装脚本**：
   - **自动匹配项目 ID 与明确回退归属**：自动解析 `~/.gemini/config/projects/*.json` 匹配当前工作区根目录并传入 `--project <id>`；若无匹配项目则省略 `--project`，会话归属至 `default-cli-project`（`CLI Project`）。
   - **严格的只读评估隔离（`agy-delegate review`）**：将 `review` 模式的 `toolPermission` 显式覆盖为 `"request-review"` 并开启沙箱，禁止 `write_file(*)`，且仅使用合法的词前缀规则（`command(git status)`、`command(git diff)`、`command(git log)`、`command(git show)`）白名单放行只读 Git 命令，其余任意终端命令在 headless 模式下均被自动拒绝（修复此前在 `always-proceed` 下仅靠 `command(rm*)` 等错误 glob 黑名单无法拦截其他写命令的问题）。
   - **自动脏工作区快照与一键无损回滚（`agy-delegate restore`）**：在 `run` / `resume` 执行前自动备份工作区已修改和未跟踪源码至 `/tmp/agy-snapshots/`，并提供 `agy-delegate restore <snapshot_dir>` 一键精确还原，物理杜绝误用 `git checkout/restore HEAD` 抹掉未提交成果。
   - **自动校验 JSON 与 `denied_actions`**：自动解析 `agy` 返回的 JSON，若 `status != "SUCCESS"` 或 `denied_actions` 非空，直接以退出码 `2` 报错，消除退出码 `0` 软拒绝误判。

---

## [2.2.1] - 2026-11-10 — 全局完整权限固化与 Codex 唤醒防线收口

1. **全局权限下沉至 `settings.json`，彻底移除命令行 `--sandbox --settings` 枷锁**：
   - 在 `~/.gemini/antigravity-cli/settings.json` 中固化全局完整权限（`"toolPermission": "always-proceed"`, `"allowNonWorkspaceAccess": true`, `"enableTerminalSandbox": false`），并清理 `~/.gemini/config/projects/*.json` 中残留的项目级询问策略。
2. **收紧对 Codex 自身行为的硬性约束**：
   - 补齐纯续等铁律、JSON `denied_actions` 完成判定、职责红线（生产/测试代码始终由 AGY 修改，Codex 绝不亲自下场写代码）及细节修正。

---

## [2.2.0] - 2026-11-10 — 彻底去微观管理化（不把 AGY 当傻子：只定目标与边界，不做过度限制与过度指导）

- 移除提示词中对 AGY 工具用法的琐碎说教（如“≤800行一次读完”、“必须传绝对路径”、“核实真实签名”、“日志写到 `target/`”等），回归“委托前定目标与边界 $\rightarrow$ 执行中 AGY 自治闭环 $\rightarrow$ 交付后一次集中终验 $\rightarrow$ 阻塞时定向排障”的四阶段极简契约。

---

## [2.1.0] - 2026-11-10 — 额度重平衡与执行自治架构（解决“Codex 额度耗尽 100%、Gemini 仅耗 6%”）

- **根因总结**：11 月 9 日全天 Codex 共触发 323 次模型调用、累计 8,441 万输入 tokens；其中仅最后一轮“四表实施”就包含 49 次 `yield_time_ms: 30000` 空等待返回，直接触发的下一次模型唤醒累计携带 1,832 万输入 tokens。再加上 Codex 委托前自己做了 76 次代码搜索读取、通过负责人双进程传话催写、用单文件白名单和 `/private/tmp` 日志重定向制造沙箱冲突，导致省下的编码消耗被监工和返工消耗成倍抵消。
- **核心改进**：砍掉外部“AGY 负责人”传话层，放开工作区完整权限与构建自检权限，让 AGY 端到端修到构建全绿再返回。

---

## [2.0.1 / 2.0.2] - 2026-11-10 — 交叉审计底层机制取证

- **`PublicHealthIngestService` 11 处编译错误的真实因果链**：`15:02` AGY 分段读取了 `1–450/580` 行 $\rightarrow$ `15:09–15:15` Codex 仅凭“已读 46 次”误判读完并下令停止全量阅读、立即写入 $\rightarrow$ `15:17` AGY 在缺失 `451–580` 行原文时整体重写该类 $\rightarrow$ `15:24` AGY 解压基线试图补读 `420–580` 行被 `/private/tmp` 权限拒绝 $\rightarrow$ `15:36` 触发 256K 自动压缩。
- **弃用 `--mode plan`**：反编译 `/Users/du/.local/bin/agy` 证实 `--mode plan` 底层自动注入 `/plan` 宏；只读评估改用 `--mode accept-edits --disable-slash-commands` 搭配 `--settings` 物理禁写。
- **脏工作区基线保护**：防止在存在未提交改动时误用 `git checkout/restore` 清空前序实现。
