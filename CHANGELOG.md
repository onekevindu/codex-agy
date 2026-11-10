# Changelog

## [2.1.0] - 2026-11-10 — 额度重平衡与执行自治架构（解决“Codex 额度耗尽 100%、Gemini 仅耗 6%”的本末倒置）

### 一、直击核心矛盾：为什么把编码交出去，Codex 额度反而比自己干还快耗尽？

复盘整个任务的终极失败指标：**用户引入 AGY（Gemini）是为了分担工作、节省主控 Codex 的宝贵额度；结果任务结束时 Codex 额度被彻底烧光，而 Gemini 额度仅消耗了 6%。**

根本原因在于**“只把敲代码交了出去，却没有把执行过程的自主权交出去”**：
1. **委托前 Codex 自己干了重体力调研**：Codex 自己在仓库里执行了 76 次搜索/文件读取、跨 3 个微服务比对实现、撰写 5 份长篇设计/委托文档，在还没调 AGY 前就把自己的上下文撑到了 30 万～42 万 tokens。
2. **执行中 Codex 高频监工**：每隔 1～30 秒唤醒自己 40 万 token 的上下文去轮询、看 `git diff`、解析 AGY 内部数据库、按读取次数发催写指令。
3. **打断 AGY 的沙箱自测闭环，把 Codex 变成“人肉编译器”**：
   - 核查 `31cd7989` 原始记录（第 212、276、280、371–529 步）发现：**AGY 在 `--sandbox`（`proceed-in-sandbox`）下原本完全可以自己运行 JDK8 Maven 编译与单测（13 次成功，每次仅 6 秒）**！
   - 唯一一次失败（第 276/280 步）是因为 Codex 要求把日志重定向到 `/private/tmp/ph-four-implementation-build.log`，在 macOS Seatbelt 沙箱下覆盖已有 `/private/tmp` 文件触发 `zsh:1: operation not permitted`，导致 AGY 误以为沙箱拦截了 Maven 而尝试 `BypassSandbox=true` 被拒。
   - 如果不让 AGY 在自己回合内完成“编码 $\rightarrow$ 本地编译测试 $\rightarrow$ 自修报错”闭环，而是每次小错都退回给 Codex 编译再续接，Codex 就会在多轮往返中被迅速吸干额度。

---

### 二、v2.1.0 核心重构：四个阶段的彻底减负与自治下放

1. **委托前（Codex 极简立项，重度调研下放 AGY）**
   - Codex 只用 1–3 次 `rg` 定位入口并保护未提交基线，明确**目标、必要设计、不可变边界与验收条件**；绝不自行全量扫库把几万行源码塞进主控上下文。
2. **执行中（AGY 沙箱内“读取 + 编码 + 构建自修复”全闭环自治）**
   - 赋予 AGY `--sandbox` + `toolPermission: "proceed-in-sandbox"` 权限，允许其在工作区内自由读写源码并直接运行本地 Maven/测试命令。
   - **破除沙箱构建伪阻塞**：明确要求 AGY 直接读命令标准输出或将构建日志写入工作区内 `target/agy-build.log`，**严禁重定向到 `/private/tmp`，严禁设置 `BypassSandbox=true`**。AGY 必须在单回合内自主把代码和单测修到全绿再返回。
   - **Codex 静默长等待与“三不准”**：工具侧拉满 `yield_time_ms` 持续等待，不轮询、不扒内部状态库、不凭读取次数或耗时催写、不禁止缺失原文（如 `PublicHealthIngestService` 451–580 行）的必要定向补读。
3. **交付后（Codex 一次性集中终验）**
   - AGY 交付全绿结果后，Codex 集中审查 `git diff` 并做一次宿主构建终验；若有遗漏问题一次性打包交回。
4. **出现阻塞时（定向排障，不重查全局）**
   - 仅针对具体阻塞点（如补齐某个路径权限或澄清业务边界）定点恢复，绝不推翻重来。

---

## [2.0.2] - 2026-11-10 — 双 Agent 交叉审计共识（确立完整因果链与双向边界）

- **校准 `PublicHealthIngestService` 11 处编译错误的完整因果链**：`15:02` AGY 分三次仅读 `1–450/580` 行 $\rightarrow$ `15:09–15:15` Codex 凭“已读 46 次”误判读完并借负责人与 Prompt 双重催写禁读 $\rightarrow$ `15:17` AGY 未补读 `451–580` 行便违反局部修改要求用 `write_file(Overwrite=true)` 全文生成 $\rightarrow$ `15:24` AGY 解压基线试图补读 `420–580` 行又被 `/private/tmp` 权限拒绝 $\rightarrow$ `15:36` 触发 256K 自动压缩。
- **校准缓存成本**：按 GPT-6.1 Sol 官方 Standard credits（缓存输入单价为普通输入的 5%），全天 8,364 万缓存输入对应的 credits 仍达 77.5 万未缓存输入的 **5.4 倍**。

---

## [2.0.1] - 2026-11-10 — 封堵 `--mode plan` 底层宏注入与脏工作区误回滚

- **弃用 `--mode plan`**：反编译 `/Users/du/.local/bin/agy` 证实 `--mode plan` 底层自动注入 `/plan` 宏；只读评审改用 `--mode accept-edits --disable-slash-commands` 搭配 `--settings` 物理禁写（`deny: ["write_file(*)","command(*)"]`）。
- **脏工作区基线保护**：开工前若有未提交改动，必须先建快照或 `git stash create`，严禁在回滚单轮改动时直接恢复 `git HEAD`。
