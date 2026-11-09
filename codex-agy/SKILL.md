---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。采用薄契约直派、按需单轮评审、热缓存续接与宿主构建解耦，彻底消除轮询空转、权限死锁与 256K 压缩失忆。Codex 保留技术决策、构建验证和独立验收权。
---

# 高效调用 AGY（薄契约直派架构）

## 核心原则（针对性解决 8 大痛点）

1. **禁止轮询空转（防 Codex 额度爆炸）**：Codex 调用 `agy -p` 时必须使用**单次长超时同步等待**（把工具单次 `yield_time_ms` / timeout 拉到最大，或设 `--print-timeout 600s`）。**严禁每 30–60 秒循环发送空 `write_stdin(chars:"")` 轮询等待**，因为每次空轮询都会把 Codex 几十万 token 的上下文重新推理一遍。
2. **禁止越界扒库**：`agy -p --output-format json` 在回合结束前无流式输出属正常现象。**严禁 Codex 编写脚本读取或反序列化 `~/.gemini/antigravity-cli/` 下的内部数据库、`transcript.jsonl` 或 `.pb` 文件来监控进度**。
3. **单层直派，砍掉双进程传话筒**：默认由 **Codex 直接派发单个 AGY 会话**完成编码与修复。**严禁 Codex 在外部同时启动“AGY 负责人 + AGY 执行者”两个独立 `agy -p` 进程并在中间人工传话**，严禁跨独立 CLI 进程调用 `send_message`。
4. **禁止在 Prompt 中写 `/plan` 斜杠命令**：在 `agy -p` 提示词内写 `/plan` 会触发 AGY 内置的 1500 字 `<PLAN>` 宏展开（强制要求模型全库调研并写 Artifact 文件）。只读模式必须通过 CLI 参数 `--mode plan --disable-slash-commands` 控制。
5. **严防 256K 自动压缩失忆**：AGY 单会话上下文达到 **~256K tokens** 时会触发自动 Compaction（丢弃早期读取的源码签名细节，`cache_read_tokens` 归零），导致后续修改臆造 API。**单个 AGY 会话最多续接 2–3 轮**；若仍未收敛或上下文已超 150K，立即基于当前 Git 状态开新会话，只传剩余问题的文件与行号。
6. **移除仪式性探测与沙箱死锁**：**取消开工前的 `git status` / `AGY_WORKER_READY` 空跑探测会话**。若沙箱限制外部 JDK/Maven，让 AGY 仅用原生文件工具（`read_file` / `edit_file` / `write_file`）改代码，**由 Codex 在宿主环境统一跑构建与测试**，再把精简报错交回 AGY 修复。

---

## 从设计到验收（精简 4 步流）

### 1. Codex 定向锚定与薄契约设计
- Codex 用 `rg` 快速定位入口、契约与受影响文件（最多读取必要片段，不做全量重读）。
- **拒绝文书泛滥**：不在仓库中堆砌多份长篇设计文档、实施文档、Worker 委托书。直接整理一份精炼的**薄任务契约（Thin Spec，控制在 30–50 行内）**，包含：
  1. **业务目标与不可变边界**（改什么、保留什么、哪些接口/表/协议绝不能破）；
  2. **精确文件锚点清单**（列出目标源码与测试文件的绝对路径或相对路径、关键方法签名）；
  3. **局部修改铁律**（要求对已有业务类使用 `edit_file` 局部修改，**严禁 `write_file` 全文重写已有复杂类或臆造未核实的 Mapper/Service 方法**）；
  4. **验收测试点**。

### 2. 分级触发：单轮只读可行性评审（按需）
- **何时跳过评审**：需求边界明确、单模块局部改造、明确删减冗余代码、字段调整或常规 Bug 修复，Codex 直接向用户汇报薄契约方案，确认后直奔第 3 步实施。
- **何时触发评审**：仅当涉及跨服务契约、并发/锁/事务边界重构、复杂状态机改造或存在技术路线分歧时，调用一次旗舰模型 Medium 做**单轮（One-shot）只读评审**：
  ```bash
  agy --model '<旗舰 Medium 模型 ID>' --mode plan --disable-slash-commands --output-format json --print-timeout 300s \
    -p '只读评审以下方案。仅使用 read_file 读取列出的锚点文件（最多 8 个文件，禁止全库扫描、禁止写文件或运行命令）。直接指出：1. 方案是否可行；2. 与现有代码冲突或遗漏的边界；3. 必须修正项。控制在 500 字内。'
  ```
- **取消多轮辩论**：Codex 核实 AGY 的单轮评审意见后，直接吸收合理部分并向用户汇报最终方案等待确认，**不再为了“文字表态达成一致”反复续接评审会话**。

### 3. 用户确认后：热缓存直转实施（或单层直派）
收到用户对方案的明确确认后，启动 `accept-edits` 实施：
- **路径 A（做过第 2 步评审 —— 优先复用热缓存）**：
  **不要新开空白会话！** 直接用 `--conversation '<评审会话 ID>'` 续接刚才的评审会话（此时核心源码已在 Prompt Cache 中，仅 2–4 万 tokens），切换为 `--mode accept-edits`（及中档 High 模型）立即改代码，省去 15 分钟重复 `read_file`：
  ```bash
  agy --conversation '<评审 conversation_id>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --output-format json --print-timeout 600s \
    -p '用户已确认方案。请直接基于你刚才已读取的源码缓存开始实施，禁止重复全量 read_file。对已有类必须使用 edit_file 局部修改，严禁全文覆盖重写或编造不存在的方法。完成后简要返回改动文件清单。'
  ```
- **路径 B（跳过评审的任务 —— 单层直派执行者）**：
  直接启动一个中档 High（如 `gemini-3.8-flash-high`）或旗舰 Medium 会话完成编码：
  ```bash
  agy --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --output-format json --print-timeout 600s \
    -p '按以下已确认契约实施代码与测试修改。先定向读取列出的锚点文件（禁止全库扫描），再用 edit_file/write_file 完成修改。严禁全文重写已有复杂业务类。完成后返回改动摘要。'
  ```

### 4. Codex 宿主构建验证与集中修复
- AGY 返回后，Codex 先用 `git status --short` 和 `git diff` 检查实际改动范围与代码质量。
- **构建与测试由 Codex 在宿主环境直接执行**（如运行真实 JDK8 Maven `clean test` / `clean package`），并将完整构建日志重定向到 `/private/tmp/<task>-build.log`，只在 Codex 上下文中读取退出码与最后 30–50 行报错摘要。
- **集中返工（最多续接 1–2 次）**：
  - 若有编译错误、测试失败或审查问题，Codex 将**所有问题、精确文件行号及错误摘要一次性打包**，用 `--conversation '<实施会话 ID>'` 续接让 AGY 修复。
  - **防失忆熔断**：如果该会话已续接满 3 轮，或发现 AGY 开始重复读文件/遗忘签名（接近 256K 自动压缩线），**立即放弃旧 `conversation_id`**，基于当前已落盘的 Git 状态开一个全新会话，只传那几个报错文件的路径与修复指令。

---

## 模型与额度检查（轻量化）

- 每个 Codex 对话**仅在首次调用 AGY 前（或遭遇 429/额度报错时）**执行一次：
  ```bash
  agy models
  agy -p '/usage'
  ```
- **禁止在每次阶段切换或续接前重复运行**模型与额度查询。
- 选型规则：
  - **复杂方案单轮只读评审**：有额度的旗舰模型 Medium（如 `gemini-4-argon-medium` 或同档模型）。
  - **编码、测试与局部修复**：有额度的中档模型 High（如 `gemini-3.8-flash-high`）；若逻辑极其复杂或中档模型额度不足，可直接用旗舰模型 Medium 实施。
  - 优先直接使用 `agy models` 中自带推理档位后缀的模型 ID（如 `-medium`、`-high`）。

---

## 工作区、权限与多子任务规范

1. **文件夹即工作区（免 `--project` 折腾）**：
   - 始终在目标代码仓库根目录（解析符号链接后的真实路径）下执行 `agy`。
   - 默认无需传 `--project` 或 `--new-project`，也无需去检查 `~/.gemini/config/projects/*.json`，会话天然按当前工作目录归档与隔离。仅当用户明确要求绑定特定命名项目时才传 `--project`。
2. **权限配置从简，拒绝单文件白名单死锁**：
   - 生产代码、测试代码与实现配置由 AGY 修改，Codex 绝不与 AGY 同时并发写同一个工作区。
   - **不要用 `--settings` 构造只允许读几个文件的狭窄白名单**（会导致 AGY 读关联 DTO/Mapper 或 `/private/tmp` 日志时频繁报 `permission check failed`）。
   - 在已获用户确认的实施阶段，让 AGY 使用原生文件读写工具（`read_file`、`edit_file`、`write_file`）在工作区内自由读写源码，无需在 AGY 内部强跑复杂的外部构建命令；构建、Git 检查与测试统一由 Codex 在宿主环境执行。
3. **何时才使用内部 Subagent**：
   - 注意：AGY 内置工具 `invoke_subagent` 的 `Model` 参数仅支持 `inherit | flash_lite | flash | pro` 枚举，**不支持动态传入独立 `High` 推理档位**。
   - 因此，**单模块或文件有交集的任务一律单会话直派，禁止让 AGY 内部再拆子 Agent**。
   - 仅当超大任务跨多个互不依赖的子目录、确需并行时，才预先在 `.agents/agents/<worker>.md` 静态定义好带 YAML frontmatter 的子 Agent，再由 AGY 原生调用。
