# Changelog

## [2.0.1] - 2026-11-10 — 交叉审计加固（封堵 `--mode plan` 底层宏注入、`yield_time_ms` 轮询与 150 行切片半截重写漏洞）

结合 Codex 对日志的交叉复核与对本机 `/Users/du/.local/bin/agy` 二进制文件的逆向验证，进一步修正归因精度并封堵 4 个底层机制漏洞：

### 一、深层根因再校准（剥离表面现象与真实证据链）

1. **15:17 `PublicHealthIngestService` 被全文覆盖重写并产生 11 个编译错误的真正因果链**
   - **时间线校准**：`write_file(Overwrite=True)` 发生在 15:17（第 149 步），11 个编译错误出现在 15:24，而 256K 自动上下文压缩（`CHECKPOINT`）发生在 15:36（第 286 步）。因此该次重写并非由 15:36 的压缩触发。
   - **深层真相（非简单的“AGY 自以为掌握接口”）**：
     1. `PublicHealthIngestService.java` 全长 **580 行**。AGY 在 15:02（第 40、42、44 步）按 150 行切片只读了 `1–150`、`151–300`、`301–450` 行，**尚未读到第 `451–580` 行（所有私有 helper、明细表插入、状态更新所在位置）**。
     2. 15:09–15:15（第 126、131 步），Codex 扒取后台日志看到累计 46 次 `read_file`，**误判 AGY 已读完所有文件**，遂通过负责人 `send_message` 与第 131 步 Prompt 严令 AGY：**“你已读取46次源码和所有必要依赖……现在禁止重复全量阅读；立即写入”**。
     3. AGY 在“未读到 451–580 行原文（无法做 `edit_file` 匹配）”却被“强令禁止继续 `read_file`”的夹击下，于第 149 步调用 `write_file(Overwrite=True)` 凭空脑补了后 130 行。
     4. 15:24（第 218–221 步）AGY 试图从基线包解压并 `read_file(StartLine=420, EndLine=580)` 补读最后 130 行时，又被 Codex 配置的 `allowNonWorkspaceAccess: false` 权限当场拒绝。
2. **为什么 `--mode plan --disable-slash-commands` 仍不够安全？**
   - 经反编译 `/Users/du/.local/bin/agy` 二进制确认：CLI 的 `--mode plan` 在底层就是通过向会话注入 `/plan` 模式前缀实现的，会自动触发 1,500+ 字符的 `<PLAN>` 系统宏（要求全库调研并写 Artifact 计划文档）。
   - **根治方案**：只读评审**彻底弃用 `--mode plan`**，改用 `--mode accept-edits --disable-slash-commands` 搭配 `--settings` 的 `deny: ["write_file(*)", "command(*)"]` 实现纯净的物理只读。
3. **为什么 `--print-timeout` 不能替代宿主 `yield_time_ms`？**
   - `--print-timeout` 是 `agy` 进程的自杀时限（设短了会直接腰斩正在写代码的会话）；而当天 49 次空输出唤醒是因为 Codex 在宿主 `write_stdin` 工具中硬编码了 `"yield_time_ms": 30000`（30 秒）和 `1000`（1 秒），导致带着 42 万 Token 的历史上下文反复重放（累计输入 8,441 万 tokens）。
   - **根治方案**：在 `SKILL.md` 中直接约束 Codex 宿主的 `exec_command` / `write_stdin` 必须将 `yield_time_ms` 设为工具最大上限，且 `agy` 侧不设短 `--print-timeout`。
4. **脏工作区误回滚（`git checkout HEAD` 抹除未提交基线）**
   - 11:24 回滚单轮修改时，Codex 对包含前序未提交 MQ 实现的工作区直接执行了恢复 `HEAD`，导致前序成果被清空，耗费大量时间从历史 `transcript.jsonl` 重建。
   - **根治方案**：开工前若工作区有未提交改动，强制先创建快照或 `git stash create` 基线，严禁直接恢复 `HEAD`。

---

## [2.0.0] - 2026-11-09 — 薄契约直派架构重构

1. **架构降维**：取消常态化“Codex $\rightarrow$ AGY 负责人 $\rightarrow$ AGY 执行者”双 CLI 进程传话结构，默认由 Codex 单层直派单个 AGY 会话。
2. **宿主构建解耦**：AGY 专注用原生文件工具（传绝对路径、800 行一次读完、`edit_file` 局部修改）完成编码；真实 JDK/Maven 构建与测试由 Codex 在宿主环境执行（单次仅 ~10 秒），彻底消除沙箱 `unsandboxed` 与跨目录日志读取死锁。
3. **分级单轮评审与上下文复用**：仅复杂架构/事务重构触发单轮只读评审，取消多轮辩论；支持复用评审会话上下文或按精确签名锚点直派实施。
4. **同名项目精确匹配**：通过 `~/.gemini/config/projects/*.json` 一次核对仅绑定当前单仓库的同名项目 `id`，避免关联多仓库的同名项目污染范围。
