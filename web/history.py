"""Durable, immutable local snapshots of analysis and notes."""
import datetime
import json
import os
import re
import tempfile
import uuid
from pathlib import Path


def write_json(path, value):
    """Publish only a complete JSON file, including on interrupted writes."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".saving-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save(paper, messages, notes, reason, draft=None):
    stamp = datetime.datetime.now().astimezone().isoformat(timespec="milliseconds")
    sid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:12]
    question = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "精读笔记")
    last = next((m for m in reversed(messages) if m.get("role") == "assistant"), {})
    snapshot = {"id": sid, "created": stamp, "reason": reason,
                "title": question[:100], "model": last.get("model", ""),
                "messages": messages, "notes": notes, "draft": draft}
    write_json(Path(paper) / "history" / (sid + ".json"), snapshot)
    return snapshot


def load(paper, sid):
    if not re.fullmatch(r"\d{8}-\d{6}-[a-f0-9]{12}", sid):
        raise ValueError("无效的历史版本")
    return json.loads((Path(paper) / "history" / (sid + ".json")).read_text(encoding="utf-8"))


def listing(paper):
    out = []
    for path in sorted((Path(paper) / "history").glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({k: data.get(k) for k in ("id", "created", "reason", "title", "model")}
                       | {"count": len(data.get("messages", []))})
        except (OSError, ValueError):
            continue
    return sorted(out, key=lambda item: item["created"], reverse=True)
