"""Regression checks for proxy downloads and whole-record deletion/recovery."""
import http.client
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "web")]
import fetch_repo
import networking
import server


class NetworkTests(unittest.TestCase):
    def test_explicit_proxy_and_direct_share_git_and_http_environment(self):
        for setting, expected in (("http://127.0.0.1:7897", "http://127.0.0.1:7897"), ("direct", "")):
            env = networking.proxy_environment(setting, {"https_proxy": "http://old:7890", "PATH": "keep"})
            self.assertNotIn("https_proxy", env)
            self.assertEqual(env["BLING_NETWORK_PROXY"], expected or "direct")
            self.assertEqual(env.get("HTTPS_PROXY", ""), expected)
            with patch.dict(os.environ, env, clear=True), patch.object(fetch_repo.subprocess, "Popen") as run:
                run.return_value.communicate.return_value = ("", "")
                fetch_repo.git("clone", "https://github.com/o/r.git", "code")
                self.assertEqual(run.call_args.args[0][1:3], ["-c", "http.proxy=" + expected])
            with patch.dict(os.environ, env, clear=True), patch.object(networking.urllib.request, "build_opener") as opener:
                networking.urlopen("https://github.com", timeout=2)
                self.assertEqual(opener.call_args.args[0].proxies, {"http": expected, "https": expected} if expected else {})

    def test_auto_uses_system_proxy_for_git_too(self):
        with patch.object(networking.urllib.request, "getproxies", return_value={"https": "http://127.0.0.1:7897"}):
            self.assertEqual(networking.resolve_proxy(), "http://127.0.0.1:7897")

    def test_auto_detects_running_upload_script_proxy(self):
        with patch.object(networking.urllib.request, "getproxies", return_value={}), \
                patch.object(networking.shutil, "which", return_value=None), \
                patch.object(networking.socket, "create_connection"):
            self.assertEqual(networking.resolve_proxy(), "http://127.0.0.1:7897")

    def test_invalid_proxy_rejected(self):
        for value in ("socks5://localhost:7897", "localhost:7897", "http://localhost:99999", "http://localhost"):
            with self.assertRaises(ValueError):
                networking.validate_proxy(value)

    def test_zip_retries_alternate_endpoint_after_disconnect(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r-main/main.py", "print('downloaded')\n")
        with tempfile.TemporaryDirectory() as tmp, patch.object(fetch_repo, "http_get", side_effect=[
            http.client.RemoteDisconnected("connection closed"), buf.getvalue()
        ]) as download:
            fetch_repo.github_zip("o", "r", "release/v1", Path(tmp) / "code")
            self.assertTrue((Path(tmp) / "code/main.py").is_file())
            self.assertIn("codeload.github.com", download.call_args_list[0].args[0])
            self.assertIn("github.com/o/r/archive/", download.call_args_list[1].args[0])


class RecordDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "original-code"
        self.source.mkdir()
        (self.source / "main.py").write_text("original = True\n", encoding="utf-8")
        self.record = self.base / "repos/demo"
        self.record.mkdir(parents=True)
        (self.record / "meta.json").write_text(json.dumps({"kind": "repo", "title": "Demo",
            "source": "local", "code_dir": str(self.source), "local_path": str(self.source)}), encoding="utf-8")
        self.config = self.base / "config.json"
        self.config.write_text(json.dumps({"provider": "mock", "papers_root": str(self.base / "papers"),
            "repos_root": str(self.base / "repos"), "network_proxy": "direct"}), encoding="utf-8")
        patches = patch.object(server, "CONFIG", self.config)
        patches.start()
        self.addCleanup(patches.stop)
        self.client = server.app.test_client()

    def test_delete_and_restore_complete_record_preserves_source_notes_and_history(self):
        messages = [{"id": "q1", "role": "user", "content": "read code", "station": "1"}]
        server.save_discussion(self.record, messages)
        self.client.put("/api/papers/demo/notes", json={"sections": {"s1": "Important notes"}})
        server.snapshot(self.record, "analysis")
        before = {p.relative_to(self.record): p.read_bytes() for p in self.record.rglob("*") if p.is_file()}
        deleted = self.client.delete("/api/papers/demo")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get("/api/papers").get_json()["papers"], [])
        self.assertEqual(self.client.get("/api/papers/demo").status_code, 404)
        self.assertEqual(self.client.get("/api/papers/demo/history").status_code, 404)
        self.assertEqual((self.source / "main.py").read_text(encoding="utf-8"), "original = True\n")
        restarted = server.app.test_client()
        items = restarted.get("/api/trash").get_json()["items"]
        self.assertEqual(len(items), 1)
        restored = restarted.post(f"/api/trash/{items[0]['id']}/restore")
        self.assertEqual(restored.get_json()["slug"], "demo")
        self.assertEqual(restarted.get("/api/papers/demo").get_json()["messages"], messages)
        self.assertEqual(restarted.get("/api/trash").get_json()["items"], [])
        self.assertEqual({p.relative_to(self.record): p.read_bytes() for p in self.record.rglob("*") if p.is_file()}, before)

    def test_external_record_and_reimport(self):
        cfg = server.settings()
        external = self.base / "external/demo"
        external.mkdir(parents=True)
        (external / "meta.json").write_text('{"title":"External"}', encoding="utf-8")
        cfg["extra_papers"] = [str(external)]
        server.save_settings(cfg)
        slug = next(k for k, d in server.paper_dirs().items() if d == external)
        self.assertEqual(self.client.delete(f"/api/papers/{slug}").status_code, 200)
        self.assertTrue((external / "meta.json").is_file())
        server.register_extra({"dest": str(external)})
        self.assertIn(external, server.paper_dirs().values())
        self.assertEqual(self.client.get("/api/trash").get_json()["items"], [])

    def test_bad_restore_id_and_missing_source(self):
        item = self.client.delete("/api/papers/demo").get_json()["item"]
        self.assertEqual(self.client.delete("/api/papers/demo").status_code, 404)
        self.assertEqual(self.client.post("/api/trash/unknown/restore").status_code, 404)
        moved = self.record.with_name("moved")
        self.record.rename(moved)
        self.assertEqual(self.client.post(f"/api/trash/{item['id']}/restore").status_code, 409)
        self.assertEqual(len(self.client.get("/api/trash").get_json()["items"]), 1)

    def test_settings_validate_proxy_and_cannot_bypass_deletion(self):
        self.client.delete("/api/papers/demo")
        self.assertEqual(self.client.post("/api/settings", json={"network_proxy": "bad proxy"}).status_code, 400)
        self.assertEqual(self.client.post("/api/settings", json={"network_proxy": "http://127.0.0.1:7897", "deleted_items": []}).status_code, 200)
        self.assertEqual(len(self.client.get("/api/trash").get_json()["items"]), 1)


if __name__ == "__main__":
    unittest.main()
