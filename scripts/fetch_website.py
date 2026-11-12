"""Public HTML material importer; no JavaScript execution or third-party dependencies."""
import datetime
import hashlib
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "Bling-Workspace/1.0 (website reader)"
BLOCKS = {"p", "div", "section", "article", "main", "header", "footer", "li", "tr", "pre", "blockquote", "br"}


def web_url(value, base=""):
    url = urllib.parse.urljoin(base, value or "")
    p = urllib.parse.urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        return None
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path or "/", p.query, ""))


def download(url, limit=8_000_000):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as response:
        final = web_url(response.geturl())
        if not final:
            raise ValueError("不支持的重定向地址")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"资源超过 {limit} 字节限制：{url}")
        return data, final, response.headers.get_content_type(), response.headers.get_content_charset() or "utf-8"


class Page(HTMLParser):
    def __init__(self, url):
        super().__init__(convert_charrefs=True)
        self.url = url
        self.parts, self.links, self.images, self.headings = [], [], [], []
        self.title, self.description = "", ""
        self.hidden = []
        self.in_title = False
        self.heading = None
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"script", "style", "noscript", "template", "svg"}:
            self.hidden.append(tag)
        if self.hidden:
            return
        if tag == "base":
            self.url = web_url(a.get("href"), self.url) or self.url
        if tag == "title":
            self.in_title = True
        if tag == "meta" and (a.get("name", "").lower() == "description" or a.get("property") == "og:description"):
            self.description = a.get("content", "")
        if tag in BLOCKS or re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n")
        if re.fullmatch(r"h[1-6]", tag):
            self.heading = [int(tag[1]), []]
            self.parts.append("#" * int(tag[1]) + " ")
        if tag == "a":
            url = web_url(a.get("href"), self.url)
            self.anchor = {"url": url, "text": ""} if url else None
        if tag == "img":
            url = web_url(a.get("src") or a.get("data-src"), self.url)
            if url:
                self.images.append({"url": url, "caption": a.get("alt") or a.get("title") or "网页图片"})
        if tag in {"td", "th"}:
            self.parts.append(" | ")
        if tag == "li":
            self.parts.append("- ")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if tag == "title":
            self.in_title = False
        if tag == "a" and self.anchor:
            self.links.append(self.anchor)
            self.anchor = None
        if re.fullmatch(r"h[1-6]", tag) and self.heading:
            level, words = self.heading
            self.headings.append((level, " ".join("".join(words).split())))
            self.heading = None
        if tag in BLOCKS or re.fullmatch(r"h[1-6]", tag):
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self.hidden:
            return
        if self.in_title:
            self.title += data
            return
        text = re.sub(r"[ \t\r\f\v]+", " ", data)
        self.parts.append(text)
        if self.heading:
            self.heading[1].append(text)
        if self.anchor:
            self.anchor["text"] += text

    @property
    def text(self):
        return re.sub(r"\n\s*\n(?:\s*\n)+", "\n\n", "".join(self.parts)).strip()


def fetch_website(url, args, initial=None, dest=None):
    from fetch_paper import pick_dest, slugify, log, clone

    data, final, mime, charset = initial or download(url)
    if mime not in ("text/html", "application/xhtml+xml") and not data.lstrip().lower().startswith((b"<!doctype html", b"<html")):
        raise ValueError(f"不支持的网页类型：{mime}；请提供 HTML 网页或 PDF")
    first = Page(final)
    first.feed(data.decode(charset, errors="replace"))
    if len(first.text) < 100:
        raise ValueError("网页可提取正文不足 100 字符，可能需要登录或 JavaScript 渲染；请导出 PDF 后导入")
    slug = "website-" + hashlib.sha256(final.encode()).hexdigest()[:10] + "-" + slugify(first.title, "page")[:35]
    dest = dest or pick_dest(args, args.slug or slug)
    dest.mkdir(parents=True, exist_ok=True)
    log(f"▸ 网站 · {first.title.strip() or final}")
    log(f"  → {dest}")
    pages_dir = dest / "pages"
    pages_dir.mkdir(exist_ok=True)
    queue = [(final, first, data)]
    seen, sources, all_links, figures, warnings = {final}, [], [], [], []
    texts, outline = [], ["# 网站材料大纲", "", "正文见 website.md；每页标明来源 URL，图片见 figures/index.md。", ""]
    image_seen = set()
    while queue and len(sources) < args.max_pages:
        current, page, raw = queue.pop(0)
        if page is None:
            try:
                raw, resolved, content_type, enc = download(current)
                if urllib.parse.urlsplit(resolved).netloc != urllib.parse.urlsplit(final).netloc:
                    continue
                if content_type not in ("text/html", "application/xhtml+xml"):
                    continue
                page = Page(resolved)
                page.feed(raw.decode(enc, errors="replace"))
                current = resolved
            except Exception as exc:
                warnings.append(f"子页面失败 {current}: {exc}")
                continue
        number = len(sources) + 1
        path = f"pages/page-{number:02}.txt"
        title = " ".join(page.title.split()) or current
        content = f"# {title}\n\n来源：{current}\n\n{page.text}\n"
        (dest / path).write_text(content, encoding="utf-8")
        # Raw HTML is retained for auditing, never embedded or executed in the UI.
        (pages_dir / f"page-{number:02}.html.txt").write_bytes(raw)
        sources.append({"url": current, "title": title, "file": path, "characters": len(page.text)})
        texts.append(content)
        outline += [f"## {number}. {title}", f"来源：{current} · `{path}`"] + ["  " * (level - 1) + "- " + h for level, h in page.headings] + [""]
        all_links.extend(dict(link, source=current) for link in page.links)
        log(f"  ✓ {title}（{len(page.text)} 字符）")
        for image in page.images:
            if image["url"] in image_seen or len(image_seen) >= args.max_images:
                continue
            image_seen.add(image["url"])
            try:
                blob, image_url, typ, _ = download(image["url"], limit=12_000_000)
                ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp", "image/gif": ".gif"}.get(typ)
                if not ext:
                    continue
                n = len(figures) + 1
                file = f"figures/web-{n:02}{ext}"
                (dest / "figures").mkdir(exist_ok=True)
                (dest / file).write_bytes(blob)
                figures.append(dict(image, num=n, kind="figure", file=file, page=None, source=current, source_url=image_url, mode="网页原图"))
            except Exception as exc:
                warnings.append(f"图片失败 {image['url']}: {exc}")
        if len(sources) + len(queue) < args.max_pages:
            candidates = sorted(page.links, key=lambda x: not bool(re.search(r"doc|overview|task|guide|method|about|介绍|文档", x["url"] + x["text"], re.I)))
            for link in candidates:
                candidate = link["url"]
                p = urllib.parse.urlsplit(candidate)
                if candidate in seen or p.netloc != urllib.parse.urlsplit(final).netloc or p.query:
                    continue
                if re.search(r"\.(?:pdf|zip|gz|png|jpg|svg|mp4|gif|webp|bib)$", p.path, re.I):
                    continue
                seen.add(candidate)
                queue.append((candidate, None, None))
                if len(sources) + len(queue) >= args.max_pages:
                    break
    links = {"project": [{"url": final}], "code": [], "paper": [], "documentation": []}
    for link in all_links:
        u = link["url"]
        key = "code" if re.match(r"https://github\.com/[^/]+/[^/#?]+/?$", u) else "paper" if "arxiv.org/" in u or urllib.parse.urlsplit(u).path.endswith(".pdf") else "documentation" if re.search(r"doc|guide|文档", u + link["text"], re.I) else None
        if key and not any(x["url"] == u for x in links[key]):
            links[key].append(link)
    official = args.code or next((x["url"] for x in links["code"] if re.search(r"code|代码|github", x.get("text", ""), re.I)), None)
    meta_path = dest / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update(kind="website", title=" ".join(first.title.split()) or final, source_url=final,
                summary=first.description or first.text[:500], sources=sources, links=links,
                fetched=datetime.datetime.now(datetime.timezone.utc).isoformat(), warnings=warnings,
                official_code=official or meta.get("official_code"), official_code_from="网站资源链接", has_latex=False)
    if official and not args.no_clone:
        code_dir = Path(args.code_dir).expanduser().resolve() if args.code_dir else dest / "code"
        state = clone(official, code_dir)
        if state in ("ok", "exists"):
            meta["code_dir"] = str(code_dir)
        else:
            warnings.append(f"代码未克隆成功：{state}")
    body = "\n\n---\n\n".join(texts)
    (dest / "website.md").write_text(body, encoding="utf-8")
    (dest / "outline.md").write_text("\n".join(outline), encoding="utf-8")
    (dest / "links.json").write_text(json.dumps(all_links, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "figures").mkdir(exist_ok=True)
    (dest / "figures/index.json").write_text(json.dumps(figures, ensure_ascii=False, indent=2), encoding="utf-8")
    (dest / "figures/index.md").write_text("\n\n".join(f"图 {f['num']} · {f['caption']}\n文件：{f['file']}\n来源：{f['source']}\n原图：{f['source_url']}" for f in figures), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"  ✓ {len(sources)} 页 · {len(figures)} 张图片 · website.md · outline.md · meta.json")
    for warning in warnings:
        log(f"  · {warning}")
    log("下一步：读 website.md 和图表索引，按网站资料流程分析；未抓取的链接不能作为已读证据。")
    return dest
