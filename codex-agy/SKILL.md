---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。采用薄契约直派、按需单轮物理只读评审、宿主长等待（yield_time_ms）、允许必要补读与局部修改铁律。Codex 保留技术决策、基线保护、构建验证和独立验收权。
---

# 高效调用 AGY（v2.0.2 交叉审计定稿）

## 核心机制约束（Codex 与 AGY 双向硬边界）

1. **对 Codex 的“三不准”指挥纪律（防瞎指挥催生重写灾难）**
   - **不准凭读取次数或耗时宣布“上下文已充分”**：读取次数多（如 150 行切片读了 40 次）不代表文件已读完整（如 580 行文件只读到 450 行），更不代表关联 Mapper/DTO 签名已掌握。
   - **不准用“停止阅读、立即写入”的催写指令施压**：严禁在委托或续接 Prompt 中写“你已读完所有依赖，禁止再读文件，立即写入”。
   - **不准把缺失原文的定向补读当成无效工作**：即使续接已有会话，只要待修改的目标区间、本类尾部私有方法或关联接口签名尚未读取，**必须允许并要求 AGY 先定向补读原文再修改**。
2. **对 AGY 的“先读全、再局部改”执行铁律**
   - AGY 原生 `read_file` 单次支持 **800 行**（46,080 字节），`Path` **必须传入绝对路径**。800 行以内的源码文件应一次性完整读完，禁止按 100–150 行碎片化切片慢读导致漏掉文件尾部 helper。
   - **对已有业务类必须使用 `edit_file` 局部修改**：若发现目标行区间或依赖的 Mapper/Service 签名尚未读入上下文，**必须先定向 `read_file` 补齐真实原文**，严禁在缺失原文时调用 `write_file(Overwrite=true)` 全文重新生成已有业务类或臆造方法名。
3. **宿主持续等待，禁止短轮询唤醒模型（防 Codex 额度空转）**
   - 控制等待间隔的是 Codex 宿主工具（`exec_command` / `write_stdin`）的 **`yield_time_ms`**，而非 `agy` 的 `--print-timeout`（后者只会导致 `agy` 到点自杀截断正在执行的回合）。
   - 调用 `agy -p` 时，应将宿主工具单次等待拉到上限，尽量在工具侧完成等待后再返回模型；**严禁显式硬编码 `yield_time_ms: 1000` 或 `30000` 循环空轮询**，等待期间更**禁止夹带 `git diff`、`stat` 或解析 `~/.gemini/antigravity-cli/` 内部 `.pb` / `transcript.jsonl` 记录**。
4. **只读评审禁用 `--mode plan`，改用权限层物理只读**
   - `agy` CLI 的 `--mode plan` 在二进制底层会自动注入 `/plan` 前缀，强制展开 1,500+ 字符的 `<PLAN>` 系统宏（要求全库调研并写 Artifact 计划文档），加 `--disable-slash-commands` 也无法阻止模式自身的注入。
   - 只读可行性评审**一律不传 `--mode plan`、不在 Prompt 内写 `/plan`**，改用 `--mode accept-edits --disable-slash-commands` 配合 `--settings` 在权限层物理禁写（`deny: ["write_file(*)", "command(*)"]`）。
5. **单层直派，砍掉外部双 CLI 进程传话筒**
   - 默认由 **Codex 直接派发单个 AGY 会话**完成编码与修复。**严禁在外部同时启动“AGY 负责人 + AGY 执行者”两个独立 `agy -p` 进程传话或发 `send_message`**（负责人未读源码细节却转发催写指令，只会放大指挥错误）。
6. **权限与交付要求一致 + 宿主构建解耦 + 脏工作区基线保护**
   - **权限一致**：若要求 AGY 读取 `/private/tmp` 下的基线或日志，必须在 `--settings` 中开启 `"allowNonWorkspaceAccess": true` 并显式加入 `read_file(/private/tmp/...)`；否则直接由 Codex 把关键信息内嵌在 Prompt 中。
   - **宿主构建**：本地 JDK/Maven 构建与测试统一由 Codex 在宿主环境执行（约 10 秒），不在 AGY 沙箱内折腾跨目录构建权限，也不做开工前 `git status` / `AGY_WORKER_READY` 仪式性探测。
   - **基线保护**：若工作区存在未提交的前序实现，开工前必须先保存快照或 `git stash create`，**严禁在回滚单轮修改时直接恢复 `git HEAD` 清空未提交成果**。

---

## 从设计到验收（精简 4 步流）

### 1. Codex 保护基线、定向锚定与薄任务契约
- 检查 `git status --short`：若有未提交改动，先保存恢复基线。
- 用 `rg` 定位入口、契约与受影响文件，整理**薄任务契约（Thin Spec）**，包含：
  1. **业务目标与必须保留的既有行为**（先与用户确认是否需要额外强协调语义，不自行扩张架构）；
  2. **目标文件绝对路径与真实方法签名锚点**；
  3. **实施边界**：要求用绝对路径调用 `read_file` 一次性读完 ≤800 行文件，缺失依赖签名时允许定向补读，对已有类用 `edit_file` 局部修改，严禁 `write_file(Overwrite=true)` 整体重写；
  4. **验收标准**。

### 2. 分级触发：单轮物理只读可行性评审（按需）
- **何时跳过**：需求边界清晰、单模块局部改造、明确删减冗余或常规修复，向用户确认方案后直奔第 3 步。
- **何时触发**：涉及跨服务契约、并发/锁/事务边界、状态机重构或存在技术路线分歧时，用旗舰模型 Medium 做**单轮（One-shot）只读评审**：
  ```bash
  agy --project '<项目ID>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands \
    --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)"],"deny":["write_file(*)","command(*)","mcp(*)","read_url(*)"]}}' \
    --output-format json \
    -p '只读可行性评审（禁止写文件或执行命令）。请用 read_file（传绝对路径，≤800行一次读完）读取以下锚点文件及必要关联接口，直接指出：1. 方案是否可行；2. 与现有签名/事务/协议的冲突或遗漏边界；3. 必须修正项。'
  ```
- **单轮收敛**：Codex 核实 AGY 的评审意见后，采纳有效修正并向用户汇报最终方案等待确认，不进行多轮形式化辩论。

### 3. 用户明确确认后：单层直派实施
收到用户明确确认后，放开工作区文件读写权限，启动单层实施（可复用评审会话 `conversation_id` 并更新 `--settings` 放开 `write_file`，或直派新会话）：
```bash
agy --project '<项目ID>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands \
  --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)","write_file(/绝对路径/工作区根目录)"],"deny":["command(*)","mcp(*)","read_url(*)"]}}' \
  --output-format json \
  -p '按以下已确认方案完成代码与测试修改。规则：1. 文件工具必须传绝对路径；2. 800行以内的待改文件一次 read_file 读完，未读到的本类尾部或关联 Mapper/DTO 签名必须先定向补读核实；3. 对已有复杂业务类必须使用 edit_file 局部修改，严禁在未核实原文时用 write_file 全文重写或臆造方法；4. 无需运行外部 Maven 命令，完成后返回改动摘要，由 Codex 宿主执行构建验证。'
```

### 4. Codex 宿主构建验证与集中修复
- AGY 返回后，Codex 在宿主环境审查 `git diff` 并运行真实构建测试（如 JDK8 Maven `clean test` / `clean package`）。
- 若有编译或测试问题，Codex 将**所有报错位置、真实接口签名与审查发现一次性汇总**，用 `--conversation '<实施会话 ID>'` 续接修复（保证要求读取的日志/基线路径在 `permissions.allow` 中已授权，或直接内嵌关键报错片段）。
- 若会话已出现 `CHECKPOINT` 自动压缩且丢失源码细节，或跨多轮改动导致历史状态与当前工作区文件不一致，则从当前已核实的 Git 状态开启新会话，仅传入待修文件的绝对路径与真实签名。

---

## 项目归属、模型与额度检查

1. **同名项目精确匹配**：
   - 在目标仓库根目录（`pwd -P` 解析后的绝对路径）启动 `agy`。
   - 首次委托时从 `~/.gemini/config/projects/*.json` 选择名称匹配且 `projectResources.resources[]` 仅绑定当前目标仓库的精确项目 `id`，后续复用 `--project '<项目 ID>'`。
2. **模型与额度检查**：
   - 仅在当前对话首次使用 AGY、或遇到配额/429 报错时执行一次 `agy models` 与 `agy -p '/usage'`。
   - 复杂评审用有额度的旗舰模型 Medium（如 `gemini-4-argon-medium`）；编码与修复用中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
