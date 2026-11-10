# Codex AGY

用额度充裕的 AGY（Gemini）分担代码调研、实现与自测闭环，节省主控 Codex 的额度。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill（零外部脚本依赖，换机或分享他人直接复制 `SKILL.md` 即可使用）：

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

在目标项目的 Codex 对话中按需调用 `$codex-agy`。
- [SKILL.md](codex-agy/SKILL.md)：纯原生 `agy` 调用规范与 Codex V8 零唤醒等待模板。
- [CHANGELOG.md](CHANGELOG.md)：问题排查复盘与版本演进记录。

## 架构与执行流程

![Codex 与 AGY 架构及执行流程](assets/architecture.png)

[查看完整尺寸 PNG](assets/architecture.png)

### 协作四原则

1. **委托前**：Codex 讲清楚**业务目标、必要设计、不可变边界和验收条件**，不对 AGY 做过度限制或手把手指导。复杂方案可按需请 AGY 做单轮只读评估。
2. **执行中**：单层直派原生 `agy` 会话，由 AGY 自主完成阅读、编码、运行测试与局部纠错；Codex 在 `functions.exec` V8 沙箱内用 `while` 循环与 `functions.wait` 持续等待，不高频轮询、不按读取次数和耗时催写。
3. **交付后**：Codex 核对返回 JSON（`conversation_id`、`status`、`denied_actions`），集中审查 `git diff` 并执行独立验证，把实际问题一次性交回 AGY。
4. **出现阻塞时**：针对具体阻塞定向处理，Codex 绝不亲自下场改业务代码。
