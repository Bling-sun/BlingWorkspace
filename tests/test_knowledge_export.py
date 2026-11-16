"""Knowledge persistence, report generation and portable document regression tests."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "web"), str(ROOT / "scripts")]
import server
import notes
import knowledge
import learning_export
import context
import fetch_website


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = dict(server.DEFAULTS, provider="openai", papers_root=str(self.root / "papers"),
                           repos_root=str(self.root / "repos"), work_groups=[], deleted_items=[])
        self.patch = patch.object(server, "settings", side_effect=lambda: dict(self.config))
        self.patch.start()
        self.client = server.app.test_client()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def create(self, **fields):
        response = self.client.post("/api/knowledge", json={"title": "Flow Matching", **fields})
        self.assertEqual(response.status_code, 201)
        self.slug = response.get_json()["slug"]
        self.directory = server.paper_dir(self.slug)
        return self.client.get("/api/papers/" + self.slug).get_json()

    def test_knowledge_persists_uses_own_prompt_sections_and_notes(self):
        item = self.create(domain="具身智能", goal="自己实现", learning_mode="基础 + 前沿")
        self.assertEqual(item["kind"], "knowledge")
        self.assertIn("推导", dict(item["sections"])["s2"])
        self.assertEqual(self.client.get("/api/papers").get_json()["papers"][0]["kind"], "knowledge")
        prompt = context.build_system(self.directory, item["meta"], {"provider": "mock"})
        for required in ("先修", "自测", "待验证", "尚未核验", "RSI", "自己实现"):
            self.assertIn(required, prompt)
        self.assertNotIn("SKILL.md（带读流程）", prompt)
        response = self.client.put(f"/api/papers/{self.slug}/notes", json={"sections": {"s2": "推导 ∇L", "s7": "待验证"}})
        self.assertEqual(response.status_code, 200)
        rendered = (self.directory / "知识点学习笔记.html").read_text(encoding="utf-8")
        self.assertIn("② 原理与推导", rendered)
        self.assertNotIn("<h2>② 架构</h2>", rendered)
        self.assertIn("推导 ∇L", notes.load(self.directory)["sections"]["s2"])
        self.assertEqual(self.client.post(f"/api/papers/{self.slug}/refigures").status_code, 400)

    def test_create_rejects_invalid_and_path_like_title_is_only_data(self):
        for body in ({"title": ""}, {"title": 3}, {"title": "a", "source_urls": ["file:///C:/secret"]},
                     {"title": "a", "source_urls": ["https://a.test"] * 6}, {"title": "a", "goal": {}}):
            self.assertEqual(self.client.post("/api/knowledge", json=body).status_code, 400)
        self.create(title="../../escape")
        self.assertEqual(self.directory.parent, self.root / "papers")

    def test_source_snapshots_show_success_failure_and_provenance(self):
        self.create(source_urls=["https://a.test/", "https://fail.test/"])
        page = b"<html><title>Official</title><p>" + b"A long primary source. " * 30 + b"</p></html>"
        with patch.object(fetch_website, "download", side_effect=[(page, "https://a.test/v2", "text/html", "utf-8"), ValueError("offline")]):
            knowledge.refresh_sources(self.directory)
        snapshots = json.loads((self.directory / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual([s["status"] for s in snapshots], ["ok", "failed"])
        prompt = context.build_system(self.directory, server.load_meta(self.directory), {})
        self.assertIn("https://a.test/v2", prompt)
        self.assertIn("offline", prompt)
        self.assertIn("抓取日期不等于发布日期", prompt)
        with patch.object(server, "run_job", return_value={"id": "test", "status": "running"}) as job:
            r = self.client.post(f"/api/papers/{self.slug}/knowledge-sources", json={"source_urls": ["https://new.test"]})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(server.load_meta(self.directory)["source_urls"], ["https://new.test/"])
            job.assert_called_once()

    def seed_discussion(self):
        server.save_discussion(self.directory, [
            {"id": "q", "role": "user", "station": "2", "content": "请推导", "ts": "2026-11-13"},
            {"id": "a", "role": "assistant", "station": "2", "content": "速度 v = 2。∇L。", "ts": "2026-11-13"},
        ])

    def test_direct_export_html_and_tex_all_kinds_preserve_notes_and_discussion(self):
        self.create()
        for kind in ("paper", "repo", "website", "knowledge"):
            meta = {"title": "中文 & test_#%", "kind": kind}
            (self.directory / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
            notes.save(self.directory, {"s2": "核心笔记\n\n```python\nx = 2\n```"}, meta)
            self.seed_discussion()
            for fmt in ("html", "tex"):
                response = self.client.get(f"/api/papers/{self.slug}/export?format={fmt}&transcript=1&save=1")
                self.assertEqual(response.status_code, 200)
                self.assertIn("核心笔记", response.get_data(as_text=True))
                self.assertIn("请推导", response.get_data(as_text=True))
                self.assertIn("filename*=UTF-8", response.headers["Content-Disposition"])
                self.assertTrue(list(self.directory.glob("*-导出." + fmt)))

    @staticmethod
    def fake_stream(settings, system, messages, ws):
        yield {"type": "text", "text": "## 核心结论\n\n速度 v = 2。\n\n## 复习\n\n未作答，待验证。"}

    def test_one_click_report_formats_download_and_preserves_originals(self):
        self.create()
        self.seed_discussion()
        original = (self.directory / "discussion.json").read_bytes()
        for fmt in ("tex", "html"):
            with patch.object(server.llm, "stream", side_effect=self.fake_stream) as model:
                response = self.client.post(f"/api/papers/{self.slug}/study-export", json={"format": fmt})
                events = [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines() if line.startswith("data: ")]
            self.assertEqual(events[-1]["type"], "done")
            self.assertIn("请推导", model.call_args.args[2][0]["content"])
            result = self.client.get(events[-1]["url"])
            self.assertEqual(result.status_code, 200)
            self.assertIn("待验证", result.get_data(as_text=True))
            self.assertEqual((self.directory / "discussion.json").read_bytes(), original)
            if fmt == "tex":
                self.assertFalse(list((self.directory / "learning-exports").glob("*.html")))
                self.assertIn("\\documentclass", result.get_data(as_text=True))

    def test_failure_does_not_publish_partial_report(self):
        self.create()
        self.seed_discussion()
        def fail(*args):
            yield {"type": "text", "text": "partial"}
            yield {"type": "error", "error": "quota"}
        with patch.object(server.llm, "stream", side_effect=fail):
            response = self.client.post(f"/api/papers/{self.slug}/study-export", json={"format": "tex"})
            self.assertIn('"error": "quota"', response.get_data(as_text=True))
        self.assertFalse((self.directory / "learning-exports").exists())
        self.config["provider"] = "mock"
        self.assertEqual(self.client.post(f"/api/papers/{self.slug}/study-export", json={"format": "tex"}).status_code, 400)

    def test_long_report_inputs_include_oldest_and_newest(self):
        messages = [{"role": "user", "content": "FIRST" + "x" * 700}, {"role": "assistant", "content": "LAST"}]
        chunks = learning_export.report_inputs(messages, notes.empty_notes(), {"title": "test"}, budget=150)
        self.assertGreater(len(chunks), 1)
        self.assertIn("FIRST", "".join(chunks))
        self.assertIn("LAST", "".join(chunks))

    def test_tex_handles_tables_code_math_and_escapes_tex_input(self):
        markdown = "## 数学\n∇L = α × x²\n\n| 变量 | 含义 |\n|---|---|\n| x_1 | 100% & A |\n\n```python\n\\end{quote}\\input{secret}\nx = 1\n```\n\n[来源](https://a.test/p?q=1&x=2)\n\n<script>alert(1)</script>"
        tex = learning_export.render_tex("学习 #1", markdown)
        self.assertIn(r"\begin{longtable}", tex)
        self.assertIn(r"\ensuremath{\nabla}", tex)
        self.assertIn(r"100\% \& A", tex)
        self.assertNotIn(r"\input{secret}", tex)
        self.assertNotIn("alert(1)", tex)
        self.assertIn(r"\href{https://a.test/p?q=1\&x=2}", tex)
        doc = learning_export.render_html("test", markdown, self.root, {})
        self.assertNotIn("<script>", doc)
        self.assertIn("script-src 'none'", doc)


if __name__ == "__main__":
    unittest.main()
