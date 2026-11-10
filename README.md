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

---

## 实时查看 AGY 执行状态（可选彩色大盘）

若想在另一个终端窗口实时观察 AGY 当前正在调用的工具、修改的文件与思考过程（100% 只读旁路，零侵入，不干扰 Codex 与 AGY 自动化流程）：

### 方式 1：执行仓库内置脚本（推荐，支持跨会话自动切换）
`bin/agy-watch` 使用 Python 标准库实现，无需安装 `jq`，且**支持跨会话自动切换**（当一次会话结束、新一轮会话启动时，会自动检测并切换监听最新会话，无需每次手动 Ctrl+C 重启）：
```bash
./bin/agy-watch
```
*(也可将脚本软链或拷贝至 PATH：`cp bin/agy-watch ~/.local/bin/`，之后在任何目录直接敲 `agy-watch` 即可)*

### 方式 2：终端原始单行命令（单会话静态跟踪，免安装）
*(注：原始单行命令绑定于启动瞬间抓到的特定日志文件，会话结束后需重新执行以跟踪下一会话)*
```bash
tail -n 30 -f "$(ls -t ~/.gemini/antigravity-cli/brain/*/.system_generated/logs/transcript.jsonl | head -n 1)" | jq --unbuffered -r '
  def c_dim(s): "\u001b[90m" + s + "\u001b[0m";
  def c_step(s): "\u001b[1;33m" + s + "\u001b[0m";
  def c_cmd(s): "\u001b[1;32m" + s + "\u001b[0m";
  def c_edit(s): "\u001b[1;35m" + s + "\u001b[0m";
  def c_read(s): "\u001b[1;36m" + s + "\u001b[0m";
  def c_tool(s): "\u001b[1;34m" + s + "\u001b[0m";
  def c_arg(s): "\u001b[37m" + s + "\u001b[0m";
  def c_msg(s): "\u001b[96m" + s + "\u001b[0m";
  def c_user(s): "\u001b[1;45;97m" + s + "\u001b[0m";

  if .type == "USER_INPUT" then
    c_dim("[\(.created_at[11:19])]") + " " + c_user(" 🚀 USER ") + " " + c_msg((.content // "") | gsub("\n"; " ") | .[0:80])
  elif .type == "PLANNER_RESPONSE" then
    c_dim("[\(.created_at[11:19])]") + " " + c_step("#\(.step_index)") + " " +
    (if (.tool_calls | length) > 0 then
      ([.tool_calls[] |
        (if .name == "run_command" then c_cmd(.name)
         elif (.name == "edit_file" or .name == "write_file") then c_edit(.name)
         elif .name == "read_file" then c_read(.name)
         else c_tool(.name) end) +
        "(" + c_arg(
          if .args.Path then (.args.Path | gsub("^\"|\"$"; "") | split("/") | last)
          elif .args.CommandLine then (.args.CommandLine | gsub("^\"|\"$"; "") | .[0:60])
          else (.args.Query // .args.SearchPath // "" | gsub("^\"|\"$"; ""))
          end
        ) + ")"
      ] | join(", "))
    else
      "\u001b[35m💬\u001b[0m " + c_msg((.content // "") | gsub("\n"; " ") | .[0:80])
    end)
  else empty end
'
```
