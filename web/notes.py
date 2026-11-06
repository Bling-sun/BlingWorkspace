"""精读笔记：网页端用 notes.json 存每一节的 Markdown，同时把它渲染成论文目录里的「精读笔记.html」。

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
KEYS = [k for k, _ in SECTIONS]
TITLES = dict(SECTIONS)

TEMPLATE = Path(__file__).resolve().parent.parent / "references" / "notes-template.html"


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


def load(paper_dir):
    p = Path(paper_dir)
    j, h, m = p / NOTE_JSON, p / NOTE_HTML, p / NOTE_MD
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
            notes["imported_from"] = NOTE_HTML
        return notes
    if h.exists():
        notes["sections"].update(parse_html(h.read_text(encoding="utf-8", errors="ignore")))
        notes["imported_from"] = NOTE_HTML
    elif m.exists():
        notes["sections"].update(parse_md(m.read_text(encoding="utf-8", errors="ignore")))
        notes["imported_from"] = NOTE_MD
    return notes


# ---------------- 渲染 ----------------

def md_to_html(text):
    if not text or not text.strip():
        return ""
    return md.markdown(text, extensions=["tables", "fenced_code", "sane_lists"], output_format="html")


def meta_line(meta):
    bits = []
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
    tpl = TEMPLATE.read_text(encoding="utf-8")
    tpl = re.sub(r"<!--.*?-->\s*", "", tpl, count=1, flags=re.S)  # 去掉给 agent 的说明注释
    tpl = tpl.replace("<title>精读笔记 · {{标题}}</title>", f"<title>精读笔记 · {html.escape(title)}</title>")
    tpl = re.sub(r'(<h1 id="note-title">).*?(</h1>)', lambda m: m.group(1) + html.escape(title) + m.group(2), tpl, flags=re.S)
    tpl = re.sub(r'(<p class="meta" id="note-meta">).*?(</p>)', lambda m: m.group(1) + meta_line(meta) + m.group(2), tpl, flags=re.S)

    secs = notes.get("sections", {})

    def fill(m):
        open_tag, key, body, close = m.group(1), m.group(2), m.group(3), m.group(4)
        h2 = H2_RE.match(body)
        head = h2.group(0).strip() if h2 else f"<h2>{TITLES.get(key, key)}</h2>"
        content = md_to_html(secs.get(key, ""))
        if not content:
            content = '<p class="empty">（还没整理）</p>'
        return f"{open_tag}\n{head}\n{content}\n{close}"

    doc = SEC_RE.sub(fill, tpl)

    if discussion:
        doc = doc.replace('<p class="foot" id="note-foot">', _discussion_html(discussion) + '\n<p class="foot" id="note-foot">', 1)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    doc = re.sub(r'(<p class="foot" id="note-foot">).*?(</p>)',
                 lambda m: m.group(1) + f"由 bling-paper-reading 精读工作台生成 · 更新于 {now}" + m.group(2), doc, flags=re.S)
    if mode == "standalone":
        doc = _inline_images(doc, paper_dir)
    elif mode == "web" and slug:
        doc = _web_paths(doc, slug)
    return doc


STATION_NAMES = {"0": "开场", "1": "① 动机", "2": "② 架构", "3": "③ 训练", "4": "④ 数据", "5": "⑤ 信息流",
                 "6": "⑥ 例子", "7": "⑦ 实验", "free": "自由讨论"}


def _discussion_html(messages):
    parts = ['<section class="note-sec" data-key="transcript" id="transcript"><h2>附录 · 讨论记录</h2>']
    for msg in messages:
        who = "我" if msg.get("role") == "user" else "AI"
        st = STATION_NAMES.get(str(msg.get("station", "")), "")
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
    (p / NOTE_HTML).write_text(render(p, notes, meta, mode="file"), encoding="utf-8")
    notes["html_mtime"] = (p / NOTE_HTML).stat().st_mtime
    (p / NOTE_JSON).write_text(json.dumps(notes, ensure_ascii=False, indent=1), encoding="utf-8")
    return notes
