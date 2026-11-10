---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。采用薄契约直派、按需单轮只读评审、宿主长等待（yield_time_ms）、800行完整读取与宿主构建解耦。Codex 保留技术决策、基线保护、构建验证和独立验收权。
---

# 高效调用 AGY（v2.0 薄契约直派架构）

## 核心机制约束（直击 8 大底层根因）

1. **宿主长等待，禁止短轮询空转（防 Codex 额度爆炸）**
   - 控制 Codex 等待间隔的是宿主工具（`exec_command` / `write_stdin`）的 **`yield_time_ms`**，而非 `agy` 的 `--print-timeout`（后者只会导致 `agy` 到点自杀截断正在写代码的回合）。
   - 启动 `agy -p` 或等待其完成时，**必须将宿主 `exec_command` / `write_stdin` 的 `yield_time_ms` 设为工具支持的最大上限**，让操作系统挂起等待进程返回；`agy` 侧保持默认不限时（或仅设充裕兜底上限）。
   - **严禁以 1–30 秒短间隔循环发送空 `write_stdin(chars:"")` 轮询**，等待期间更**禁止夹带 `git diff`、`stat` 或编写脚本去解析 `~/.gemini/antigravity-cli/` 下的 `.pb` / `transcript.jsonl` 内部状态**。
2. **只读评审禁用 `--mode plan`，改用权限层物理只读**
   - 经对 `agy` 二进制反编译验证，CLI 参数 `--mode plan` 在底层会自动向会话注入 `/plan` 前缀，强制展开 1,500+ 字符的 `<PLAN>` 系统宏（要求模型全库遍历并生成 Artifact 计划文件），即使加 `--disable-slash-commands` 也无法阻止模式自身的注入。
   - 因此，**只读可行性评审一律不传 `--mode plan`、不在 Prompt 内写 `/plan`**，而是使用 `--mode accept-edits --disable-slash-commands` 配合 `--settings` 在权限层物理禁写（`deny: ["write_file(*)", "command(*)"]`，注：`agy` 权限引擎中 `write_file` 同时管辖 `write_file` 与 `edit_file`）。
3. **强制 800 行完整读取，严禁未读完全文就 `write_file` 重写，严禁盲目催写**
   - AGY 原生 `read_file` 工具单次最多支持 **800 行**（46,080 字节），且 `Path` **必须传入绝对路径**。
   - 必须在委托提示词中要求 AGY：**800 行以内的源码文件一次性完整读取（禁止按 100–150 行碎片化切片慢读）**；超过 800 行的文件必须读完尾部签名与私有 helper 后才能修改。
   - **对已有业务类必须使用 `edit_file` 局部修改，严禁在未读完文件全貌时调用 `write_file(Overwrite=true)` 全文覆盖重写或臆造未核实的 Mapper/Service 方法**。
   - **严禁 Codex 根据工具调用次数主观臆断“AGY 已读完所有依赖”并下达“禁止继续读取、立即写入”的指令**（此前 `PublicHealthIngestService` 580 行仅读到 450 行即被强令禁读，直接导致后 130 行被脑补重写并产生 11 个编译错误）。
4. **单层直派，砍掉外部双 CLI 进程传话筒**
   - 默认由 **Codex 直接派发单个 AGY 会话**完成编码与修复。**严禁 Codex 在外部同时启动“AGY 负责人 + AGY 执行者”两个独立 `agy -p` 进程并在中间传话或让其跨进程发 `send_message`**（外部独立进程无法实时共享上下文视野，极易变成盲目催促）。
5. **脏工作区基线保护（严禁误用 `git checkout HEAD` 回滚未提交基线）**
   - 若任务开始前工作区已有未提交的实现改动，Codex **必须先记录干净的恢复基线**（如 `git stash create` 记录 commit 对象，或将当前工作区完整打包备份到工作区内临时归档），**严禁在需要回滚单轮改动时直接执行 `git checkout HEAD` / `git reset --hard` / `git clean` 把前序未提交成果一并抹除**。
6. **移除仪式性探测与沙箱构建死锁**
   - **取消每次任务前的 `git status` / `AGY_WORKER_READY` 空跑探测会话**。
   - 构建与测试（如本地 JDK8 + Maven）涉及仓库外路径（`/Library/Java/...`、`/Applications/...`、`/private/tmp/...`），在 AGY 沙箱中极易触发 `unsandboxed` 或跨目录读取拒绝。**实施阶段让 AGY 专注用原生文件工具改代码与单测，由 Codex 在宿主环境统一执行构建测试**，再将精简报错回传修复。

---

## 从设计到验收（精简 4 步流）

### 1. Codex 确认基线、定向锚定与薄任务契约
- 检查 `git status --short`：若有未提交的前序成果，先保存基线快照。
- 用 `rg` 定位入口、契约与受影响文件，整理一份精炼的**薄任务契约（Thin Spec，默认控制在 30–60 行，复杂事务可按需扩展）**，包含：
  1. **业务目标与必须保留的既有行为**（先确认是否需要强语义，不自行扩张架构）；
  2. **目标文件绝对路径与关键方法签名锚点**；
  3. **实施边界**：要求用绝对路径调用 `read_file` 一次性读完单个文件（≤800 行不切片），用 `edit_file` 局部修改已有类，严禁全文覆盖重写；
  4. **验收标准**。

### 2. 分级触发：单轮物理只读可行性评审（按需）
- **何时跳过**：需求边界清晰、单模块局部改造、明确删减冗余或常规修复，向用户确认方案后直奔第 3 步。
- **何时触发**：涉及跨服务契约、并发/锁/事务边界、状态机重构或存在技术路线分歧时，用旗舰模型 Medium 做**单轮（One-shot）只读评审**（用 `--settings` 锁死只读，**不传 `--mode plan`**）：
  ```bash
  agy --project '<项目ID或名称>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands \
    --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)"],"deny":["write_file(*)","command(*)","mcp(*)","read_url(*)"]}}' \
    --output-format json \
    -p '只读可行性评审（禁止写文件或执行命令）。请用 read_file（传绝对路径，≤800行一次读完）读取以下锚点文件，直接指出：1. 方案是否可行；2. 与现有签名/事务/协议的冲突或遗漏边界；3. 必须修正项。'
  ```
- **单轮收敛**：Codex 核实 AGY 的评审意见后，采纳有效修正并向用户汇报最终方案等待明确确认，**不为了形式上的“文字认可”多轮续接辩论**。

### 3. 用户明确确认后：单层直派实施（复用上下文或新开执行会话）
收到用户明确确认后，放开工作区文件读写权限，启动单层实施：
- **若刚做过第 2 步评审且在同一工作区**：可用 `--conversation '<评审会话 ID>'` 续接该会话（传入允许 `write_file(/绝对路径/工作区根目录)` 的 `--settings`），让 AGY 基于已读源码上下文直接开始修改，或切换到有额度的中档 High 模型。
- **若跳过评审或需独立执行会话**：直接启动单个中档 High（如 `gemini-3.8-flash-high`）或旗舰 Medium 会话：
  ```bash
  agy --project '<项目ID或名称>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands \
    --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)","write_file(/绝对路径/工作区根目录)"],"deny":["command(*)","mcp(*)","read_url(*)"]}}' \
    --output-format json \
    -p '按以下已确认方案完成代码与测试修改。规则：1. 调用文件工具必须传绝对路径；2. 800行以内的文件一次 read_file 读完，禁止150行切片慢读；3. 对已有复杂业务类必须先读完首尾再用 edit_file 局部修改，严禁 write_file 全文重写或臆造不存在的 Mapper/DTO 方法；4. 无需运行外部 Maven 命令，完成后返回改动摘要，由 Codex 宿主立即执行构建验证。'
  ```

### 4. Codex 宿主构建验证与集中修复
- AGY 返回后，Codex 在宿主环境执行 `git diff` 审查与真实构建测试（如 JDK8 Maven `clean test` / `clean package`），构建耗时通常仅 ~10 秒。
- **集中返工与上下文卫生**：
  - 若有编译或测试问题，Codex 将**所有编译报错行号、真实方法签名与审查问题一次性汇总**，用 `--conversation '<实施会话 ID>'` 续接修复（若需读取 `/private/tmp` 下的日志或基线，必须在 `--settings` 中显式设置 `"allowNonWorkspaceAccess": true` 并加入 `read_file(/private/tmp/...)`，或直接把几十行报错摘要贴进 Prompt）。
  - **防上下文污染与压缩失忆**：当同一会话已历经多轮大文件读写、或观察到 `CHECKPOINT` 压缩/模型开始遗忘真实接口签名时，停止在旧会话上叠加，基于当前已确认的 Git 状态开启新会话，仅传入剩余待修文件的绝对路径与真实接口签名。

---

## 项目归属、模型与额度检查

1. **同名项目绑定（一次核对，免反复探测）**：
   - 在目标仓库根目录（`pwd -P` 解析符号链接后的绝对路径）启动 `agy`。
   - 每个对话首次委托时，可快速读取 `~/.gemini/config/projects/*.json` 选择名称匹配且 `projectResources.resources[]` 仅绑定当前目标仓库的精确项目 `id`（避免同名但关联了多个无关仓库的项目），后续调用直接复用 `--project '<项目 ID>'`。
2. **模型与额度检查（仅首次或遇 429 时执行）**：
   - 仅在当前 Codex 对话首次使用 AGY、或遇到配额/速率限制报错时运行一次：
     ```bash
     agy models
     agy -p '/usage'
     ```
   - 评审优先选有额度的旗舰模型 Medium（如 `gemini-4-argon-medium`）；编码与修复优先选中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
