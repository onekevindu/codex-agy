# Codex AGY

Codex 负责理解需求、保护未提交基线、锚定关键文件、制定薄任务契约并执行宿主构建与独立验收；AGY 通过原生 CLI（`agy -p`）按需提供单轮物理只读可行性反馈，并在授权范围内用原生文件工具完成生产代码、测试代码与配置的局部修改。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill：

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

在目标项目的 Codex 对话中按需调用 `$codex-agy`。
- [SKILL.md](codex-agy/SKILL.md)：薄契约直派、物理只读单轮评审、宿主 `yield_time_ms` 长等待、800 行完整读取与防半截重写、脏基线保护与宿主构建验收规范。
- [CHANGELOG.md](CHANGELOG.md)：v2.0 / v2.0.1 架构重构复盘与底层机制取证（含 `PublicHealthIngestService` 451–580 行漏读强令重写事件、`--mode plan` 二进制宏注入与 `yield_time_ms` 空转账单剖析）。

## 架构与执行流程（v2.0.1）

![Codex 与 AGY 架构及执行流程](assets/architecture.png)

[查看完整尺寸 PNG](assets/architecture.png)

### 核心机制

1. **薄契约单层直派（砍掉双进程传话层）**：Codex 先保护未提交基线，用 `rg` 定位核心文件与真实方法签名，直接派发给单个 AGY 会话，不在外部同时维护“负责人 + 执行者”双 CLI 进程。
2. **分级单轮物理只读评审**：常规局部改动确认后直派实施；复杂架构/事务重构触发单轮只读评审（通过 `--settings` 设 `deny: ["write_file(*)","command(*)"]` 物理锁死只读，弃用会自动注入 1,500 字 `<PLAN>` 宏的 `--mode plan`）。
3. **800 行完整读取 + 局部编辑铁律**：要求 AGY 使用绝对路径调用 `read_file` 一次性读完 ≤800 行的文件（严禁 150 行碎片化切片慢读），严禁 Codex 根据读取次数盲目下令禁读催写，对已有复杂业务类强制使用 `edit_file` 局部修改。
4. **宿主长等待与宿主构建解耦**：Codex 调用 `exec_command` / `write_stdin` 必须将 `yield_time_ms` 拉到最大上限（严禁 30 秒空轮询与扒内部状态库）；JDK/Maven 构建测试统一由 Codex 在宿主环境执行（单次仅 ~10 秒），彻底消除沙箱权限死锁。
