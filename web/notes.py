"""笔记：网页端用 notes.json 存每一节的 Markdown，同时渲染成资料目录里的 HTML——
论文 / 网站是「精读笔记.html」，代码仓库是「代码分析笔记.html」。两类笔记的 section key 一样，只是标题和模板不同。

- 渲染用 references/notes-template.html 当骨架（和 SKILL.md 让 agent 写的是同一份模板），只替换每个
  <section data-key="…"> 的正文，所以网页端和 agent 写出来的笔记长得一样、可以互相读。
- 精读笔记.html 被别人（比如 Claude Code 里的 agent）改过、比 notes.json 新时，读的时候从 HTML 里把每一节捞回来。
- 老的 精读笔记.md 也能迁移：按「## 标题」切成节。
"""
import base64
import datetime
import html
import json
import mimetypes
import re
from pathlib import Path

import markdown as md

NOTE_HTML = "精读笔记.html"
NOTE_MD = "精读笔记.md"
NOTE_JSON = "notes.json"
CODE_NOTE_HTML = "代码分析笔记.html"

SECTIONS = [
    ("basic", "基本情况"),
    ("map", "导读地图"),
    ("s1", "① 动机"),
    ("s2", "② 架构"),
    ("s3", "③ 训练"),
    ("s4", "④ 数据"),
    ("s5", "⑤ 输入输出信息流"),
    ("s6", "⑥ 例子走一遍"),
    ("s7", "⑦ 实验与地位"),
    ("qa", "问答"),
    ("code", "代码 ↔ 论文"),
]
REPO_SECTIONS = [
    ("basic", "项目概览"),
    ("map", "阅读地图"),
    ("s1", "① 定位"),
    ("s2", "② 结构"),
    ("s3", "③ 入口"),
    ("s4", "④ 数据"),
    ("s5", "⑤ 主流程"),
    ("s6", "⑥ 例子走一遍"),
    ("s7", "⑦ 工程与质量"),
    ("qa", "问答"),
    ("code", "关键文件索引"),
]
KEYS = [k for k, _ in SECTIONS]
TITLES = dict(SECTIONS)

REFS = Path(__file__).resolve().parent.parent / "references"
TEMPLATE = REFS / "notes-template.html"
CODE_TEMPLATE = REFS / "code-notes-template.html"


def is_repo(meta):
    return bool(meta) and meta.get("kind") == "repo"


def sections_for(meta):
    return REPO_SECTIONS if is_repo(meta) else SECTIONS


def titles_for(meta):
    return dict(sections_for(meta))


def note_file(meta):
    return CODE_NOTE_HTML if is_repo(meta) else NOTE_HTML


def note_label(meta):
    return "代码分析笔记" if is_repo(meta) else "精读笔记"


def _meta_of(paper_dir):
    try:
        return json.loads((Path(paper_dir) / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def empty_notes():
    return {"sections": {k: "" for k in KEYS}, "updated": None, "html_mtime": None}


# ---------------- 读 ----------------

SEC_RE = re.compile(r'(<section\b[^>]*\bdata-key="(\w+)"[^>]*>)(.*?)(</section>)', re.S)
H2_RE = re.compile(r'^\s*<h2\b[^>]*>.*?</h2>\s*', re.S)


def parse_html(text):
    out = {}
    for m in SEC_RE.finditer(text):
        key, body = m.group(2), m.group(3)
        if key in TITLES:
            body = H2_RE.sub("", body, count=1).strip()
            body = re.sub(r'<p class="empty">.*?</p>', "", body).strip()  # 渲染时给空节加的占位
            if "{{" in body:  # 模板占位符原样没填，当空节
                body = ""
            out[key] = body
    return out


def parse_md(text):
    """老格式 精读笔记.md → 节。标题模糊匹配：含「动机」→ s1 …"""
    hints = {"基本情况": "basic", "导读地图": "map", "动机": "s1", "架构": "s2", "训练": "s3", "数据": "s4",
             "信息流": "s5", "例子": "s6", "实验": "s7", "问答": "qa", "代码": "code"}
    out, cur, buf = {}, None, []

    def flush():
        if cur:
            out[cur] = (out.get(cur, "") + "\n".join(buf)).strip()

    for line in text.splitlines():
        if line.startswith("## "):
            flush()
            buf = []
            title = line[3:]
            cur = next((k for h, k in hints.items() if h in title), None)
            continue
        buf.append(line)
    flush()
    return out


def load(paper_dir, meta=None):
    p = Path(paper_dir)
    meta = _meta_of(p) if meta is None else meta
    j, h, m = p / NOTE_JSON, p / note_file(meta), p / NOTE_MD
    notes = empty_notes()
    if j.exists():
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
            notes["sections"].update(data.get("sections", {}))
            notes["updated"] = data.get("updated")
            notes["html_mtime"] = data.get("html_mtime")
        except ValueError:
            pass
        # HTML 在网页端之外被改过 → 以 HTML 为准
        if h.exists() and notes["html_mtime"] and h.stat().st_mtime > notes["html_mtime"] + 1:
            notes["sections"].update(parse_html(h.read_text(encoding="utf-8", errors="ignore")))
            notes["imported_from"] = h.name
        return notes
    if h.exists():
        notes["sections"].update(parse_html(h.read_text(encoding="utf-8", errors="ignore")))
        notes["imported_from"] = h.name
    elif m.exists() and not is_repo(meta):
        notes["sections"].update(parse_md(m.read_text(encoding="utf-8", errors="ignore")))
        notes["imported_from"] = NOTE_MD
    return notes


# ---------------- 渲染 ----------------

def md_to_html(text):
    if not text or not text.strip():
        return ""
    return md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")


def repo_meta_line(meta):
    bits = []
    src = meta.get("source_url") or meta.get("remote_url")
    if src:
        bits.append(f'<a href="{html.escape(src, quote=True)}">{html.escape(src)}</a>')
    elif meta.get("local_path"):
        bits.append("本机：" + html.escape(meta["local_path"]))
    if meta.get("subdir"):
        bits.append("子目录 " + html.escape(meta["subdir"]))
    if meta.get("commit"):
        bits.append("提交 " + html.escape(meta["commit"][:10]) + (f"（{html.escape(meta['branch'])}）" if meta.get("branch") else ""))
    langs = meta.get("languages") or []
    if langs:
        bits.append(html.escape(" / ".join(f"{l['name']} {l['pct']}%" for l in langs[:3])))
    if meta.get("n_code_lines"):
        bits.append(f"代码 {meta['n_code_lines']:,} 行")
    if meta.get("paper_title"):
        bits.append("论文：" + html.escape(meta["paper_title"]))
    bits.append("分析于 " + html.escape(str(meta.get("fetched", ""))[:10]))
    return " · ".join(bits)


def meta_line(meta):
    if is_repo(meta):
        return repo_meta_line(meta)
    bits = []
    if meta.get("kind") == "website" and meta.get("source_url"):
        source = html.escape(meta["source_url"], quote=True)
        bits.append(f'网站：<a href="{source}">{source}</a>')
        bits.append("抓取于 " + html.escape(str(meta.get("fetched", ""))[:10]))
    aid = meta.get("arxiv_id")
    if aid:
        bits.append(f'<a href="https://arxiv.org/abs/{html.escape(aid)}">arXiv {html.escape(aid)}</a>')
    venue = meta.get("journal_ref") or ""
    if venue:
        bits.append(html.escape(venue))
    au = meta.get("authors") or []
    if au:
        bits.append(html.escape("、".join(au[:3]) + (f" 等 {len(au)} 人" if len(au) > 3 else "")))
    if meta.get("published"):
        bits.append(html.escape(str(meta["published"])[:10]))
    code = meta.get("official_code")
    bits.append(f'代码：<a href="{html.escape(code)}">{html.escape(code)}</a>' if code else "代码：无")
    return " · ".join(bits)


def _inline_images(doc, paper_dir):
    root = Path(paper_dir).resolve()

    def repl(m):
        src = m.group(2)
        if re.match(r"^(https?:|data:|/)", src):
            return m.group(0)
        f = (root / src).resolve()
        if root not in f.parents or not f.is_file():
            return m.group(0)
        mime = mimetypes.guess_type(f.name)[0] or "image/png"
        b64 = base64.b64encode(f.read_bytes()).decode()
        return f'{m.group(1)}data:{mime};base64,{b64}{m.group(3)}'

    return re.sub(r'(<img\b[^>]*?\bsrc=")([^"]+)(")', repl, doc)


def _web_paths(doc, slug):
    """在网页里预览时，相对路径指到 /files/<slug>/…"""
    return re.sub(r'(<img\b[^>]*?\bsrc=")(?!https?:|data:|/)([^"]+)(")',
                  lambda m: f'{m.group(1)}/files/{slug}/{m.group(2)}{m.group(3)}', doc)


def render(paper_dir, notes, meta, mode="file", slug=None, discussion=None):
    """mode: file（写进论文目录，图用相对路径）/ standalone（图内嵌成 base64，单文件可分享）/ web（网页预览）"""
    title = meta.get("title") or Path(paper_dir).name
    titles = titles_for(meta)
    tpl = (CODE_TEMPLATE if is_repo(meta) else TEMPLATE).read_text(encoding="utf-8")
    tpl = re.sub(r"<!--.*?-->\s*", "", tpl, count=1, flags=re.S)  # 去掉给 agent 的说明注释
    tpl = re.sub(r"<title>.*?</title>", lambda m: f"<title>{note_label(meta)} · {html.escape(title)}</title>", tpl, count=1, flags=re.S)
    tpl = re.sub(r'(<h1 id="note-title">).*?(</h1>)', lambda m: m.group(1) + html.escape(title) + m.group(2), tpl, flags=re.S)
    tpl = re.sub(r'(<p class="meta" id="note-meta">).*?(</p>)', lambda m: m.group(1) + meta_line(meta) + m.group(2), tpl, flags=re.S)

    secs = notes.get("sections", {})

    def fill(m):
        open_tag, key, body, close = m.group(1), m.group(2), m.group(3), m.group(4)
        h2 = H2_RE.match(body)
        head = h2.group(0).strip() if h2 else f"<h2>{titles.get(key, key)}</h2>"
        content = md_to_html(secs.get(key, ""))
        if not content:
            content = '<p class="empty">（还没整理）</p>'
        return f"{open_tag}\n{head}\n{content}\n{close}"

    doc = SEC_RE.sub(fill, tpl)

    if discussion:
        doc = doc.replace('<p class="foot" id="note-foot">', _discussion_html(discussion, meta) + '\n<p class="foot" id="note-foot">', 1)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = re.sub(r'(<p class="foot" id="note-foot">).*?(</p>)',
                 lambda m: m.group(1) + f"由 Bling-Workspace 生成 · 更新于 {now}" + m.group(2), doc, flags=re.S)
    if mode == "standalone":
        doc = _inline_images(doc, paper_dir)
    elif mode == "web" and slug:
        doc = _web_paths(doc, slug)
    return doc


STATION_NAMES = {"0": "开场", "1": "① 动机", "2": "② 架构", "3": "③ 训练", "4": "④ 数据", "5": "⑤ 信息流",
                 "6": "⑥ 例子", "7": "⑦ 实验", "free": "自由讨论"}
REPO_STATION_NAMES = {"0": "概览", "1": "① 定位", "2": "② 结构", "3": "③ 入口", "4": "④ 数据", "5": "⑤ 主流程",
                      "6": "⑥ 例子", "7": "⑦ 工程", "free": "自由讨论"}


def station_names(meta):
    return REPO_STATION_NAMES if is_repo(meta) else STATION_NAMES


def _discussion_html(messages, meta=None):
    names = station_names(meta)
    parts = ['<section class="note-sec" data-key="transcript" id="transcript"><h2>附录 · 讨论记录</h2>']
    for msg in messages:
        who = "我" if msg.get("role") == "user" else "AI"
        st = names.get(str(msg.get("station", "")), "")
        parts.append(f"<details><summary>{who}{' · ' + st if st else ''} · {html.escape(msg.get('ts', '')[:16])}</summary>")
        parts.append(md_to_html(msg.get("content", "")))
        parts.append("</details>")
    parts.append("</section>")
    return "\n".join(parts)


def save(paper_dir, sections, meta):
    p = Path(paper_dir)
    notes = empty_notes()
    notes["sections"].update({k: v for k, v in sections.items() if k in TITLES})
    notes["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    h = p / note_file(meta)
    h.write_text(render(p, notes, meta, mode="file"), encoding="utf-8")
    notes["html_mtime"] = h.stat().st_mtime
    (p / NOTE_JSON).write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    return notes
