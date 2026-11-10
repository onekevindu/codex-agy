# Changelog

## [2.4.0] - 2026-11-10 — 移除自定义包装脚本，回归 100% 纯原生 `agy` 跨机可移植方案

1. **移除 `bin/agy-delegate` 外部脚本依赖，换机/分享开箱即用**：
   - 撤除自定义包装脚本，回归纯 `SKILL.md` 单文件形态，任何机器只需安装官方 `agy` 并复制 `SKILL.md` 即可直接使用。
2. **原生参数实现跨机免配置完整权限 + 破坏性命令拦截**：
   - 实施与续接命令直接使用 `agy` 原生 `--mode accept-edits --disable-slash-commands --dangerously-skip-permissions` 配合 `--settings '{"permissions":{"deny":["command(git reset)","command(git checkout)","command(git restore)","command(git clean)"]}}'`（`agy` 内核保证 `--dangerously-skip-permissions` 自动放行工作区内外读写与构建命令，同时严格生效显式 `deny` 规则，无需手动修改每台电脑的 `settings.json`）。
3. **保留 Codex V8 内置 `while` 循环 + `functions.wait` 持续等待机制**：
   - 在 `functions.exec` 中通过 `// @exec: {"yield_time_ms": 300000}` 与 `while (res.session_id !== undefined)` 串联 `exec_command`（30s）与 `write_stdin`（300s），5 分钟内 0 次中途唤醒；超过 5 分钟返回 `Script running with cell ID <cell_id>` 时，通过 `functions.wait` 继续等待原 `cell_id`。

---

## [2.3.0 / 2.3.1] - 2026-11-10 — 定位 Codex V8 `exec` 30s 唤醒根因与 `functions.wait` 续等机制

- 排查 `rollout-2026-11-09T09-53-04.jsonl` 的 `additional_tools` 声明与 205 次 `exec` 调用源码，确认 `tools.exec_command` 单次等待物理上限为 `30000 ms`，而 `tools.write_stdin` 空轮询支持 `300000 ms`（5 分钟）；确立 V8 内置 `while` 循环 + 超时后 `functions.wait` 绑定 `cell_id` 的标准等待范式。
- 修正只读评估（`deny: ["write_file(*)", "command(*)", "mcp(*)", "read_url(*)"]`）与 `--project` 省略时归属 `default-cli-project` 的机制说明。

---

## [2.2.0 / 2.2.1] - 2026-11-10 — 彻底去微观管理化（不把 AGY 当傻子：只定目标与边界）

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
