---
name: codex-agy
description: 通过 Antigravity CLI（agy）使用 AGY 作为 Codex 的实现 Subagent。以“节省 Codex 额度、下放执行自治权”为核心：委托前 Codex 定边界，执行中 AGY 自主完成阅读、局部编码与沙箱内构建自修复闭环，交付后 Codex 集中终验。
---

# 高效调用 AGY（额度重平衡与执行自治架构）

## 核心目标：把重度消耗转给 AGY，把 Codex 调用压到最低

协作的衡量标准是：**完成同等任务时，Codex 的总模型调用次数与 Token 消耗大幅下降，返工轮次最小化**。为此必须把“编码”和“执行过程的自主权（详查代码、编译自检、局部纠错）”一并交给额度充裕的 AGY，禁止 Codex 充当高频监工或人肉编译器。

---

## 四个阶段的职责边界

### 1. 委托前：Codex 极简立项（不替 AGY 做全量代码阅读）
- **控制 Codex 上下文体积**：Codex 仅用 1–3 次 `rg` 确认核心入口目录与关键契约文件，**禁止 Codex 自行读取几十个源码文件或跨多个仓库做地毯式调研**（每次把几万行代码塞进 Codex 上下文，后续每一轮调度都会成倍烧掉 Codex 额度）。
- **脏工作区基线保护**：若 `git status --short` 显示工作区已有未提交的前序实现，先用 `git stash create` 或打包备份记录恢复基线，**严禁在回滚单轮改动时直接对脏工作区执行 `git checkout HEAD` / `git reset --hard`**。
- **明确四要素即可派发**：
  1. **业务目标与关键技术决策**（先向用户确认是否需要强协调语义，不自行过度设计）；
  2. **不可变边界**（必须保留的表、接口、协议、事务/ACK 顺序）；
  3. **代码锚点与局部修改要求**；
  4. **验收命令与通过标准**（如本机 JDK8 离线 Maven 测试命令）。

### 2. 按需可行性评审：让 AGY 做重度只读调研（单轮收敛）
- **常规/边界清晰任务**：直接跳过评审，向用户确认方案后进入第 3 步实施。
- **复杂架构/事务重构任务**：把跨文件调用链核对与可行性评估交给旗舰模型 Medium 的 AGY 单轮完成。
- **禁用 `--mode plan`（防 1,500 字 `<PLAN>` 宏污染）**：`agy` 二进制底层会将 `--mode plan` 自动展开为 `/plan` 宏（要求全库扫描并写 Artifact 文件）。只读评审一律使用 `--mode accept-edits --disable-slash-commands` 搭配 `--settings` 物理禁写：
  ```bash
  agy --project '<项目ID>' --model '<旗舰 Medium 模型 ID>' --mode accept-edits --disable-slash-commands \
    --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"request-review","permissions":{"allow":["read_file(/绝对路径/工作区根目录)"],"deny":["write_file(*)","command(*)","mcp(*)","read_url(*)"]}}' \
    --output-format json \
    -p '只读可行性评审（禁止写文件或执行命令）。请用 read_file（传绝对路径，≤800行一次读完）核对以下锚点文件及关联调用链，指出：1. 方案是否可行；2. 与现有接口签名/事务/协议的冲突或遗漏边界；3. 必须修正项。'
  ```
- Codex 吸收有效意见后直接向用户汇报定稿，**不与 AGY 进行多轮文字辩论**。

### 3. 执行中：AGY 端到端自治闭环，Codex 静默等待
收到用户明确确认后，**由 Codex 直接派发单个 AGY 执行会话**（严禁在外部同时起“AGY 负责人 + AGY 执行者”两个 CLI 进程传话）。

#### （1）赋予 AGY 沙箱内“编码 + 本地构建自修复”完整自治权
- 不要让 AGY 写完代码盲交回来等 Codex 编译报错。使用 `--sandbox` 搭配会话设置 `"enableTerminalSandbox": true, "toolPermission": "proceed-in-sandbox"`，允许 AGY 在沙箱内自主运行本地构建与单测，**自己看报错、自己修到编译与单测全绿后再退出返回**。
- **不要规定构建日志落盘路径**：Codex 不要要求 AGY 把构建日志重定向到 `/private/tmp` 等指定文件，交给 AGY 原生 `run_command` 自行处理即可。

```bash
agy --project '<项目ID>' --model '<中档 High 模型 ID>' --mode accept-edits --disable-slash-commands --sandbox \
  --settings '{"allowNonWorkspaceAccess":false,"enableTerminalSandbox":true,"toolPermission":"proceed-in-sandbox","permissions":{"allow":["read_file(/绝对路径/工作区根目录)","write_file(/绝对路径/工作区根目录)","command(env)","command(mvn)","command(git status)","command(git diff)"],"deny":["unsandboxed(*)","command(git checkout)","command(git reset)","command(git clean)","command(git commit)","command(git push)","mcp(*)","read_url(*)"]}}' \
  --output-format json \
  -p '按以下已确认边界完成编码、单测与本地构建自检闭环：
1. 完整读取：调用文件工具必须传绝对路径；800行以内的文件一次 read_file 读完；未读到的本类尾部私有方法或关联 Mapper/DTO 签名必须先定向补读核实。
2. 局部修改：对已有复杂业务类必须使用 edit_file 局部修改，严禁在缺失原文时调用 write_file(Overwrite=true) 全文重新生成或臆造不存在的方法。
3. 自主构建修复：修改后在沙箱内自主运行构建与测试，若有编译或测试错误请自行定位修复，直到测试通过后再集中返回改动摘要与测试结果。'
```

#### （2）Codex 执行中“三不准”与长等待纪律
- **工具侧持续等待，减少无信息唤醒**：Codex 调用 `exec_command` / `write_stdin` 等待 `agy -p` 时，必须将 `yield_time_ms` 设为工具支持的最大上限；`agy` 侧不设短 `--print-timeout` 截断任务。
- **等待期间零折腾**：若单次等待到期进程仍在运行，仅继续純等待；**严禁每隔 1–30 秒唤醒模型轮询，严禁在等待期间夹带 `git diff`、`stat` 或编写脚本解析 `~/.gemini/antigravity-cli/` 内部 `.pb` / `transcript.jsonl` 记录**。
- **不准凭读取次数或耗时催写**：严禁主观宣布“你已读取 N 次源码、上下文已具备，禁止继续读取、立即写入”，不得把 AGY 对缺失原文或关联签名的必要补读当成无效工作。

### 4. 交付后与阻塞处理：Codex 集中终验、定向排障
- **交付后一次性终验**：AGY 完成自检返回后，Codex 审查 `git diff` 并独立运行一次宿主构建测试确认结果。若有遗漏问题，**一次性集中列出所有问题、文件行号与真实签名**，用 `--conversation '<会话 ID>'` 交回修复。
- **出现阻塞时定向处理**：
  - 若因权限拒绝（`denied_actions`）中断，只针对被拒的具体路径/命令修正 `--settings`（例如确实需要读 `/private/tmp` 下某文件时，必须同步开启 `"allowNonWorkspaceAccess": true` 并授权该路径），然后续接原会话，**严禁推翻重查整个任务**。
  - 若会话已发生 `CHECKPOINT` 自动压缩（~256K tokens）且出现接口遗忘，则从当前已核实的 Git 状态开启新会话，仅传入剩余待修文件与具体问题。

---

## 项目归属与模型额度（仅首次核对）

1. **同名项目精确匹配**：首次委托时从 `~/.gemini/config/projects/*.json` 选出名称匹配且 `projectResources.resources[]` 仅绑定当前目标仓库的精确 `id`，后续复用 `--project '<项目 ID>'`。
2. **额度与模型**：仅在对话首次使用 AGY 或遇 429 报错时查一次 `agy models` 与 `agy -p '/usage'`。只读评审用旗舰模型 Medium（如 `gemini-4-argon-medium`），实施与自测用中档模型 High（如 `gemini-3.8-flash-high`）或旗舰 Medium。
