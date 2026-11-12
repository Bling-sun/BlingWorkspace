"""Bling-Workspace：论文精读 + 代码分析的本地网页端。

    python web/server.py            # 默认 http://127.0.0.1:8765

论文 / 网站：导入（scripts/fetch_paper.py）→ 阅读（PDF / 图表 / 大纲 / 代码）→ 按 SKILL.md 六站带读 → 精读笔记 → 导出 HTML。
代码仓库：导入 GitHub / Git 链接或本机文件夹（scripts/fetch_repo.py）→ 概览 / 代码 / 符号 / 仓库地图
          → 按 references/code-reading.md 七站带读 → 代码分析笔记 → 导出 HTML。
"""
import datetime
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import mimetypes

try:
    from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory
    import markdown  # noqa: F401  notes.py 要用
except ImportError as e:
    sys.exit(f"缺少依赖：{e.name}。在项目根目录运行 start.bat（Windows）/ start.sh，或者 pip install -r web/requirements.txt")

# Windows 注册表里 .js / .css 的 MIME 类型有时被别的软件改成 text/plain，浏览器就不执行脚本、不加载样式 → 页面空白
import warnings  # noqa: E402
warnings.filterwarnings("ignore", category=FutureWarning)  # PyMuPDF 的 fitz 改名提示
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
mimetypes.add_type("application/pdf", ".pdf")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import context  # noqa: E402
import llm  # noqa: E402
import notes as notes_mod  # noqa: E402
import history as history_mod  # noqa: E402

WEB = Path(__file__).resolve().parent
REPO = WEB.parent
SCRIPTS = REPO / "scripts"
CONFIG = WEB / "config.json"
UPLOADS = WEB / "_uploads"

DEFAULTS = {
    "provider": "mock",          # anthropic / openai / deepseek / claude_cli / codex_cli / mock
    "max_tokens": 8000,
    "use_tools": True,           # 让模型自己读代码 / 原文 / 看图
    "max_paper_chars": 160000,   # 放进上下文的正文最多多少字
    "papers_root": str(REPO / "papers"),
    "repos_root": str(REPO / "repos"),   # 代码仓库的分析目录放这里
    "extra_papers": [],          # 在 papers_root / repos_root 之外导入过的资料目录
    "host": "127.0.0.1",
    "port": 8765,
}
PROVIDERS = ("anthropic", "openai", "deepseek", "claude_cli", "codex_cli", "mock")
# 每个接口各存一份 Key / 地址 / 模型，切换接口不会把别的接口的 Key 弄丢
PROFILE_FIELDS = ("api_key", "base_url", "model", "vision", "cli_path")
PROFILE_DEFAULTS = {
    "anthropic": {"vision": True},
    "openai": {"vision": True},
    "deepseek": {"base_url": llm.DEEPSEEK_URL, "model": "deepseek-chat", "vision": False},
    "claude_cli": {"vision": True},
    "codex_cli": {"vision": False},
    "mock": {"vision": True},
}

app = Flask(__name__, static_folder=str(WEB / "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
_locks = {}
_jobs = {}


# ---------------- 设置 ----------------

def _raw():
    raw = {}
    if CONFIG.exists():
        try:
            raw = json.loads(CONFIG.read_text(encoding="utf-8"))
        except ValueError:
            raw = {}
    if "profiles" not in raw:  # 旧版配置：Key / 地址 / 模型在顶层 → 挪进当前接口的 profile
        prov = raw.get("provider", "mock")
        raw["profiles"] = {prov: {k: raw[k] for k in PROFILE_FIELDS if k in raw}} if prov in PROVIDERS else {}
    for k in PROFILE_FIELDS:
        raw.pop(k, None)
    return raw


def profile_of(raw, prov):
    p = {"api_key": "", "base_url": "", "model": "", "vision": True, "cli_path": ""}
    p.update(PROFILE_DEFAULTS.get(prov, {}))
    p.update({k: v for k, v in (raw.get("profiles", {}).get(prov) or {}).items() if k in PROFILE_FIELDS and v not in (None, "")})
    return p


def settings():
    """当前生效的设置：全局项 + 当前接口的 Key / 地址 / 模型（平铺在顶层，llm.py / context.py 直接用）。"""
    raw = _raw()
    s = dict(DEFAULTS)
    s.update({k: v for k, v in raw.items() if k != "profiles"})
    if s["provider"] not in PROVIDERS:
        s["provider"] = "mock"
    s.update(profile_of(raw, s["provider"]))
    s["profiles"] = raw.get("profiles", {})
    return s


def save_settings(s):
    raw = _raw()
    out = {k: s.get(k, raw.get(k, DEFAULTS[k])) for k in DEFAULTS}
    out["profiles"] = s.get("profiles", raw.get("profiles", {}))
    CONFIG.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def mask(k):
    return (k[:6] + "…" + k[-4:]) if k and len(k) > 12 else ("已填写" if k else "")


@app.get("/api/settings")
def get_settings():
    s = settings()
    raw = _raw()
    profiles = {}
    for prov in PROVIDERS:
        p = profile_of(raw, prov)
        env = llm.ENV_KEYS.get(prov)
        p["api_key_masked"] = mask(p.pop("api_key")) or (f"（用环境变量 {env}）" if env and os.environ.get(env) else "")
        profiles[prov] = p
    detected = {"claude_cli": llm.find_cli("claude", profile_of(raw, "claude_cli")),
                "codex_cli": llm.find_cli("codex", profile_of(raw, "codex_cli"))}
    out = {k: s[k] for k in DEFAULTS}
    out.update(provider=s["provider"], model=s["model"], profiles=profiles, detected=detected)
    return jsonify(out)


@app.post("/api/settings")
def post_settings():
    s = settings()
    body = request.get_json(force=True)
    for k in DEFAULTS:
        if k in body and k not in ("extra_papers", "host", "port"):
            s[k] = body[k]
    if s["provider"] not in PROVIDERS:
        s["provider"] = "mock"
    for k in ("max_tokens", "max_paper_chars"):
        try:
            s[k] = int(s[k])
        except (TypeError, ValueError):
            s[k] = DEFAULTS[k]
    prof = dict(s["profiles"].get(s["provider"]) or {})
    for k, v in (body.get("profile") or {}).items():
        if k == "api_key":
            if v and v.strip():
                prof["api_key"] = v.strip()
        elif k in PROFILE_FIELDS:
            prof[k] = v.strip() if isinstance(v, str) else v
    if body.get("clear_key"):
        prof["api_key"] = ""
    s["profiles"][s["provider"]] = prof
    save_settings(s)
    return get_settings()


@app.post("/api/settings/test")
def test_settings():
    """发一句最短的话试试当前接口：Key 对不对、模型名对不对、命令行登录了没有。"""
    s = settings()
    box = {"text": "", "error": None, "tools": 0}

    def work():
        sys_prompt = "你是连通性测试。只回复「连接成功」四个字，不要读任何文件。"
        for ev in llm.stream(dict(s, use_tools=False), sys_prompt, [{"role": "user", "content": "测试", "images": []}], None):
            if ev["type"] == "text":
                box["text"] += ev["text"]
            elif ev["type"] == "error":
                box["error"] = ev["error"]

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout=120)
    if t.is_alive():
        return jsonify({"ok": False, "error": "120 秒没有回应（网络不通，或者命令行在等登录）"})
    ok = bool(box["text"].strip()) and not box["error"]
    return jsonify({"ok": ok, "text": box["text"].strip()[:300], "error": box["error"], "provider": s["provider"], "model": s["model"]})


@app.get("/api/profile")
def get_profile():
    p = REPO / "profile.md"
    ex = REPO / "profile.example.md"
    return jsonify({"text": p.read_text(encoding="utf-8") if p.exists() else "",
                    "example": ex.read_text(encoding="utf-8") if ex.exists() else "", "exists": p.exists()})


@app.post("/api/profile")
def post_profile():
    (REPO / "profile.md").write_text(request.get_json(force=True).get("text", ""), encoding="utf-8")
    return jsonify({"ok": True})


# ---------------- 资料库（论文 / 网站 / 代码仓库） ----------------

def _dir_setting(value, default_name):
    """相对路径按项目根目录算；项目文件夹改过名（如 bling-paper-reading → Bling-Workspace）、
    配置里的旧绝对路径已经不存在时，自动退回项目里的同名目录。"""
    p = Path(os.path.expanduser(str(value or default_name)))
    if not p.is_absolute():
        p = REPO / p
    if not p.exists() and p.name == default_name and (REPO / default_name).exists():
        p = REPO / default_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def roots():
    s = settings()
    return _dir_setting(s["papers_root"], "papers"), [Path(p) for p in s.get("extra_papers", [])]


def repos_root():
    return _dir_setting(settings().get("repos_root"), "repos")


def paper_dirs():
    root, extra = roots()
    found = {}
    rr = repos_root()
    cands = [d for d in sorted(root.iterdir()) if d.is_dir()] + \
            ([d for d in sorted(rr.iterdir()) if d.is_dir()] if rr.resolve() != root.resolve() else []) + \
            [d for d in extra if d.is_dir()]
    for d in cands:
        if (d / "meta.json").exists() or (d / "paper.pdf").exists():
            slug = d.name
            while slug in found and found[slug] != d:
                slug += "-1"
            found[slug] = d
    return found


def paper_dir(slug):
    d = paper_dirs().get(slug)
    if not d:
        abort(404, "没有这份资料")
    return d


def load_meta(d):
    try:
        return json.loads((d / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"title": d.name}


def load_discussion(d):
    f = d / "discussion.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8")).get("messages", [])
        except ValueError:
            pass
    return []


def save_discussion(d, msgs):
    history_mod.write_json(d / "discussion.json", {"messages": msgs})


def is_repo(d):
    return load_meta(d).get("kind") == "repo"


def snapshot(d, reason, messages=None, draft=None):
    return history_mod.save(d, load_discussion(d) if messages is None else messages,
                            notes_mod.load(d), reason, draft=draft)


@app.get("/api/papers/<slug>/history")
def history_list(slug):
    d = paper_dir(slug)
    with lock(slug):
        items = history_mod.listing(d)
        if not items and (load_discussion(d) or any(notes_mod.load(d)["sections"].values())):
            snapshot(d, "existing")
            items = history_mod.listing(d)
    return jsonify({"items": items})


@app.get("/api/papers/<slug>/history/<sid>")
def history_detail(slug, sid):
    try:
        return jsonify(history_mod.load(paper_dir(slug), sid))
    except (OSError, ValueError):
        abort(404, "没有这个历史版本")


def lock(slug):
    return _locks.setdefault(slug, threading.Lock())


def progress(d, msgs=None, notes=None):
    msgs = load_discussion(d) if msgs is None else msgs
    notes = notes_mod.load(d) if notes is None else notes
    talked = sorted({str(m.get("station")) for m in msgs if m.get("role") == "assistant"})
    noted = [k for k, v in notes["sections"].items() if v and v.strip()]
    return {"talked": talked, "noted": noted, "messages": len(msgs)}


@app.get("/api/papers")
def list_papers():
    out = []
    for slug, d in paper_dirs().items():
        meta = load_meta(d)
        idx = context.figures_dir(d) / "index.json"
        nfig = 0
        if idx.exists():
            try:
                nfig = sum(1 for it in json.loads(idx.read_text(encoding="utf-8")) if it.get("file"))
            except ValueError:
                pass
        mt = max([f.stat().st_mtime for f in (d / "discussion.json", d / "notes.json", d / "meta.json") if f.exists()] or [d.stat().st_mtime])
        item = {"slug": slug, "title": meta.get("title") or slug, "authors": meta.get("authors", [])[:4],
                "n_authors": len(meta.get("authors", [])), "published": meta.get("published", ""),
                "arxiv_id": meta.get("arxiv_id"), "kind": meta.get("kind", "paper"), "code": meta.get("official_code"), "figures": nfig,
                "has_latex": meta.get("has_latex"), "summary": (meta.get("summary") or "")[:400],
                "progress": progress(d), "mtime": mt, "path": str(d)}
        if item["kind"] == "repo":
            item.update({k: meta.get(k) for k in ("source", "source_url", "local_path", "subdir", "stars", "license",
                                                  "n_files", "n_code_lines", "commit", "branch", "paper_title", "from_paper")})
            item["languages"] = (meta.get("languages") or [])[:6]
            item["topics"] = (meta.get("topics") or [])[:5]
        out.append(item)
    out.sort(key=lambda x: -x["mtime"])
    return jsonify({"papers": out, "root": str(roots()[0]), "repos_root": str(repos_root())})


@app.get("/api/papers/<slug>")
def get_paper(slug):
    d = paper_dir(slug)
    meta = load_meta(d)
    fig = context.figures_dir(d)
    figures = []
    if (fig / "index.json").exists():
        try:
            figures = json.loads((fig / "index.json").read_text(encoding="utf-8"))
        except ValueError:
            pass
    msgs = load_discussion(d)
    nts = notes_mod.load(d)
    cr = context.code_root(d, meta)
    repo = None
    if meta.get("kind") != "repo":  # 未克隆的网页代码也能跳回已经建立的分析工作区
        for s2, d2 in paper_dirs().items():
            m2 = load_meta(d2)
            if m2.get("kind") == "repo" and m2.get("from_paper") == slug:
                repo = s2
                break
    return jsonify({"slug": slug, "path": str(d), "kind": meta.get("kind", "paper"), "meta": meta, "figures": figures,
                    "fig_dir": fig.name, "outline": context.read(d / "outline.md"), "has_pdf": (d / "paper.pdf").exists(),
                    "code_root": str(cr) if cr else None, "messages": msgs, "notes": nts, "repo_slug": repo,
                    "note_file": notes_mod.note_file(meta), "progress": progress(d, msgs, nts),
                    "sections": notes_mod.sections_for(meta)})


@app.get("/api/papers/<slug>/symbols")
def symbols(slug):
    f = paper_dir(slug) / "symbols.json"
    try:
        return jsonify(json.loads(f.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return jsonify({"prefix": "code/", "files": {}})


@app.get("/files/<slug>/<path:sub>")
def files(slug, sub):
    d = paper_dir(slug).resolve()
    f = (d / sub).resolve()
    if d not in f.parents or not f.is_file():
        abort(404)
    return send_file(f)


@app.get("/api/papers/<slug>/tree")
def tree(slug):
    d = paper_dir(slug)
    ws = context.Workspace(d, load_meta(d))
    rel = request.args.get("path", "code")
    try:
        p = ws.resolve(rel)
    except context.ToolError as e:
        return jsonify({"error": str(e), "items": []})
    if not p.is_dir():
        return jsonify({"error": "不是目录", "items": []})
    items = []
    for x in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
        if x.name in context.SKIP_DIRS or x.name.startswith("."):
            continue
        items.append({"name": x.name, "path": ws.display(x), "dir": x.is_dir(), "size": x.stat().st_size if x.is_file() else None})
    return jsonify({"path": ws.display(p), "items": items[:2000]})


@app.get("/api/papers/<slug>/text")
def text_file(slug):
    d = paper_dir(slug)
    ws = context.Workspace(d, load_meta(d))
    try:
        f = ws.resolve(request.args.get("path", ""))
    except context.ToolError as e:
        abort(400, str(e))
    if not f.is_file():
        abort(404)
    if f.stat().st_size > 3_000_000:
        return jsonify({"path": ws.display(f), "text": "（文件太大，不在网页里显示）", "big": True})
    with open(f, "rb") as fh:
        head = fh.read(8192)
    if b"\x00" in head:
        return jsonify({"path": ws.display(f), "text": "（二进制文件，不在网页里显示）", "big": True})
    return jsonify({"path": ws.display(f), "text": f.read_text(encoding="utf-8", errors="replace")})


@app.get("/api/papers/<slug>/raw")
def raw_file(slug):
    """代码目录里的图片 / PDF（代码可能在资料目录外，比如本机文件夹）。只读。"""
    d = paper_dir(slug)
    ws = context.Workspace(d, load_meta(d))
    try:
        f = ws.resolve(request.args.get("path", ""))
    except context.ToolError as e:
        abort(400, str(e))
    if not f.is_file() or f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".pdf", ".bmp", ".ico"):
        abort(404)
    resp = send_file(f)
    if f.suffix.lower() == ".svg":  # 仓库里的 SVG 可能带脚本：只当图片看
        resp.headers["Content-Security-Policy"] = "script-src 'none'"
    return resp


# ---------------- 导入 / 补代码 / 重裁图：后台任务 ----------------

def run_job(cmd, cwd, on_done=None):
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "status": "running", "log": [], "dest": None, "slug": None, "cmd": " ".join(map(str, cmd))}
    _jobs[jid] = job

    def work():
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONWARNINGS="ignore")
        status = "failed"
        try:
            with subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, env=env) as p:
                for raw in p.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip()
                    job["log"].append(line)
                    m = re.match(r"^\s*→\s*(.+)$", line)
                    if m:
                        job["dest"] = m.group(1).strip()
                p.wait()
                status = "done" if p.returncode == 0 else "failed"
            if status == "done":
                if on_done:
                    on_done(job)
                if job["dest"]:
                    dest = Path(job["dest"]).resolve()
                    for slug, d in paper_dirs().items():
                        if d.resolve() == dest:
                            job["slug"] = slug
                            break
        except Exception as e:  # noqa: BLE001
            job["log"].append(f"✗ {e}")
            status = "failed"
        finally:
            # 发布完成状态之前先登记资料并生成跳转地址，避免轮询拿到没有 slug 的完成任务。
            job["status"] = status

    threading.Thread(target=work, daemon=True).start()
    return job


def register_extra(job):
    """导入的是 papers_root / repos_root 之外的已有目录：记进 extra_papers，库里才看得到。"""
    if not job.get("dest"):
        return
    dest = Path(job["dest"]).resolve()
    if not (dest / "meta.json").exists():
        return
    if dest.parent not in (roots()[0].resolve(), repos_root().resolve()):
        s = settings()
        if str(dest) not in s["extra_papers"]:
            s["extra_papers"].append(str(dest))
            save_settings(s)


@app.post("/api/import")
def import_paper():
    root, _ = roots()
    f = request.files.get("pdf")
    form = request.form if (f or request.form) else (request.get_json(silent=True) or {})
    target = (form.get("target") or "").strip()
    if form.get("type") == "repo":  # 代码仓库：GitHub / Git 链接或本机文件夹
        if not target:
            return jsonify({"error": "给一个 GitHub / Git 链接，或者本机代码文件夹的完整路径"}), 400
        cmd = [sys.executable, "-u", SCRIPTS / "fetch_repo.py", target, "--root", repos_root()]
        for k in ("slug", "ref", "subdir", "title"):
            if (form.get(k) or "").strip():
                cmd += [f"--{k}", form[k].strip()]
        return jsonify(run_job(cmd, repos_root(), on_done=register_extra))
    if f and f.filename:
        up = UPLOADS / uuid.uuid4().hex[:8]
        up.mkdir(parents=True, exist_ok=True)
        name = re.sub(r'[\\/:*?"<>|]+', "_", Path(f.filename).name) or "paper.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        target = str(up / name)
        f.save(target)
    if not target:
        return jsonify({"error": "给一个网站 / arXiv / PDF 链接、本地 PDF 或资料目录"}), 400
    cmd = [sys.executable, "-u", SCRIPTS / "fetch_paper.py", target, "--root", root]
    if form.get("slug"):
        cmd += ["--slug", form["slug"]]
    if form.get("code"):
        cmd += ["--code", form["code"]]
    if str(form.get("no_clone", "")).lower() in ("1", "true", "on"):
        cmd += ["--no-clone"]
    job = run_job(cmd, root, on_done=register_extra)
    return jsonify(job)


@app.post("/api/papers/<slug>/analyze-code")
def analyze_code(slug):
    """论文工作区 → 把它的官方代码在代码分析器里打开（已克隆就直接分析本地那份，不重复下载）。"""
    d = paper_dir(slug)
    meta = load_meta(d)
    if meta.get("kind") == "repo":
        return jsonify({"error": "这已经是代码仓库"}), 400
    selected = (request.get_json(silent=True) or {}).get("url")
    if selected and (not isinstance(selected, str) or not re.match(
            r"^https://github\.com/[\w.-]+/[\w.-]+(?:[/?#]|$)", selected, re.I)):
        return jsonify({"error": "请选择完整的 GitHub 仓库链接"}), 400
    cr = context.code_root(d, meta) if not selected else None
    url = meta.get("official_code") or ""
    target = selected or (str(cr) if cr else url)
    if not target:
        return jsonify({"error": "这篇还没有代码：先在「代码 / 文件」里补上仓库地址"}), 400
    name = url.rstrip("/").split("/")[-1].removesuffix(".git") if url else ""
    cmd = [sys.executable, "-u", SCRIPTS / "fetch_repo.py", target, "--root", repos_root(), "--from-paper", slug,
           "--paper-title", meta.get("title") or slug]
    if cr and name:
        cmd += ["--title", name, "--slug", re.sub(r"[^\w.-]+", "-", f"{name}-{slug}")[:80].lower()]
    elif cr:
        cmd += ["--title", f"{meta.get('title') or slug} · 代码", "--slug", f"code-{slug}"[:80]]
    return jsonify(run_job(cmd, repos_root()))


@app.post("/api/papers/<slug>/reanalyze")
def reanalyze(slug):
    """代码仓库：拉最新提交（克隆的）并重新分析；讨论和笔记保留。"""
    d = paper_dir(slug)
    if not is_repo(d):
        return jsonify({"error": "只有代码仓库能重新分析"}), 400
    return jsonify(run_job([sys.executable, "-u", SCRIPTS / "fetch_repo.py", d], repos_root()))


@app.post("/api/papers/<slug>/code")
def add_code(slug):
    d = paper_dir(slug)
    if is_repo(d):
        return jsonify({"error": "代码仓库请用「重新分析」"}), 400
    url = (request.get_json(force=True).get("url") or "").strip()
    if not url:
        return jsonify({"error": "缺少仓库地址"}), 400
    return jsonify(run_job([sys.executable, "-u", SCRIPTS / "fetch_paper.py", d, "--code", url], roots()[0]))


@app.post("/api/papers/<slug>/refigures")
def refigures(slug):
    d = paper_dir(slug)
    if load_meta(d).get("kind") in ("website", "repo"):
        return jsonify({"error": "这类资料没有可重裁的 PDF 图表。"}), 400
    return jsonify(run_job([sys.executable, "-u", SCRIPTS / "extract_figures.py", d], roots()[0]))


@app.get("/api/jobs/<jid>")
def job(jid):
    j = _jobs.get(jid)
    if not j:
        abort(404)
    since = int(request.args.get("since", 0))
    return jsonify({**j, "log": j["log"][since:], "total": len(j["log"])})


# ---------------- 分析讨论 ----------------

def sse(obj):
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def to_llm_messages(d, msgs, keep=40, image_turns=2):
    """讨论记录 → 模型消息。只保留最近 keep 条；只有最近 image_turns 条带图的用户消息真的把图发过去。"""
    names = notes_mod.station_names(load_meta(d))
    msgs = [m for m in msgs if m.get("content") or m.get("images") or m.get("attachments")][-keep:]
    while msgs and msgs[0]["role"] != "user":
        msgs = msgs[1:]
    with_img = [i for i, m in enumerate(msgs) if m["role"] == "user" and m.get("images")][-image_turns:]
    out = []
    for i, m in enumerate(msgs):
        text = m.get("content", "")
        if m["role"] == "user":
            st = names.get(str(m.get("station")), "")
            for a in m.get("attachments") or []:
                text += f"\n\n[附：{a.get('path')}" + (f" 第 {a['start']}–{a['end']} 行" if a.get("start") else "") + "]\n```\n" + a.get("text", "") + "\n```"
            if m.get("images"):
                text += "\n\n[附图：" + "、".join(m["images"]) + "]"
            if st and m.get("kind") != "station":
                text = f"（当前在「{st}」）\n" + text
        images = []
        if i in with_img:
            for rel in m.get("images", []):
                f = (d / rel).resolve()
                if f.is_file() and d.resolve() in f.parents:
                    images.append(context.load_image(f))
        paths = [str((d / rel).resolve()) for rel in (m.get("images") or []) if (d / rel).is_file()] if m["role"] == "user" else []
        if out and out[-1]["role"] == m["role"]:  # 连续两条同角色（比如上一次生成失败）就合并
            out[-1]["content"] += "\n\n" + text
            out[-1]["images"] += images
            out[-1]["image_paths"] += paths
        else:
            out.append({"role": m["role"], "content": text, "images": images, "image_paths": paths})
    return out


def run_stream(d, slug, msgs_for_llm, on_finish):
    s = settings()
    meta = load_meta(d)
    system = context.build_system(d, meta, s)
    ws = context.Workspace(d, meta)
    acc, tools, err = [], [], None
    try:
        for ev in llm.stream(s, system, msgs_for_llm, ws):
            if ev["type"] == "text":
                acc.append(ev["text"])
            elif ev["type"] == "tool":
                tools.append(ev["summary"])
            elif ev["type"] == "error":
                err = ev["error"]
            yield sse(ev)
    except GeneratorExit:
        on_finish("".join(acc), tools, err or "生成已中断，已保存收到的内容")
        raise
    else:
        yield sse(on_finish("".join(acc), tools, err))


@app.post("/api/papers/<slug>/chat")
def chat(slug):
    d = paper_dir(slug)
    body = request.get_json(force=True)
    user = {"id": uuid.uuid4().hex[:10], "role": "user", "content": body.get("text", "").strip(),
            "station": str(body.get("station", "free")), "kind": body.get("kind", "chat"),
            "images": body.get("images") or [], "attachments": body.get("attachments") or [], "ts": now()}
    with lock(slug):
        msgs = load_discussion(d)
        if body.get("regenerate"):
            snapshot(d, "before_regenerate", msgs)
            while msgs and msgs[-1]["role"] == "assistant":
                msgs.pop()
            if not msgs:
                return jsonify({"error": "没有可以重新生成的消息"}), 400
            user = msgs[-1]
        else:
            msgs.append(user)
        save_discussion(d, msgs)
    llm_msgs = to_llm_messages(d, msgs)

    def finish(text, tools, err):
        reply = {"id": uuid.uuid4().hex[:10], "role": "assistant", "content": text.strip(), "station": user["station"],
                 "tools": tools, "error": err, "ts": now(), "model": settings().get("model") or settings().get("provider")}
        if text.strip() or err:
            with lock(slug):
                m2 = load_discussion(d)
                m2.append(reply)
                save_discussion(d, m2)
                snapshot(d, "analysis", m2)
        return {"type": "done", "message": reply, "user": user}

    def gen():
        yield sse({"type": "user", "message": user})
        yield from run_stream(d, slug, llm_msgs, finish)

    return Response(gen(), mimetype="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.delete("/api/papers/<slug>/messages/<mid>")
def delete_message(slug, mid):
    d = paper_dir(slug)
    with lock(slug):
        snapshot(d, "before_delete")
        msgs = [m for m in load_discussion(d) if m.get("id") != mid]
        save_discussion(d, msgs)
    return jsonify({"ok": True, "messages": msgs})


# ---------------- 精读笔记 ----------------

SECTION_GUIDE = {
    "basic": "写「基本情况」：3–6 条列表——谁做的（机构）、什么时候、发在哪；一句话：输入什么 → 输出什么；开源：代码 / 权重 / 数据各开没开；和用户读过的哪篇最像、差在哪（profile 里没有就省略）。",
    "map": "写「导读地图」：一张 Markdown 表，列为 站 | 这一站讲清楚什么（一句话） | 图 | 原文位置 | 代码，① 动机 到 ⑦ 实验 各一行。原文位置写 paper.tex 的行号（§2 L120–180），没源码写页码；代码写文件（:行）。可以先用工具查准位置。",
    "s1": "要点：要解决什么问题（具体场景）、以前的做法卡在哪（具体失败的样子）、作者押注的关键想法（一句话）、一个把问题讲实的例子；附 teaser 图。",
    "s2": "要点：总览图（附图）怎么读、模型接口参数（几帧、几步动作、多少 Hz）、按数据流顺序每个模块是什么、为什么要有它；最后一张表：模块 | 来源 / 初始化 | 参数量 | 训练时更新吗 | 作用。",
    "s3": "要点：一句人话的训练目标；公式（代码块 + Unicode）；符号表 | 符号 | 是什么 | 形状 / 取值 |；代一组小数字算一遍；为什么是这个损失；训练阶段（数据、冻结 / 更新哪些、步数 / batch / 算力）；loss 在代码哪里。",
    "s4": "要点：一个时刻的样本表 | 字段 | 形状 | 单位 / 取值 | 例子 |；怎么变成模型输入（归一化、tokenize、动作块怎么切）；规模和来源；开源没有。",
    "s5": "要点：一张文字流程图（代码块，箭头上标形状和次数）；哪些只算一次、哪些循环；训练和推理的流有什么不同；时间（控制频率、一次推理多久）。",
    "s6": "要点：场景（一句具体指令）；玩具尺寸下按时间顺序每一步：手里有什么 → 做了什么 → 变成什么（标 code/文件:行）；关键一步的大白话；最后一行把整条链串起来。",
    "s7": "要点：最关键的 2–3 个结果（数字 + 对比对象 + 一句话意义）、局限、资源需求、现在的地位（写明信息截止到什么时候）。",
    "code": "写「代码 ↔ 论文」：一张表 | 论文里 | 代码位置 | 备注（对不上的地方写这里） |，从讨论里讲过的对应关系整理，可以用工具核对行号。",
}


REPO_SECTION_GUIDE = {
    "basic": "写「项目概览」：4–7 条列表——一句话定位（给谁用、解决什么）；技术栈（语言 / 框架 / 关键依赖）；规模（文件数、代码行、主要目录）；"
             "成熟度信号（测试、CI、文档、最近提交、star，看得到才写）；怎么装、怎么跑（照 README，标明没实际运行）；许可证。",
    "map": "写「阅读地图」：一张 Markdown 表，列为 站 | 这一站讲清楚什么（一句话） | 先看的文件 / 符号（`code/路径:行`），① 定位 到 ⑦ 工程 各一行。"
           "可以先用工具查准位置。",
    "s1": "要点：没有它时要怎么做、痛在哪；它的做法（一句话）；对外接口表 | 入口 | 形式（CLI / 库 API / HTTP / 页面） | 例子 |；一个最小用法。",
    "s2": "要点：一张文字架构图（代码块，分层 + 依赖箭头）；模块表 | 目录 / 模块 | 职责 | 关键文件 | 依赖谁 |；最值得先读的 3–5 个文件。",
    "s3": "要点：启动链路按执行顺序，每步一行「做了什么 → `code/路径:行`」；配置项表 | 名字 | 默认值 | 从哪读 | 作用 |。",
    "s4": "要点：每个核心数据结构一张表 | 字段 | 类型 / 形状 | 含义 | 例子值 |；它从哪创建、在哪被修改、最后被谁消费。",
    "s5": "要点：核心调用链（代码块，缩进表示调用层级，标 `文件:行`）；关键分支、循环、并发、异常处理、性能热点。",
    "s6": "要点：场景（一条具体命令 / 请求 / 输入）；按时间顺序每一步：手里有什么 → 调了哪个函数（`code/路径:行`）→ 变成什么；最后一行串起整条链。",
    "s7": "要点：依赖表 | 名字 | 用途 | 是否核心 |；测试覆盖了什么 / 没覆盖什么；CI 和构建、部署；风险和技术债（给位置）；「想加 X 功能要改这几处」的具体例子。",
    "code": "写「关键文件索引」：一张表 | 文件 | 作用 | 关键符号（类 / 函数:行） | 什么时候需要看 |，按重要性排序，10–25 行，可以用工具核对行号。",
}


def draft_instruction(target, qa_pair=None, meta=None):
    repo = notes_mod.is_repo(meta)
    title = notes_mod.titles_for(meta).get(target, target)
    names = notes_mod.station_names(meta)
    label = notes_mod.note_label(meta)
    if repo:
        common = ("只输出这一节的正文 Markdown，不要写这一节的标题、不要开场白和结束语。"
                  "是整理过的要点，不是把回复原样粘贴。代码位置写成 `code/路径:行号`，结构图 / 调用链放代码块，表格用 Markdown 表格。"
                  "代码里看到的 / README 写的 / 推测的，要分清。")
        guide = REPO_SECTION_GUIDE
    else:
        common = ("只输出这一节的正文 Markdown，不要写这一节的标题、不要开场白和结束语。"
                  "是整理过的要点，不是把回复原样粘贴。图写成 `![图 N · 一句说明](figures/fig-NN.png)`（用图表索引里的真实路径），"
                  "公式放代码块用 Unicode，表格用 Markdown 表格。论文写的 / 代码看到的 / 推测的，要分清。")
        guide = SECTION_GUIDE
    if target == "qa" and qa_pair:
        q, a = qa_pair
        st = names.get(str(q.get("station")), "")
        return (f"把下面这组问答压成{label}「问答」里的一条，格式严格是：\n"
                f"- **Q（{st or '讨论'}）**：用户原话（可略删口语）\n  **A**：最后讲通的那个版本，几句话\n"
                "只输出这一条。\n\n【问】\n" + q.get("content", "") + "\n\n【答】\n" + a.get("content", ""))
    if target == "qa":
        return f"把我们讨论里我问过的问题整理成{label}的「问答」：每条格式 `- **Q（第 N 站）**：原话\\n  **A**：最后讲通的答案，几句话`，按时间顺序。只输出列表。"
    if target in ("basic", "map", "code"):
        return f"现在写{label}的「{title}」这一节。{guide[target]}\n\n{common}"
    return (f"把我们在「{title}」这一站的讨论整理成{label}里「{title}」这一节。{guide.get(target, '')}"
            f"讨论里没讲到的内容可以根据{'代码' if repo else '论文'}补上，但要简洁。\n\n{common}")


@app.get("/api/papers/<slug>/notes")
def get_notes(slug):
    return jsonify(notes_mod.load(paper_dir(slug)))


@app.put("/api/papers/<slug>/notes")
def put_notes(slug):
    d = paper_dir(slug)
    body = request.get_json(force=True)
    with lock(slug):
        snapshot(d, "before_notes")
        n = notes_mod.save(d, body.get("sections", {}), load_meta(d))
        snapshot(d, "notes")
    return jsonify(n)


@app.post("/api/papers/<slug>/notes/draft")
def draft_notes(slug):
    d = paper_dir(slug)
    body = request.get_json(force=True)
    target = body.get("target")
    if target not in notes_mod.TITLES:
        return jsonify({"error": "未知的节"}), 400
    msgs = load_discussion(d)
    qa_pair = None
    if target == "qa" and body.get("msg_id"):
        i = next((i for i, m in enumerate(msgs) if m.get("id") == body["msg_id"]), None)
        if i is None:
            return jsonify({"error": "找不到这条消息"}), 404
        if msgs[i]["role"] == "assistant":
            a = msgs[i]
            q = next((m for m in reversed(msgs[:i]) if m["role"] == "user"), {"content": ""})
        else:
            q = msgs[i]
            a = next((m for m in msgs[i + 1:] if m["role"] == "assistant"), {"content": ""})
        qa_pair = (q, a)
        history = []
    else:
        st = target[1:] if re.fullmatch(r"s\d", target) else None
        history = [m for m in msgs if st is None or str(m.get("station")) in (st, "free") or (st == "1" and str(m.get("station")) == "0")]
        if st and not any(m["role"] == "assistant" for m in history):
            history = msgs  # 这一站还没单独讨论过，就拿全部讨论
    llm_msgs = to_llm_messages(d, history, keep=30, image_turns=0)
    llm_msgs.append({"role": "user", "content": draft_instruction(target, qa_pair, load_meta(d)), "images": []})
    if len(llm_msgs) >= 2 and llm_msgs[-2]["role"] == "user":
        llm_msgs[-2]["content"] += "\n\n" + llm_msgs.pop()["content"]

    def finish(text, tools, err):
        if text.strip() or err:
            with lock(slug):
                snapshot(d, "draft", draft={"target": target, "text": text, "error": err})
        return {"type": "done", "text": text, "error": err, "target": target}

    return Response(run_stream(d, slug, llm_msgs, finish), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/papers/<slug>/notes/view")
def view_notes(slug):
    d = paper_dir(slug)
    html = notes_mod.render(d, notes_mod.load(d), load_meta(d), mode="web", slug=slug)
    return Response(html, mimetype="text/html")


@app.get("/api/papers/<slug>/export")
def export(slug):
    d = paper_dir(slug)
    meta = load_meta(d)
    transcript = load_discussion(d) if request.args.get("transcript") == "1" else None
    html = notes_mod.render(d, notes_mod.load(d), meta, mode="standalone", discussion=transcript)
    label = notes_mod.note_label(meta)
    name = re.sub(r'[\\/:*?"<>|]+', "_", f"{label}-{meta.get('title') or slug}")[:120] + ".html"
    if request.args.get("save") == "1":  # 同时在资料目录里留一份自包含的
        (d / f"{label}-导出.html").write_text(html, encoding="utf-8")
    from urllib.parse import quote
    return Response(html, mimetype="text/html", headers={
        "Content-Disposition": f"attachment; filename=notes.html; filename*=UTF-8''{quote(name)}"})


# ---------------- 页面 ----------------

@app.get("/")
def index():
    return send_from_directory(WEB / "static", "index.html")


@app.errorhandler(404)
@app.errorhandler(400)
def err(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": getattr(e, "description", str(e))}), e.code
    return e


def _free_port(host, port, tries=20):
    import socket
    for p in range(port, port + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
            try:
                sk.bind((host, p))
                return p
            except OSError:
                continue
    sys.exit(f"端口 {port}–{port + tries - 1} 都被占用了，用 --port 换一个")


def _open_when_ready(host, port, url):
    import socket
    import time
    import webbrowser
    for _ in range(100):
        try:
            with socket.create_connection((host, port), timeout=0.3):
                break
        except OSError:
            time.sleep(0.15)
    webbrowser.open(url)


def main():
    import argparse
    s = settings()
    ap = argparse.ArgumentParser(description="Bling-Workspace：论文精读 + 代码分析")
    ap.add_argument("--host", default=s["host"])
    ap.add_argument("--port", type=int, default=s["port"])
    ap.add_argument("--open", action="store_true", help="启动后打开浏览器")
    a = ap.parse_args()
    port = _free_port(a.host, a.port)
    if port != a.port:
        print(f"端口 {a.port} 被占用，改用 {port}")
    url = f"http://{'127.0.0.1' if a.host in ('0.0.0.0', '') else a.host}:{port}"
    print(f"\n  Bling-Workspace 已启动 → {url}\n  论文 / 网站：{roots()[0]}\n  代码仓库：{repos_root()}\n"
          "  浏览器没自动打开的话，手动访问上面的地址。关掉这个窗口就停止。\n")
    if a.open:
        threading.Thread(target=_open_when_ready, args=("127.0.0.1", port, url), daemon=True).start()
    app.run(host=a.host, port=port, threaded=True, debug=False)


if __name__ == "__main__":
    main()
