# Codex AGY

在同一个 Codex 对话里规划、委托和验收开发任务。Codex 制定方案和验收标准，Antigravity CLI（`agy`）负责可行性分析、编码和修复。AGY 在批准的方案内选择实现方式，遇到需要调整技术方向的问题时交回 Codex。

## 安装与使用

需要 Codex、Python 3，以及已登录且可从命令行运行的 `agy`。调用脚本使用 POSIX 文件锁，适用于 macOS 和 Linux。

将本仓库中的 `codex-agy` 文件夹完整复制到你的 Codex 个人 Skill 目录。例如，在仓库根目录执行：

```bash
mkdir -p ~/.codex/skills
cp -R codex-agy ~/.codex/skills/
```

在目标项目的 Codex 对话中输入：

> 使用 $codex-agy 完成这个需求，由你规划、委托 AGY 实现并验收。

## 项目结构

| 文件 | 用途 |
| --- | --- |
| [SKILL.md](codex-agy/SKILL.md) | Codex 的委托、决策和验收规则 |
| [交接协议](codex-agy/references/protocol.md) | 调用方法、权限边界及异常处理 |
| [结果 Schema](codex-agy/references/result.schema.json) | AGY 的结构化回传格式 |
| [调用脚本](codex-agy/scripts/run_agy.py) | 单次执行、日志和退出状态记录 |

使用 `plan` 进行可行性分析，使用 `accept-edits` 执行已授权的修改。AGY 的文件与命令权限由运行环境配置，Codex 根据实际改动和独立验证结果判断任务是否完成。
