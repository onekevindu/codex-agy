# Codex AGY

Codex 决定技术方案并独立验收。AGY 通过原生 CLI 提供可行性反馈，并在授权范围内实现和测试。

将 [AGENTS.md](AGENTS.md) 中的分工合并到目标项目的 `AGENTS.md`。确认 `agy` 已安装并登录，然后在本仓库根目录安装 Skill。

```bash
mkdir -p ~/.codex/skills/codex-agy
cp codex-agy/SKILL.md ~/.codex/skills/codex-agy/SKILL.md
```

从旧版升级时，可从个人 Skill 目录中移除旧版的 `scripts/run_agy.py`、`references/protocol.md`、`references/result.schema.json` 和 `agents/openai.yaml`。

在目标项目的 Codex 对话中按需调用 `$codex-agy`。[SKILL.md](codex-agy/SKILL.md) 提供原生命令、会话续接和权限配置说明。

## 架构与执行流程

```mermaid
flowchart TB
    subgraph DESIGN["需求、设计与评审"]
        U["用户提出需求与约束"]
        C["Codex 主控<br/>调查代码并完成详细开发设计"]
        R["AGY 只读可行性评审<br/>旗舰模型 · Medium"]
        J{"Codex 核实评审意见"}
        E["Codex 解释依据并提供证据"]
        A["双方认可同一版设计"]
        U --> C --> R --> J
        J -->|"设计确有问题，修订后复评"| C
        J -->|"分析前提或判断有误"| E --> R
        J -->|"分歧已解决"| A
    end

    A --> REPORT["Codex 向用户汇报最终设计"]
    REPORT --> CONFIRM{"用户明确确认"}
    CONFIRM -->|"调整要求"| C

    subgraph BUILD["实施、集成与验收"]
        M["AGY 负责人<br/>旗舰模型 · Medium<br/>拆分任务、协调依赖"]
        W["AGY 执行者<br/>中档模型 · High<br/>编码、测试与局部修复"]
        INTEGRATE["AGY 负责人<br/>集成、自检、组织修复<br/>集中提交结果与验证证据"]
        CHECK{"Codex 独立验收<br/>审查差异、构建、测试与受影响链路"}
        TROUBLE["Codex 排查权限与环境阻塞"]
        M -->|"内部工具派发"| W
        W --> INTEGRATE
        INTEGRATE -->|"内部核验发现问题"| W
        INTEGRATE --> CHECK
        CHECK -->|"集中反馈验收问题"| M
        M -->|"遇到阻塞"| TROUBLE -->|"恢复委托"| M
    end

    CONFIRM -->|"Codex 通过 Shell 派发定稿与验收条件"| M
    M -->|"需要实质改变设计，重新评审与确认"| C
    CHECK -->|"通过"| DONE["交付用户最终验收"]

    classDef codex fill:#dbeafe,stroke:#2563eb,color:#172554
    classDef agy fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef user fill:#fef3c7,stroke:#d97706,color:#78350f
    class C,J,E,REPORT,CHECK,TROUBLE codex
    class R,M,W,INTEGRATE agy
    class U,CONFIRM,DONE user
```

Codex 实际执行 AGY CLI 调用。AGY 负责人按已确认设计组织实现，生产代码、测试代码与实现配置由 AGY 执行者修改。定稿设计、Git 差异及验证日志作为交接和验收依据。设计评审续接原会话，确认后新开负责人实施会话，同一交付单元的返工优先续接。

内部子 Agent 的模型和推理档位配置、headless 调用能力须在正式派发前验证。并行写任务使用已授权的隔离工作树，或先核实文件修改范围互不重叠。共享契约和集成修改按依赖顺序执行。
