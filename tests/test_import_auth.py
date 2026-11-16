"""PDF lifetime and local Claude authentication regressions; no external model calls."""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "web")]
import fetch_paper
import fetch_website
import extract_figures
import llm
import server
import fitz


class DownloadedPdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.dest = self.base / "paper"
        with fitz.open() as doc:
            for _ in range(3):
                page = doc.new_page()
                page.insert_text((40, 50), "GR00T 2: A valid downloaded PDF for Windows lifetime checks")
            doc.set_metadata({"title": "GR00T 2: A valid downloaded PDF"})
            self.pdf = doc.tobytes()
        self.url = "https://research.nvidia.com/labs/gear/gr00t-2/assets/gr00t2_whitepaper.pdf"
        self.temp_dirs = []
        original = tempfile.TemporaryDirectory
        def tracked(*args, **kwargs):
            kwargs["dir"] = self.base
            item = original(*args, **kwargs)
            self.temp_dirs.append(Path(item.name))
            return item
        patcher = patch.object(fetch_paper.tempfile, "TemporaryDirectory", side_effect=tracked)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_import(self, target=None, **extra):
        with patch.object(sys, "argv", ["fetch_paper.py", target or self.url, "--dest", str(self.dest), "--no-clone"]), \
                patch.object(fetch_website, "download", return_value=(self.pdf, self.url, "application/pdf", "utf-8")) as download, \
                patch.object(fetch_paper, "collect_links", return_value={}), \
                patch.object(extract_figures, "extract", return_value=[]), patch("builtins.print"):
            fetch_paper.main()
        return download

    def test_pdf_import_finishes_and_temp_file_is_closed_before_unlink(self):
        self.run_import()
        self.assertEqual((self.dest / "paper.pdf").read_bytes(), self.pdf)
        self.assertIn("GR00T 2", (self.dest / "paper.txt").read_text(encoding="utf-8"))
        self.assertEqual(json.loads((self.dest / "meta.json").read_text(encoding="utf-8"))["source_url"], self.url)
        self.assertTrue(self.temp_dirs)
        self.assertTrue(all(not path.exists() for path in self.temp_dirs))

    def test_reimport_existing_pdf_preserves_notes_and_cleans_unused_download(self):
        self.run_import()
        (self.dest / "discussion.json").write_text('{"messages":[]}', encoding="utf-8")
        (self.dest / "notes.json").write_text('{"sections":{"s1":"keep me"}}', encoding="utf-8")
        before = {name: (self.dest / name).read_bytes() for name in ("paper.pdf", "discussion.json", "notes.json")}
        self.run_import()
        self.assertEqual({name: (self.dest / name).read_bytes() for name in before}, before)
        self.assertTrue(all(not path.exists() for path in self.temp_dirs))

    def test_temp_directory_is_cleaned_if_metadata_parsing_raises(self):
        with patch.object(fetch_paper, "title_from_pdf", side_effect=RuntimeError("parse failed")):
            with self.assertRaisesRegex(RuntimeError, "parse failed"):
                self.run_import()
        self.assertTrue(all(not path.exists() for path in self.temp_dirs))

    def test_local_pdf_source_is_never_removed(self):
        source = self.base / "original.pdf"
        source.write_bytes(self.pdf)
        download = self.run_import(str(source))
        download.assert_not_called()
        self.assertEqual(source.read_bytes(), self.pdf)
        self.assertTrue(all(not path.exists() for path in self.temp_dirs))


class ClaudeAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.exe = r"C:\Users\A Person\.local\bin\claude.exe"

    def test_status_hides_private_fields_and_uses_membership_environment(self):
        payload = {"loggedIn": True, "authMethod": "claude.ai", "configDirectory": "local-config",
                   "email": "private@example.com", "accessToken": "DO-NOT-RETURN"}
        result = subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        with patch.object(llm, "find_cli", return_value=self.exe), patch.object(llm.subprocess, "run", return_value=result) as run, \
                patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-api", "ANTHROPIC_AUTH_TOKEN": "fake-auth", "CLAUDE_CODE_OAUTH_TOKEN": "fake-member"}):
            status = llm.claude_auth_status({})
        self.assertTrue(status["logged_in"])
        self.assertNotIn("private@example.com", json.dumps(status))
        self.assertNotIn("DO-NOT-RETURN", json.dumps(status))
        env = run.call_args.kwargs["env"]
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", env)
        self.assertEqual(env["CLAUDE_CODE_OAUTH_TOKEN"], "fake-member")
        self.assertIn(self.exe, status["login_command"])

    def test_not_logged_in_stops_before_sending_context_to_a_model(self):
        with patch.object(llm, "find_cli", return_value=self.exe), \
                patch.object(llm, "claude_auth_status", return_value={"logged_in": False}), patch.object(llm, "_popen") as launch:
            events = list(llm.stream({"provider": "claude_cli"}, "private material", [], None))
        launch.assert_not_called()
        self.assertEqual(events[0]["type"], "error")
        self.assertIn(self.exe, events[0]["error"])
        self.assertIn("auth login", events[0]["error"])
        self.assertIn("免 API Key", events[0]["error"])

    def test_missing_or_old_cli_is_unknown_not_falsely_logged_in(self):
        with patch.object(llm, "find_cli", return_value=None):
            self.assertFalse(llm.claude_auth_status()["available"])
        with patch.object(llm, "find_cli", return_value=self.exe), patch.object(llm.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "not JSON", "unsupported")):
            self.assertIsNone(llm.claude_auth_status()["logged_in"])
        with patch.object(llm, "find_cli", return_value=self.exe), patch.object(llm.subprocess, "run", side_effect=subprocess.TimeoutExpired("claude", 8)):
            self.assertIsNone(llm.claude_auth_status()["logged_in"])

    def stream_with_result(self, payload):
        process = MagicMock()
        process.stdout = io.BytesIO((json.dumps(payload) + "\n").encode())
        process.returncode = 0
        process.poll.return_value = 0
        with patch.object(llm, "find_cli", return_value=self.exe), patch.object(llm, "claude_auth_status", return_value={"logged_in": True}), \
                patch.object(llm, "_popen", return_value=process), patch.object(llm, "_feed"), patch.object(llm, "_drain_stderr"):
            return list(llm.stream({"provider": "claude_cli"}, "test", [], None))

    def test_logged_in_cli_returns_normal_model_result(self):
        events = self.stream_with_result({"type": "result", "subtype": "success", "result": "连接成功"})
        self.assertTrue(any(ev.get("text") == "连接成功" for ev in events))
        self.assertFalse(any(ev["type"] == "error" for ev in events))

    def test_expired_session_has_actionable_full_path_login_instruction(self):
        events = self.stream_with_result({"type": "result", "is_error": True, "result": "Not logged in · Please run /login"})
        self.assertIn("auth login", events[0]["error"])
        self.assertIn("刷新登录状态", events[0]["error"])

    def test_auth_diagnostic_endpoint_does_not_call_a_model(self):
        status = {"available": True, "logged_in": True, "auth_method": "claude.ai", "path": self.exe}
        with patch.object(llm, "claude_auth_status", return_value=status), patch.object(llm, "stream") as model:
            response = server.app.test_client().get("/api/settings/claude-auth")
        self.assertEqual(response.get_json(), status)
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
