"""Run with python -m unittest discover -s tests; no network or model calls."""
import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "web")]
import fetch_paper
import fetch_website as web
import context
import server
import notes


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dest = Path(self.tmp.name) / "material"
        self.args = argparse.Namespace(dest=str(self.dest), root=None, slug=None,
                                       max_pages=2, max_images=2, no_clone=True,
                                       code=None, code_dir=None)
        self.home = """<html><title>通用 Project</title><script>SECRET_SCRIPT</script>
        <h1>Architecture</h1><p>""" + "公开的项目资料 " * 30 + """</p>
        <table><tr><th>Size</th><td>42</td></tr></table>
        <a href='/docs/'>Document</a><a href='/docs/#duplicate'>Again</a>
        <a href='https://other.test/'>External</a>
        <a href='https://github.com/team/project'>Code</a>
        <a href='https://arxiv.org/abs/2506.18088'>Paper</a>
        <img src='/image.png' alt='Pipeline'></html>"""

    def get(self, url, **kwargs):
        if url.endswith("image.png"):
            raise OSError("image unavailable")
        return b"<html><title>Docs</title><h2>Usage</h2><p>Use the API</p></html>", url, "text/html", "utf-8"

    def ingest(self):
        with patch.object(web, "download", side_effect=self.get):
            return web.fetch_website("https://project.test/", self.args,
                                     initial=(self.home.encode(), "https://project.test/", "text/html", "utf-8"))

    def test_generic_material_and_provenance(self):
        self.ingest()
        meta = json.loads((self.dest / "meta.json").read_text(encoding="utf-8"))
        body = (self.dest / "website.md").read_text(encoding="utf-8")
        self.assertEqual(len(meta["sources"]), 2)
        self.assertIn("https://project.test/docs/", body)
        self.assertIn("42", body)
        self.assertNotIn("SECRET_SCRIPT", body)
        self.assertEqual(meta["official_code"], "https://github.com/team/project")
        self.assertEqual(len(meta["links"]["paper"]), 1)
        self.assertIn("image unavailable", meta["warnings"][0])
        self.assertFalse(list((self.dest / "pages").glob("*.html")))
        discussion = self.dest / "discussion.json"
        discussion.write_text("keep me", encoding="utf-8")
        self.ingest()
        self.assertEqual(discussion.read_text(encoding="utf-8"), "keep me")

    def test_context_api_and_note_export(self):
        self.ingest()
        meta = json.loads((self.dest / "meta.json").read_text(encoding="utf-8"))
        prompt = context.build_system(self.dest, meta, {"provider": "mock"})
        self.assertIn("## website.md", prompt)
        self.assertIn("网站未提供", prompt)
        self.assertIn("https://project.test/docs/", prompt)
        with patch.object(server, "roots", return_value=(Path(self.tmp.name), [])):
            client = server.app.test_client()
            listing = client.get("/api/papers").get_json()["papers"]
            self.assertEqual(listing[0]["kind"], "website")
            detail = client.get("/api/papers/material").get_json()
            self.assertFalse(detail["has_pdf"])
            self.assertEqual(client.get("/api/papers/material/text?path=website.md").status_code, 200)
            self.assertEqual(client.post("/api/papers/material/refigures").status_code, 400)
        notes.save(self.dest, {"basic": "网站资料", "s1": "动机"}, meta)
        html = (self.dest / "精读笔记.html").read_text(encoding="utf-8")
        self.assertIn("https://project.test/", html)
        self.assertIn('data-key="s1"', html)

    def test_short_dynamic_page_and_non_html_fail(self):
        for raw, mime in [(b"<html><div id='root'></div></html>", "text/html"), (b"{}", "application/json")]:
            with self.assertRaises(ValueError):
                web.fetch_website("https://project.test/", self.args,
                                  initial=(raw, "https://project.test/", mime, "utf-8"))

    def test_arxiv_and_local_pdf_routing_unchanged(self):
        self.assertEqual(fetch_paper.parse_target("https://arxiv.org/abs/2506.18088")["kind"], "arxiv")
        local = Path(self.tmp.name) / "example.pdf"
        local.write_bytes(b"%PDF-1.7")
        self.assertEqual(fetch_paper.parse_target(str(local))["kind"], "local-pdf")

    def test_download_without_pdf_suffix_uses_pdf_flow(self):
        with patch.object(sys, "argv", ["fetch_paper.py", "https://project.test/download"]), \
             patch.object(web, "download", return_value=(b"%PDF-1.7 test", "https://project.test/download", "application/pdf", "utf-8")), \
             patch.object(web, "fetch_website") as website, \
             patch.object(fetch_paper, "arxiv_id_from_pdf", side_effect=RuntimeError("reached PDF flow")):
            with self.assertRaisesRegex(RuntimeError, "reached PDF flow"):
                fetch_paper.main()
            website.assert_not_called()

    def test_html_with_pdf_suffix_uses_website_flow(self):
        response = (self.home.encode(), "https://project.test/article.pdf", "text/html", "utf-8")
        with patch.object(sys, "argv", ["fetch_paper.py", response[1]]), \
             patch.object(web, "download", return_value=response), \
             patch.object(web, "fetch_website") as website:
            fetch_paper.main()
            self.assertEqual(website.call_args.kwargs["initial"], response)

    def test_import_api_reuses_shared_importer(self):
        with patch.object(server, "roots", return_value=(Path(self.tmp.name), [])), \
             patch.object(server, "run_job", return_value={"id": "test"}) as run:
            client = server.app.test_client()
            result = client.post("/api/import", json={"target": "https://other-project.test/", "no_clone": True})
            self.assertEqual(result.status_code, 200)
            cmd = [str(x) for x in run.call_args.args[0]]
            self.assertIn("https://other-project.test/", cmd)
            self.assertIn("--no-clone", cmd)


if __name__ == "__main__":
    unittest.main()
