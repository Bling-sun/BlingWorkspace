"""代码分析器：python -m unittest discover -s tests；不联网、不调用模型。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "scripts"), str(REPO / "web")]
import fetch_repo  # noqa: E402
import context  # noqa: E402
import notes  # noqa: E402
import server  # noqa: E402


def make_project(root):
    """一个迷你多语言项目：Python 包（含相对导入和 __main__）、TS 前端、依赖清单、测试、CI。"""
    files = {
        "README.md": "# Demo\n\nA tiny demo project that turns raw text into tidy reports for the analyzer tests.\n",
        "pyproject.toml": '[project]\nname = "demo"\ndependencies = ["requests>=2", "rich"]\n[project.scripts]\ndemo = "demo.cli:main"\n',
        "src/demo/__init__.py": "from .core import Report\n",
        "src/demo/core.py": "class Report:\n    def __init__(self, text):\n        self.text = text\n\n    def render(self):\n        return self.text.upper()\n\n\ndef build(text):\n    return Report(text)\n",
        "src/demo/cli.py": "import sys\nfrom demo.core import build\n\n\ndef main(argv=None):\n    print(build(' '.join(argv or sys.argv[1:])).render())\n\n\nif __name__ == '__main__':\n    main()\n",
        "web/src/api.ts": "export interface Item { id: number }\nexport async function load(): Promise<Item[]> { return [] }\n",
        "web/src/main.ts": "import { load } from './api'\nexport const start = async () => load()\n",
        "web/package.json": '{"name": "web", "dependencies": {"vue": "^3"}, "scripts": {"dev": "vite"}}',
        "tests/test_core.py": "from demo.core import build\n\n\ndef test_render():\n    assert build('a').render() == 'A'\n",
        ".github/workflows/ci.yml": "on: push\n",
        "node_modules/junk/index.js": "module.exports = 1\n",
        "LICENSE": "MIT\n",
    }
    for rel, text in files.items():
        f = Path(root) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


class ParseTargetTests(unittest.TestCase):
    def test_github_forms(self):
        t = fetch_repo.parse_target("https://github.com/owner/repo.git")
        self.assertEqual((t["kind"], t["owner"], t["repo"], t["ref"], t["subdir"]), ("github", "owner", "repo", None, ""))
        t = fetch_repo.parse_target("https://github.com/owner/repo/tree/dev/src/pkg")
        self.assertEqual((t["ref"], t["subdir"]), ("dev", "src/pkg"))
        t = fetch_repo.parse_target("git@github.com:owner/repo.git")
        self.assertEqual(t["url"], "https://github.com/owner/repo")
        self.assertEqual(fetch_repo.parse_target("owner/repo")["kind"], "github")

    def test_other_git_hosts_and_errors(self):
        t = fetch_repo.parse_target("https://gitee.com/team/proj/tree/master/lib")
        self.assertEqual((t["kind"], t["ref"], t["subdir"]), ("git", "master", "lib"))
        self.assertTrue(t["clone_url"].endswith(".git"))
        with self.assertRaises(ValueError):
            fetch_repo.parse_target("D:/definitely/not/here")

    def test_local_folder(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(fetch_repo.parse_target(d)["kind"], "local")


class AnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.proj = Path(self.tmp.name) / "proj"
        make_project(self.proj)
        self.root = Path(self.tmp.name) / "repos"

    def run_script(self, *args):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_repo.py"), *map(str, args)],
                           capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_local_analysis_outputs(self):
        out = self.run_script(self.proj, "--root", self.root)
        dest = self.root / "proj"
        self.assertIn(f"→ {dest.resolve()}", out)
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["kind"], "repo")
        self.assertEqual(meta["source"], "local")
        self.assertEqual(Path(meta["code_dir"]), self.proj.resolve())
        self.assertFalse((dest / "code").exists(), "本机文件夹不复制")
        langs = {l["name"] for l in meta["languages"]}
        self.assertTrue({"Python", "TypeScript"} <= langs)
        self.assertIn("src/demo/cli.py", [e["path"] for e in meta["entry_points"]])
        self.assertIn("requests", meta["dependencies"]["pyproject.toml"])
        self.assertIn({"name": "demo", "target": "demo.cli:main", "from": "pyproject.toml"}, meta["bins"])
        self.assertEqual(meta["tests"]["files"], 1)
        self.assertEqual(meta["ci"], [".github/workflows/ci.yml"])
        self.assertTrue(meta["summary"].startswith("A tiny demo project"))
        top = {m["path"]: m["imported_by"] for m in meta["top_modules"]}
        self.assertGreaterEqual(top.get("src/demo/core.py", 0), 2)  # __init__（相对导入）+ cli + tests
        self.assertIn("web/src/api.ts", top)
        syms = json.loads((dest / "symbols.json").read_text(encoding="utf-8"))["files"]
        self.assertIn("Report.render", [s["name"] for s in syms["src/demo/core.py"]])
        self.assertIn("load", [s["name"] for s in syms["web/src/api.ts"]])
        outline = (dest / "outline.md").read_text(encoding="utf-8")
        self.assertIn("`code/src/demo/cli.py:9`", outline)
        self.assertNotIn("node_modules", outline)
        self.assertIn("A tiny demo project", (dest / "repo.md").read_text(encoding="utf-8"))

    def test_subdir_title_and_refresh_keep_discussion(self):
        self.run_script(self.proj, "--root", self.root, "--subdir", "src", "--title", "Demo Core")
        dest = self.root / "demo-core"
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual((meta["title"], meta["subdir"]), ("Demo Core / src", "src"))
        self.assertTrue(all(not e["path"].startswith("web/") for e in meta["entry_points"]))
        (dest / "discussion.json").write_text('{"messages": []}', encoding="utf-8")
        self.run_script(dest)  # 刷新已有分析目录
        self.assertTrue((dest / "discussion.json").exists())
        self.assertEqual(json.loads((dest / "meta.json").read_text(encoding="utf-8"))["title"], "Demo Core / src")

    def test_workspace_inside_analyzed_folder_is_skipped(self):
        root = self.proj / "repos"
        self.run_script(self.proj, "--root", root)
        meta = json.loads((root / "proj" / "meta.json").read_text(encoding="utf-8"))
        self.assertFalse(any("repos/" in e["path"] for e in meta["entry_points"]))
        self.assertNotIn("repos/", (root / "proj" / "outline.md").read_text(encoding="utf-8"))

    def test_rejects_source_overwrite_and_escaping_subdirectory(self):
        before = (self.proj / "README.md").read_bytes()
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_repo.py"), str(self.proj),
                            "--dest", str(self.proj.parent)], capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual((self.proj / "README.md").read_bytes(), before)
        self.assertFalse((self.proj.parent / "meta.json").exists())
        with self.assertRaises(ValueError):
            fetch_repo.analyze(self.proj, "../")

    def test_slug_cannot_escape_analysis_root(self):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_repo.py"), str(self.proj),
                            "--root", str(self.root), "--slug", "../escape"], capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_zip_fallback_strips_top_folder(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("repo-main/a.py", "print(1)\n")
            z.writestr("repo-main/pkg/b.py", "x = 1\n")
            z.writestr("repo-main/../evil.py", "bad\n")
        out = Path(self.tmp.name) / "unz"
        fetch_repo.safe_unzip(buf.getvalue(), out)
        self.assertTrue((out / "a.py").is_file() and (out / "pkg" / "b.py").is_file())
        self.assertFalse((Path(self.tmp.name) / "evil.py").exists())

    def test_github_without_git_uses_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("r-HEAD/main.go", "package main\n\nfunc main() {}\n")
        dest = Path(self.tmp.name) / "gh"
        argv = ["fetch_repo.py", "https://github.com/o/r", "--dest", str(dest)]
        with patch.object(sys, "argv", argv), patch.object(fetch_repo, "github_api", side_effect=OSError("offline")), \
                patch.object(fetch_repo.shutil, "which", return_value=None), \
                patch.object(fetch_repo, "http_get", return_value=buf.getvalue()), patch("builtins.print"):
            fetch_repo.main()
        meta = json.loads((dest / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["source"], "github")
        self.assertEqual(meta["entry_points"][0]["path"], "main.go")
        self.assertTrue(any("zip" in w for w in meta["warnings"]))

    def test_zip_refresh_replaces_deleted_files_and_preserves_on_failure(self):
        dest = Path(self.tmp.name) / "snapshot"
        dest.mkdir()
        (dest / "old.py").write_text("old = True\n", encoding="utf-8")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("repo-main/new.py", "new = True\n")
        with patch.object(fetch_repo, "http_get", return_value=buf.getvalue()):
            fetch_repo.github_zip("o", "r", "main", dest)
        self.assertTrue((dest / "new.py").is_file())
        self.assertFalse((dest / "old.py").exists())
        with patch.object(fetch_repo, "http_get", side_effect=OSError("offline")):
            with self.assertRaises(OSError):
                fetch_repo.github_zip("o", "r", "main", dest)
        self.assertTrue((dest / "new.py").is_file())


class WebRepoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.proj = base / "proj"
        make_project(self.proj)
        self.repos = base / "repos"
        subprocess.run([sys.executable, str(REPO / "scripts" / "fetch_repo.py"), str(self.proj), "--root", str(self.repos)],
                       capture_output=True, check=True, env=dict(os.environ, PYTHONUTF8="1"))
        self.dest = self.repos / "proj"
        cfg = base / "config.json"
        cfg.write_text(json.dumps({"provider": "mock", "papers_root": str(base / "papers"), "repos_root": str(self.repos)}), encoding="utf-8")
        p = patch.object(server, "CONFIG", cfg)
        p.start()
        self.addCleanup(p.stop)
        self.client = server.app.test_client()

    def wait_job(self, job):
        deadline = time.monotonic() + 30
        while job["status"] == "running" and time.monotonic() < deadline:
            time.sleep(.05)
            job = self.client.get(f"/api/jobs/{job['id']}").get_json()
        self.assertEqual(job["status"], "done", job)
        self.assertTrue(job["slug"], job)
        return job

    def test_library_paper_api_and_notes(self):
        items = self.client.get("/api/papers").get_json()["papers"]
        repo = next(x for x in items if x["slug"] == "proj")
        self.assertEqual(repo["kind"], "repo")
        self.assertTrue(repo["languages"])
        p = self.client.get("/api/papers/proj").get_json()
        self.assertEqual(p["note_file"], "代码分析笔记.html")
        self.assertEqual(dict(p["sections"])["s3"], "③ 入口")
        tree = self.client.get("/api/papers/proj/tree?path=code").get_json()
        self.assertIn("src", [i["name"] for i in tree["items"]])
        self.assertNotIn("node_modules", [i["name"] for i in tree["items"]])
        text = self.client.get("/api/papers/proj/text?path=code/src/demo/core.py").get_json()
        self.assertIn("class Report", text["text"])
        self.assertEqual(self.client.get("/api/papers/proj/text?path=code/../../etc/passwd").status_code, 400)
        self.assertIn("src/demo/core.py", self.client.get("/api/papers/proj/symbols").get_json()["files"])
        r = self.client.put("/api/papers/proj/notes", json={"sections": {"s3": "入口在 `code/src/demo/cli.py:5`"}})
        self.assertEqual(r.status_code, 200)
        html = (self.dest / "代码分析笔记.html").read_text(encoding="utf-8")
        self.assertIn("③ 入口", html)
        self.assertIn("code/src/demo/cli.py:5", html)
        self.assertEqual(notes.load(self.dest)["sections"]["s3"], "入口在 `code/src/demo/cli.py:5`")
        exp = self.client.get("/api/papers/proj/export").headers["Content-Disposition"]
        self.assertIn("%E4%BB%A3%E7%A0%81%E5%88%86%E6%9E%90%E7%AC%94%E8%AE%B0", exp)  # 代码分析笔记

    def test_repo_prompt_and_mock_chat(self):
        meta = server.load_meta(self.dest)
        prompt = context.build_system(self.dest, meta, server.settings())
        self.assertIn("代码分析器", prompt)
        self.assertIn("code-reading.md", prompt)
        self.assertIn("仓库地图", prompt)
        self.assertIn("Report.render", prompt)
        self.assertNotIn("SKILL.md（带读流程）", prompt)
        body = self.client.post("/api/papers/proj/chat", json={"text": "开始", "station": "0"}).get_data(as_text=True)
        self.assertIn("code/src/demo/cli.py:9", body)
        self.assertIn("「③ 入口」", server.draft_instruction("s3", meta=meta))

    def test_reanalyze_and_paper_code_routes(self):
        job = self.client.post("/api/papers/proj/reanalyze").get_json()
        self.assertIn("fetch_repo.py", job["cmd"])
        self.wait_job(job)
        self.assertEqual(self.client.post("/api/papers/proj/refigures").status_code, 400)
        paper = Path(self.tmp.name) / "papers" / "p1"
        (paper / "code").mkdir(parents=True)
        (paper / "code" / "x.py").write_text("print(1)\n", encoding="utf-8")
        (paper / "meta.json").write_text(json.dumps({"title": "P1", "official_code": "https://github.com/o/tool"}), encoding="utf-8")
        job = self.client.post("/api/papers/p1/analyze-code").get_json()
        self.assertIn("--from-paper", job["cmd"])
        self.assertIn("--title tool", job["cmd"])
        self.wait_job(job)

    def test_select_github_resource_from_website(self):
        paper = Path(self.tmp.name) / "papers" / "site"
        paper.mkdir(parents=True)
        (paper / "meta.json").write_text(json.dumps({"kind": "website", "title": "Project site",
                                                      "official_code": "https://github.com/o/first"}), encoding="utf-8")
        with patch.object(server, "run_job", return_value={"id": "selected"}) as run:
            response = self.client.post("/api/papers/site/analyze-code", json={"url": "https://github.com/o/second"})
            self.assertEqual(response.status_code, 200)
            command = list(map(str, run.call_args.args[0]))
            self.assertIn("https://github.com/o/second", command)
            self.assertIn("--from-paper", command)
            self.assertNotIn("https://github.com/o/first", command)
        self.assertEqual(self.client.post("/api/papers/site/analyze-code", json={"url": "file:///private"}).status_code, 400)

    @unittest.skipUnless((server.REPO / "papers").is_dir(), "项目里没有 papers/")
    def test_renamed_project_folder_falls_back(self):
        missing = Path(self.tmp.name) / "old-name" / "papers"
        self.assertEqual(server._dir_setting(str(missing), "papers"), server.REPO / "papers")


if __name__ == "__main__":
    unittest.main()
