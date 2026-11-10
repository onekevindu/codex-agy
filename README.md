# Codex AGY

用额度充裕的 AGY（Gemini）分担重度代码调研、编码与本地构建自修复闭环，将主控 Codex 的额度集中在高价值的边界设定、技术决策与最终独立验收上。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill：

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

在目标项目的 Codex 对话中按需调用 `$codex-agy`。
- [SKILL.md](codex-agy/SKILL.md)：额度重平衡与执行自治规范（委托前极简立项、执行中 AGY 沙箱内编码+构建自测闭环、Codex 静默长等待与三不准纪律、交付后集中终验）。
- [CHANGELOG.md](CHANGELOG.md)：v2.1.0 额度重平衡复盘与全链路证据取证。

## 架构与执行流程（v2.1 额度重平衡与执行自治）

![Codex 与 AGY 架构及执行流程](assets/architecture.png)

[查看完整尺寸 PNG](assets/architecture.png)

### 四阶段协作原则

1. **委托前（Codex 极简立项）**：Codex 保护未提交基线，仅用 1–3 次 `rg` 定位入口，明确**目标、必要设计、不可变边界和验收条件**，不自行全量扫库撑爆主控上下文；若需跨多文件可行性核对，交由 AGY 单轮物理只读评审完成。
2. **执行中（AGY 自主闭环，Codex 静默等待）**：单层直派单个 AGY 会话（`--sandbox` + `proceed-in-sandbox`），由 AGY 自主完成**完整读取（≤800行一次读完，缺失必补读）、`edit_file` 局部修改、沙箱内运行本地 Maven/测试（日志写 `target/`，禁写 `/private/tmp`、禁 `BypassSandbox`）并自修到全绿**。期间 Codex 工具侧持续长等待，不按读取次数和耗时催写。
3. **交付后（Codex 集中终验）**：Codex 对 AGY 自测通过的代码集中审查 `git diff` 并做宿主独立验证，把实际遗漏问题一次性交回修复。
4. **出现阻塞时（定向排障）**：仅针对具体阻塞（如补齐某项路径权限或澄清边界）处理，避免重新调查整个任务。
