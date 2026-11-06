# Codex AGY

Codex 决定技术方案并独立验收。AGY 通过原生 CLI 提供可行性反馈，并在授权范围内实现和测试。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill。

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

从旧版升级时，可从个人 Skill 目录中移除旧版的 `scripts/run_agy.py`、`references/protocol.md`、`references/result.schema.json` 和 `agents/openai.yaml`。

在目标项目的 Codex 对话中按需调用 `$codex-agy`。[SKILL.md](codex-agy/SKILL.md) 提供原生命令、会话续接和权限配置说明。
