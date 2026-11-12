"""模型调用：
  anthropic   Claude API（API Key）
  openai      OpenAI 兼容接口（通义、Kimi、智谱、本地 vLLM / Ollama…）
  deepseek    DeepSeek API（OpenAI 兼容，预设好地址；不支持看图）
  claude_cli  本机 Claude Code 命令行（claude -p），用 Claude 会员（Pro / Max）的额度，不需要 API Key
  codex_cli   本机 Codex 命令行（codex exec），用 ChatGPT 会员的 Codex 额度，不需要 API Key
  mock        演示模式

统一成一个生成器 stream(settings, system, messages, workspace)，吐出事件：
  {"type": "text", "text": "…"}            模型输出的文字（增量）
  {"type": "tool", "name": "…", "input": {…}, "summary": "…"}   模型读了一次文件 / 看了一次图
  {"type": "error", "error": "…"}
messages 是统一格式：[{"role": "user"|"assistant", "content": "文字", "images": [(media_type, b64), …],
                      "image_paths": [绝对路径, …]}]
"""
import glob
import json
import os
import shutil
import subprocess
import time

from context import TOOLS

MAX_ROUNDS = 12
DEEPSEEK_URL = "https://api.deepseek.com"
ENV_KEYS = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "deepseek": "DEEPSEEK_API_KEY"}


def _key(settings, env):
    return settings.get("api_key") or os.environ.get(env, "")


def stream(settings, system, messages, workspace=None):
    provider = settings.get("provider", "mock")
    try:
        if provider == "anthropic":
            yield from _anthropic(settings, system, messages, workspace)
        elif provider == "openai":
            yield from _openai(settings, system, messages, workspace)
        elif provider == "deepseek":
            ds = dict(settings, base_url=settings.get("base_url") or DEEPSEEK_URL,
                      model=settings.get("model") or "deepseek-chat", vision=False)
            yield from _openai(ds, system, messages, workspace, env="DEEPSEEK_API_KEY")
        elif provider == "claude_cli":
            yield from _claude_cli(settings, system, messages, workspace)
        elif provider == "codex_cli":
            yield from _codex_cli(settings, system, messages, workspace)
        else:
            yield from _mock(settings, system, messages, workspace)
    except Exception as e:  # 网络、鉴权、模型名写错……都原样告诉用户
        yield {"type": "error", "error": f"{type(e).__name__}: {e}"}


def _summary(name, args):
    if name == "read_text":
        return f"读 {args.get('path')} {args.get('start') or 1}–{args.get('end') or ''}".rstrip("–")
    if name == "grep":
        return f"搜索 /{args.get('pattern')}/ 于 {args.get('path') or 'code'}"
    if name == "list_dir":
        return f"列目录 {args.get('path')}"
    if name == "view_image":
        return f"看图 {args.get('path')}"
    return name


# ---------------- Anthropic ----------------

def _anthropic(settings, system, messages, ws):
    import anthropic

    kw = {"api_key": _key(settings, "ANTHROPIC_API_KEY")}
    if settings.get("base_url"):
        kw["base_url"] = settings["base_url"]
    client = anthropic.Anthropic(**kw)
    vision = settings.get("vision", True)

    msgs = []
    for m in messages:
        if m["role"] == "user" and m.get("images") and vision:
            content = [{"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}} for mt, b64 in m["images"]]
            content.append({"type": "text", "text": m["content"] or "(见图)"})
        else:
            content = m["content"] or "…"
        msgs.append({"role": m["role"], "content": content})

    tools = [{"name": t["name"], "description": t["description"], "input_schema": t["schema"]} for t in TOOLS]
    if not vision:
        tools = [t for t in tools if t["name"] != "view_image"]
    use_tools = settings.get("use_tools", True) and ws is not None
    sys_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]

    for _ in range(MAX_ROUNDS):
        kwargs = dict(model=settings.get("model") or "claude-sonnet-4-5", max_tokens=int(settings.get("max_tokens") or 8000),
                      system=sys_blocks, messages=msgs)
        if use_tools:
            kwargs["tools"] = tools
        with client.messages.stream(**kwargs) as s:
            for ev in s:
                if ev.type == "content_block_delta" and getattr(ev.delta, "type", "") == "text_delta":
                    yield {"type": "text", "text": ev.delta.text}
            final = s.get_final_message()
        content, calls = [], []
        for b in final.content:
            if b.type == "text":
                content.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                content.append({"type": "tool_use", "id": b.id, "name": b.name, "input": b.input})
                calls.append(b)
        if final.stop_reason != "tool_use" or not calls:
            if final.stop_reason == "max_tokens":
                yield {"type": "text", "text": "\n\n（输出达到长度上限被截断，可以说「接着说」）"}
            return
        msgs.append({"role": "assistant", "content": content})
        results = []
        for b in calls:
            text, img = ws.run(b.name, b.input or {}, vision)
            yield {"type": "tool", "name": b.name, "input": b.input, "summary": _summary(b.name, b.input or {})}
            if img:
                rc = [{"type": "image", "source": {"type": "base64", "media_type": img[0], "data": img[1]}},
                      {"type": "text", "text": text}]
            else:
                rc = text
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": rc})
        msgs.append({"role": "user", "content": results})
        yield {"type": "text", "text": "\n\n"}
    yield {"type": "text", "text": "\n\n（工具调用轮数到上限了，先停在这里）"}


# ---------------- OpenAI 兼容 ----------------

def _openai(settings, system, messages, ws, env="OPENAI_API_KEY"):
    import openai

    kw = {"api_key": _key(settings, env) or "none"}
    if settings.get("base_url"):
        kw["base_url"] = settings["base_url"]
    client = openai.OpenAI(**kw)
    vision = settings.get("vision", True)

    def img_part(mt, b64):
        return {"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}}

    msgs = [{"role": "system", "content": system}]
    for m in messages:
        if m["role"] == "user" and m.get("images") and vision:
            msgs.append({"role": "user", "content": [img_part(*i) for i in m["images"]] + [{"type": "text", "text": m["content"] or "(见图)"}]})
        else:
            msgs.append({"role": m["role"], "content": m["content"] or "…"})

    tools = [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["schema"]}}
             for t in TOOLS if vision or t["name"] != "view_image"]
    use_tools = settings.get("use_tools", True) and ws is not None

    for _ in range(MAX_ROUNDS):
        kwargs = dict(model=settings.get("model") or "gpt-4o", messages=msgs, stream=True)
        if settings.get("max_tokens"):
            kwargs["max_tokens"] = int(settings["max_tokens"])
        if use_tools:
            kwargs["tools"] = tools
        text, calls, finish, reasoning = "", {}, None, ""
        try:
            resp = client.chat.completions.create(**kwargs)
        except openai.BadRequestError as e:
            # 有的模型（比如部分推理模型）不支持工具调用：去掉工具重试一次，改成只靠上下文里的材料讲
            if use_tools and any(w in str(e).lower() for w in ("tool", "function")):
                use_tools = False
                kwargs.pop("tools", None)
                yield {"type": "tool", "name": "notice", "input": {}, "summary": "这个模型不支持工具调用，改为只用上下文里的材料"}
                resp = client.chat.completions.create(**kwargs)
            else:
                raise
        for chunk in resp:
            if not chunk.choices:
                continue
            ch = chunk.choices[0]
            d = ch.delta
            rc = getattr(d, "reasoning_content", None)  # DeepSeek 思考模式的思考过程（不显示）
            if rc:
                reasoning += rc
            if getattr(d, "content", None):
                text += d.content
                yield {"type": "text", "text": d.content}
            for tc in getattr(d, "tool_calls", None) or []:
                c = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    c["id"] = tc.id
                if tc.function:
                    c["name"] += tc.function.name or ""
                    c["args"] += tc.function.arguments or ""
            finish = ch.finish_reason or finish
        if not calls:
            if finish == "length":
                yield {"type": "text", "text": "\n\n（输出达到长度上限被截断，可以说「接着说」）"}
            return
        ordered = [calls[i] for i in sorted(calls)]
        amsg = {"role": "assistant", "content": text or None, "tool_calls": [
            {"id": c["id"] or f"call_{i}", "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}}
            for i, c in enumerate(ordered)]}
        if reasoning:  # DeepSeek 思考模式：同一轮里调工具时要把思考过程原样带回去
            amsg["reasoning_content"] = reasoning
        msgs.append(amsg)
        pending = []
        for i, c in enumerate(ordered):
            try:
                args = json.loads(c["args"] or "{}")
            except ValueError:
                args = {}
            out, img = ws.run(c["name"], args, vision)
            yield {"type": "tool", "name": c["name"], "input": args, "summary": _summary(c["name"], args)}
            if img:
                pending.append(img)
                out += "（图片附在下一条消息里）"
            msgs.append({"role": "tool", "tool_call_id": c["id"] or f"call_{i}", "content": out})
        if pending:
            msgs.append({"role": "user", "content": [{"type": "text", "text": "view_image 返回的图片："}] + [img_part(*p) for p in pending]})
        yield {"type": "text", "text": "\n\n"}
    yield {"type": "text", "text": "\n\n（工具调用轮数到上限了，先停在这里）"}


# ---------------- 本机命令行（用会员额度，不需要 API Key） ----------------

def find_cli(name, settings=None):
    """找 claude / codex 可执行文件。设置里填了路径就用它；否则 PATH → 常见安装位置。"""
    custom = (settings or {}).get("cli_path")
    if custom and os.path.isfile(os.path.expanduser(custom)):
        return os.path.expanduser(custom)
    p = shutil.which(name)
    if p:
        return p
    home = os.path.expanduser("~")
    appdata = os.environ.get("APPDATA", os.path.join(home, "AppData", "Roaming"))
    cands = [
        os.path.join(home, ".local", "bin", name + (".exe" if os.name == "nt" else "")),  # 官方原生安装
        os.path.join(appdata, "npm", name + ".cmd"),                                          # npm i -g
        os.path.join(home, ".npm-global", "bin", name),
        "/opt/homebrew/bin/" + name, "/usr/local/bin/" + name,
    ]
    if name == "codex":  # VS Code / Cursor 里的 Codex 扩展自带一份 codex
        for ext in (".vscode", ".cursor", ".windsurf"):
            pat = os.path.join(home, ext, "extensions", "openai.chatgpt-*", "bin", "*", "codex" + (".exe" if os.name == "nt" else ""))
            cands += sorted(glob.glob(pat), reverse=True)
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def _transcript(system, messages, tail):
    """命令行一次只接一个 prompt：把上下文 + 对话记录拼成一段，通过 stdin 发过去。"""
    parts = [system, "\n\n---\n\n# 到目前为止的对话\n"]
    for m in messages[:-1]:
        who = "用户" if m["role"] == "user" else "你（助手）"
        parts.append(f"\n## {who}\n\n{m['content']}\n")
    last = messages[-1]["content"] if messages else ""
    parts.append(f"\n---\n\n# 现在要回复的用户消息\n\n{last}\n\n---\n{tail}")
    return "".join(parts)


def _clean_env(drop):
    env = dict(os.environ, PYTHONUTF8="1")
    for k in drop:  # 环境里有 API Key 的话命令行会改用 API 计费，这里去掉，确保走会员额度
        env.pop(k, None)
    return env


def _popen(cmd, cwd, env):
    kw = dict(cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.name == "nt":
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.Popen(cmd, **kw)


def _feed(proc, text):
    try:
        proc.stdin.write(text.encode("utf-8"))
        proc.stdin.close()
    except OSError:
        pass


def _drain_stderr(proc, sink):
    def run():
        for raw in proc.stderr:
            sink.append(raw.decode("utf-8", errors="replace").rstrip())
    import threading
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _claude_cli(settings, system, messages, ws, partial=True):
    exe = find_cli("claude", settings)
    if not exe:
        raise RuntimeError("没找到 Claude Code（claude 命令）。安装：PowerShell 里运行 irm https://claude.ai/install.ps1 | iex，"
                           "然后在终端运行一次 claude，用 Claude 会员账号登录。装在别处的话在设置里填路径。")
    cwd = str(ws.paper) if ws else os.getcwd()
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose",
           "--allowedTools", "Read,Grep,Glob",
           "--disallowedTools", "Bash,Edit,Write,MultiEdit,NotebookEdit,WebFetch,WebSearch,Task"]
    if partial:
        cmd.append("--include-partial-messages")
    if ws and ws.code and ws.paper not in ws.code.parents and ws.code != ws.paper:
        cmd += ["--add-dir", str(ws.code)]
    if settings.get("model"):
        cmd += ["--model", settings["model"]]
    tail = ("直接输出给用户看的回复（Markdown），不要复述上面的说明。需要原文、代码或图时用 Read / Grep / Glob 读"
            "（当前目录就是资料目录，代码在 code/ 或 --add-dir 加进来的目录），不要修改或创建任何文件。")
    paths = [p for m in messages[-1:] for p in m.get("image_paths", [])]
    if paths:
        tail += "\n用户这条消息附了图，先用 Read 看：" + "、".join(paths)
    prompt = _transcript(system, messages, tail)

    proc = _popen(cmd, cwd, _clean_env(["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]))
    err = []
    _drain_stderr(proc, err)
    _feed(proc, prompt)
    got_delta, got_any, result_err = False, False, None
    try:
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get("type")
            if t == "stream_event":
                e = ev.get("event") or {}
                d = e.get("delta") or {}
                if d.get("type") == "text_delta" and not ev.get("parent_tool_use_id"):
                    got_delta = got_any = True
                    yield {"type": "text", "text": d.get("text", "")}
                elif e.get("type") == "message_start" and got_any:
                    yield {"type": "text", "text": "\n\n"}
            elif t == "assistant" and not ev.get("parent_tool_use_id"):
                for b in (ev.get("message") or {}).get("content", []):
                    if b.get("type") == "tool_use":
                        inp = b.get("input") or {}
                        target = inp.get("file_path") or inp.get("path") or inp.get("pattern") or ""
                        yield {"type": "tool", "name": b.get("name"), "input": inp,
                               "summary": f"{b.get('name')} {os.path.relpath(target, cwd) if os.path.isabs(str(target)) else target}".strip()}
                    elif b.get("type") == "text" and not got_delta and b.get("text"):
                        got_any = True
                        yield {"type": "text", "text": b["text"] + "\n\n"}
            elif t == "result":
                if ev.get("is_error") or (ev.get("subtype") not in (None, "success")):
                    result_err = ev.get("result") or ev.get("subtype") or "未知错误"
                elif not got_any and ev.get("result"):
                    got_any = True
                    yield {"type": "text", "text": ev["result"]}
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    msg = "\n".join(err[-15:])
    if not got_any and partial and "include-partial-messages" in msg:  # 老版本没有这个参数：不要逐字流式，重来一次
        yield from _claude_cli(settings, system, messages, ws, partial=False)
        return
    if result_err:
        raise RuntimeError(f"Claude Code 报错：{result_err}")
    if proc.returncode not in (0, None) and not got_any:
        hint = "（没登录的话先在终端运行 claude 并用会员账号登录）" if any(w in msg.lower() for w in ("login", "auth", "credential", "/login")) else ""
        raise RuntimeError(f"Claude Code 退出码 {proc.returncode}：{msg or '无输出'}{hint}")


def _codex_cli(settings, system, messages, ws):
    exe = find_cli("codex", settings)
    if not exe:
        raise RuntimeError("没找到 Codex（codex 命令）。安装：npm i -g @openai/codex（需要 Node.js），"
                           "然后在终端运行 codex login 用 ChatGPT 账号登录。装在别处的话在设置里填路径。")
    cwd = str(ws.paper) if ws else os.getcwd()
    cmd = [exe, "exec", "--json", "--skip-git-repo-check", "--sandbox", "read-only", "-C", cwd, "--color", "never"]
    if ws and ws.code and ws.paper not in ws.code.parents and ws.code != ws.paper:
        cmd += ["--add-dir", str(ws.code)]
    if settings.get("model"):
        cmd += ["-m", settings["model"]]
    for p in [p for m in messages[-1:] for p in m.get("image_paths", [])][:4]:
        cmd += ["-i", p]
    cmd.append("-")  # prompt 从 stdin 读
    tail = ("直接输出给用户看的回复（Markdown），不要复述上面的说明。需要原文或代码时用只读命令（rg、sed -n、cat）在当前目录（资料目录）里查，"
            "不要修改或创建任何文件。")
    prompt = _transcript(system, messages, tail)

    proc = _popen(cmd, cwd, _clean_env(["OPENAI_API_KEY", "CODEX_API_KEY"]))
    err = []
    _drain_stderr(proc, err)
    _feed(proc, prompt)
    got_any, failed = False, None
    try:
        for raw in proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("{"):
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            t = ev.get("type")
            item = ev.get("item") or {}
            itype = item.get("type") or item.get("item_type")
            if t == "item.started" and itype == "command_execution":
                yield {"type": "tool", "name": "shell", "input": {"command": item.get("command")},
                       "summary": f"运行 {str(item.get('command', ''))[:120]}"}
            elif t == "item.completed" and itype in ("agent_message", "assistant_message"):
                txt = item.get("text") or ""
                if txt:
                    yield {"type": "text", "text": ("\n\n" if got_any else "") + txt}
                    got_any = True
            elif t == "turn.failed":
                failed = (ev.get("error") or {}).get("message") or json.dumps(ev, ensure_ascii=False)
            elif t == "error":
                failed = ev.get("message") or json.dumps(ev, ensure_ascii=False)
            elif "msg" in ev:  # 老版本（0.44 之前）的事件格式
                m = ev["msg"] or {}
                if m.get("type") == "agent_message" and m.get("message"):
                    yield {"type": "text", "text": ("\n\n" if got_any else "") + m["message"]}
                    got_any = True
                elif m.get("type") == "exec_command_begin":
                    yield {"type": "tool", "name": "shell", "input": {}, "summary": f"运行 {' '.join(m.get('command') or [])[:120]}"}
                elif m.get("type") == "error":
                    failed = m.get("message")
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()
    msg = "\n".join(err[-15:])
    if failed and not got_any:
        raise RuntimeError(f"Codex 报错：{failed}")
    if proc.returncode not in (0, None) and not got_any:
        hint = "（没登录的话先在终端运行 codex login）" if any(w in msg.lower() for w in ("login", "auth", "401", "unauthorized")) else ""
        raise RuntimeError(f"Codex 退出码 {proc.returncode}：{msg or '无输出'}{hint}")


# ---------------- 演示模式（没配模型时也能把界面走一遍） ----------------

def _mock_repo(ws, last):
    """代码仓库的演示回复：用真实的入口候选演示可点击的代码位置。"""
    try:
        meta = json.loads((ws.paper / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    pre = "code/" + (meta["subdir"] + "/" if meta.get("subdir") else "")
    ent = (meta.get("entry_points") or [{}])[0]
    mods = meta.get("top_modules") or []
    yield {"type": "tool", "name": "list_dir", "input": {"path": "code"}, "summary": "列目录 code"}
    langs = " / ".join(f"{l['name']} {l['pct']}%" for l in (meta.get("languages") or [])[:3]) or "未识别"
    reply = (
        "**演示模式**：还没有配置模型，这是一段占位回复，用来演示代码分析器的界面。到右上角「设置」里选好模型就能真正开讲。\n\n"
        f"你刚才说的是：\n\n> {last[:200]}\n\n"
        f"- 仓库：**{meta.get('title', '')}** · {meta.get('n_files', 0)} 个文件 · 代码 {meta.get('n_code_lines', 0):,} 行 · {langs}\n"
        + (f"- 入口候选：`{pre}{ent['path']}:{ent['line']}`（{ent.get('reason', '')}）——点一下就会在左边打开并高亮这一行\n" if ent.get("path") else "")
        + (f"- 被引用最多：`{pre}{mods[0]['path']}`（被 {mods[0]['imported_by']} 个文件引用）\n" if mods else "")
        + "\n结构图会画成文字：\n\n```\n入口 main ──解析参数──▶ Config\n   │\n   └─▶ Core.run() ──逐条处理──▶ 输出\n```\n\n"
        "一句话回顾：这是演示回复。\n下一站：① 定位。继续吗？"
    )
    for i in range(0, len(reply), 12):
        yield {"type": "text", "text": reply[i:i + 12]}
        time.sleep(0.01)


def _mock(settings, system, messages, ws):
    last = messages[-1]["content"] if messages else ""
    if ws and (ws.paper / "symbols.json").exists():
        yield from _mock_repo(ws, last)
        return
    fig = None
    if ws:
        for name in ("figures", "figures-auto"):
            d = ws.paper / name
            if d.is_dir():
                pngs = sorted(p for p in d.glob("fig-*.png"))
                if pngs:
                    fig = f"{name}/{pngs[0].name}"
                    break
    if fig:
        text, _ = ws.run("list_dir", {"path": fig.split("/")[0]})
        yield {"type": "tool", "name": "list_dir", "input": {"path": fig.split("/")[0]}, "summary": f"列目录 {fig.split('/')[0]}"}
    reply = (
        "**演示模式**：还没有配置模型，这是一段占位回复，用来演示界面。到右上角「设置」里填上 API Key 和模型名就能真正开讲。\n\n"
        f"你刚才说的是：\n\n> {last[:200]}\n\n"
        + (f"讲到图时会像这样直接显示：\n\n![图 1 · 演示]({fig})\n\n" if fig else "")
        + "公式按 SKILL.md 的写法放进代码块：\n\n```\nL(θ) = E ‖ v_θ(A^τ, o) − (ε − A) ‖²\n```\n\n"
        "| 符号 | 是什么 | 形状 |\n|---|---|---|\n| A | 动作块 | 50×14 |\n| ε | 噪声 | 50×14 |\n\n"
        "一句话回顾：这是演示回复。\n下一站：② 架构。继续吗？"
    )
    for i in range(0, len(reply), 12):
        yield {"type": "text", "text": reply[i:i + 12]}
        time.sleep(0.01)
