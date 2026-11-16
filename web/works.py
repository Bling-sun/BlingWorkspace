"""Work-level grouping. Materials, conversations, notes and history stay in place."""
import os
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def deleted_paths(item):
    return item.get("paths") or [item["path"]]


def group_views(groups, directories, load_meta):
    by_path = {path_key(path): (slug, path) for slug, path in directories.items()}
    views = []
    for group in groups:
        members = []
        for path in group["members"]:
            found = by_path.get(path_key(path))
            if found:
                slug, directory = found
                meta = load_meta(directory)
                members.append({"slug": slug, "path": str(directory.resolve()), "title": meta.get("title") or slug,
                                "kind": meta.get("kind", "paper")})
        primary = next((m for m in members if path_key(m["path"]) == path_key(group["primary"])), None)
        primary = primary or next((m for m in members if m["kind"] == "paper"), None) or next(iter(members), None)
        views.append({"id": group["id"], "title": group["title"], "members": members,
                      "primary_slug": primary["slug"] if primary else None,
                      "missing_count": len(group["members"]) - len(members)})
    return views


def canonical_url(value):
    if not isinstance(value, str):
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    path = parsed.path.rstrip("/").removesuffix(".git")
    return urlunsplit(("https", parsed.netloc.lower(), path.lower(), "", ""))


def identities(meta):
    result = set()
    if meta.get("arxiv_id"):
        result.add("arxiv:" + re.sub(r"v\d+$", "", str(meta["arxiv_id"])))
    links = [meta.get("source_url"), meta.get("official_code")]
    for kind in ("paper", "code", "project"):
        links.extend(x.get("url") if isinstance(x, dict) else x for x in (meta.get("links", {}).get(kind) or []))
    for url in links:
        normalized = canonical_url(url)
        if not normalized:
            continue
        match = re.search(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})(?:v\d+)?", normalized)
        if match:
            result.add("arxiv:" + match[1])
        else:
            result.add(normalized)
    return result


def suggestions(directories, load_meta, groups):
    grouped = {path_key(path) for group in groups for path in group["members"]}
    records = [(slug, load_meta(path)) for slug, path in directories.items() if path_key(path) not in grouped]
    candidates = []
    for i, (slug, meta) in enumerate(records):
        keys = identities(meta)
        for other, detail in records[i + 1:]:
            common = keys & identities(detail)
            if common:
                evidence = next(iter(sorted(common, key=lambda key: (not key.startswith("arxiv:"), key))))
            elif meta.get("from_paper") == other or detail.get("from_paper") == slug:
                evidence = "已有论文与代码关联"
            else:
                continue
            candidates.append({"slugs": [slug, other], "reason": evidence})
    return candidates
