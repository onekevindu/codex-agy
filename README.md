# Codex AGY

Codex 负责理解需求、锚定关键文件、制定薄契约方案并执行宿主构建与独立验收；AGY 通过原生 CLI（`agy -p`）按需提供单轮只读可行性反馈，并在授权范围内高效完成生产代码、测试代码与配置的局部修改。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill：

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

在目标项目的 Codex 对话中按需调用 `$codex-agy`。
- [SKILL.md](codex-agy/SKILL.md)：薄契约直派、按需单轮评审、热缓存续接、防 256K 压缩失忆与防轮询空转规范。
- [CHANGELOG.md](CHANGELOG.md)：v2.0 架构重构复盘与 8 大核心痛点取证分析。

## 架构与执行流程（v2.0 薄契约直派）

![Codex 与 AGY 架构及执行流程](assets/architecture.png)

[查看完整尺寸 PNG](assets/architecture.png)

### 核心机制

1. **薄契约直派（砍掉中间传话层）**：Codex 用 `rg` 快速定位核心文件锚点，整理 30–50 行以内的薄任务契约，直接派发给单个 AGY 会话，不在外部同时维护“负责人 + 执行者”双进程。
2. **分级单轮评审与热缓存复用**：常规局部改动确认后直派实施；复杂架构/事务重构触发单轮只读评审（`--mode plan --disable-slash-commands`），用户确认后直接 `--conversation` 续接该评审会话切入 `accept-edits` 编码，零成本复用已读源码热缓存。
3. **宿主构建解耦与防轮询空转**：AGY 专注用原生文件工具（`edit_file` 优先）改代码，Maven/测试构建由 Codex 在宿主环境统一执行；调用 `agy -p` 采用单次长超时同步等待，严禁 30 秒空轮询与越界读取 AGY 内部数据库。
4. **256K 压缩防失忆熔断**：单个 AGY 会话最多续接 2–3 轮；若仍有收尾项，基于已落盘的 Git 状态开启干净新会话，防止触发 256K 自动上下文压缩导致丢失方法签名与臆造 API。
