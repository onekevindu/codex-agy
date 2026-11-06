#!/usr/bin/env python3
"""Invoke AGY once and retain inputs, raw output and transport status."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
from datetime import datetime, timezone


ROLE = """
你是 Codex 委托的执行子 Agent。Codex 拥有需求解释、方案与方向决策权。
在批准方案内自主组织实施步骤、编码、测试和局部修复。
需要改变方案、需求范围、接口契约或技术路线时，提供事实和建议交回 Codex。
不清楚方案时提出具体疑问。暂停依赖该决定的部分。
严格遵守任务授权范围和适用项目规则。仅报告实际观察到的修改和验证结果。
按给定 JSON schema 返回。COMPLETED 仅表示此次委托完成，最终验收由 Codex 负责。
checks 中列明命令、运行目录、结果、可用日志路径，明确未执行的检查。
issues 列明未解决问题及权限拒绝。questions 列明需要 Codex 决定的问题。
"""


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def save_metadata(output, metadata):
    temporary = output / "run.json.tmp"
    temporary.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output / "run.json")


def stop_process(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def interrupted(signum, frame):
    raise KeyboardInterrupt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, required=True)
    parser.add_argument("--task-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=["plan", "accept-edits", "auto"], required=True)
    parser.add_argument("--project")
    parser.add_argument("--model")
    parser.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--settings-file", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=0)
    args = parser.parse_args()
    cwd = args.cwd.resolve(strict=True)
    if not cwd.is_dir() or args.timeout_seconds < 0:
        parser.error("cwd must be a directory and timeout must be nonnegative")
    executable = shutil.which("agy")
    if not executable:
        parser.error("agy is not installed or not on PATH")
    task = args.task_file.read_text(encoding="utf-8").strip()
    if not task:
        parser.error("task file is empty")
    prompt = task + "\n\n" + ROLE
    schema = Path(__file__).resolve().parents[1] / "references/result.schema.json"
    command = [executable, "--print", prompt, "--output-format", "json",
               "--json-schema", str(schema), "--mode", args.mode]
    for flag in ("project", "model", "effort"):
        value = getattr(args, flag)
        if value:
            command.extend(["--" + flag, value])
    if args.settings_file:
        settings_path = args.settings_file.resolve(strict=True)
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        if not isinstance(settings, dict):
            parser.error("settings file must contain a JSON object")
        command.extend(["--settings", str(settings_path)])

    digest = hashlib.sha256(os.fsencode(cwd)).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"codex-agy-{os.getuid()}-{digest}.lock"
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another run_agy invocation owns this workspace")
        output = args.output_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
        (output / "request.md").write_text(prompt, encoding="utf-8")
        metadata = {"state": "RUNNING", "cwd": str(cwd), "requested_mode": args.mode,
                    "started_at": timestamp(), "runner_pid": os.getpid(),
                    "exit_code": None, "error": None}
        save_metadata(output, metadata)
        print(json.dumps({"output_dir": str(output), "state": "RUNNING"}), flush=True)
        process = None
        return_code = 1
        signal.signal(signal.SIGTERM, interrupted)
        try:
            with (output / "stdout.json").open("wb") as stdout, \
                    (output / "stderr.log").open("wb") as stderr:
                process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                metadata["child_pid"] = process.pid
                save_metadata(output, metadata)
                return_code = process.wait(timeout=args.timeout_seconds or None)
                metadata["state"] = "EXITED"
        except subprocess.TimeoutExpired:
            metadata["state"] = "TIMED_OUT"
            stop_process(process)
            return_code = 124
        except KeyboardInterrupt:
            metadata["state"] = "INTERRUPTED"
            if process is not None:
                stop_process(process)
            return_code = 130
        except OSError as error:
            metadata["state"] = "LAUNCH_ERROR"
            metadata["error"] = str(error)
            if process is not None:
                stop_process(process)
        finally:
            metadata["finished_at"] = timestamp()
            metadata["exit_code"] = process.returncode if process is not None else None
            save_metadata(output, metadata)
        print(json.dumps(metadata, ensure_ascii=False), flush=True)
        return return_code if return_code >= 0 else 128 - return_code


if __name__ == "__main__":
    raise SystemExit(main())
