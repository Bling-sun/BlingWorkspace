"""Work grouping: preservation, shared evidence, read boundaries, recycle/restore."""
import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "web"), str(ROOT / "scripts")]
import context
import server
import works


class WorkGroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / "original-code"
        self.source.mkdir()
        (self.source / "main.py").write_text("def predict():\n    return 42\n", encoding="utf-8")
        self.dirs = {"paper": self.base / "papers/paper", "site": self.base / "papers/site",
                     "other": self.base / "papers/other", "code": self.base / "repos/code"}
        metas = {
            "paper": {"title": "SuperMimic: A Model", "arxiv_id": "2610.28480v2"},
            "site": {"kind": "website", "title": "SuperMimic", "source_url": "https://supermimic.test/", "links": {
                "paper": [{"url": "https://arxiv.org/pdf/2610.28480"}], "code": [{"url": "https://github.com/team/model"}]}},
            "code": {"kind": "repo", "title": "Model code", "source_url": "https://github.com/TEAM/model.git", "code_dir": str(self.source)},
            "other": {"title": "SuperMimic", "arxiv_id": "2000.12345"},
        }
        for slug, directory in self.dirs.items():
            directory.mkdir(parents=True)
            (directory / "meta.json").write_text(json.dumps(metas[slug]), encoding="utf-8")
            (directory / ("website.md" if slug == "site" else "repo.md" if slug == "code" else "paper.txt")).write_text(slug + " unique evidence", encoding="utf-8")
            server.save_discussion(directory, [{"id": "same-id", "role": "user", "content": slug + " private discussion", "station": "1"}])
            server.notes_mod.save(directory, {"s1": slug + " original notes"}, metas[slug])
            server.snapshot(directory, "analysis")
        self.png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aN1cAAAAASUVORK5CYII=")
        (self.dirs["site"] / "figures").mkdir()
        (self.dirs["site"] / "figures/demo.png").write_bytes(self.png)
        self.config = self.base / "config.json"
        self.config.write_text(json.dumps({"provider": "mock", "papers_root": str(self.base / "papers"),
            "repos_root": str(self.base / "repos"), "network_proxy": "direct"}), encoding="utf-8")
        cfg = patch.object(server, "CONFIG", self.config)
        cfg.start()
        self.addCleanup(cfg.stop)
        self.client = server.app.test_client()

    def merge(self, slugs=None):
        result = self.client.post("/api/work-groups", json={"title": "SuperMimic", "slugs": slugs or ["paper", "site"], "primary_slug": "paper"})
        self.assertEqual(result.status_code, 200, result.get_json())
        return result.get_json()["group"]

    def all_files(self):
        return {p.relative_to(self.base): p.read_bytes() for root in [*self.dirs.values(), self.source] for p in root.rglob("*") if p.is_file()}

    def test_suggestions_use_evidence_not_just_matching_titles(self):
        suggestions = self.client.get("/api/work-groups").get_json()["suggestions"]
        self.assertTrue(any(set(s["slugs"]) == {"paper", "site"} and "2610.28480" in s["reason"] for s in suggestions))
        self.assertTrue(any(set(s["slugs"]) == {"site", "code"} for s in suggestions))
        self.assertFalse(any("other" in s["slugs"] for s in suggestions))

    def test_merge_persists_and_dissolve_preserves_every_material_file(self):
        before = self.all_files()
        group = self.merge()
        fresh = server.app.test_client()
        result = fresh.get("/api/papers").get_json()
        self.assertEqual(len(result["papers"]), 4)
        self.assertEqual(result["work_groups"][0]["primary_slug"], "paper")
        self.assertEqual({m["slug"] for m in result["work_groups"][0]["members"]}, {"paper", "site"})
        for slug in ("paper", "site"):
            record = fresh.get("/api/papers/" + slug).get_json()
            self.assertEqual(record["messages"][0]["content"], slug + " private discussion")
            self.assertEqual(record["notes"]["sections"]["s1"], slug + " original notes")
            self.assertEqual(record["work_group"]["id"], group["id"])
        self.assertEqual(self.all_files(), before)
        self.assertEqual(fresh.delete("/api/work-groups/" + group["id"]).status_code, 200)
        self.assertIsNone(fresh.get("/api/papers/paper").get_json()["work_group"])
        self.assertEqual(self.all_files(), before)

    def test_joint_reading_has_selected_materials_and_repository_code(self):
        self.merge(["paper", "site", "code"])
        record = self.client.get("/api/papers/paper").get_json()
        self.assertEqual(record["code_root"], str(self.source))
        self.assertEqual(record["repo_slug"], "code")
        evidence = self.client.get("/api/papers/paper/text", query_string={"path": "materials/site/website.md"}).get_json()
        self.assertIn("site unique evidence", evidence["text"])
        code = self.client.get("/api/papers/paper/text", query_string={"path": "materials/code/code/main.py"}).get_json()
        self.assertIn("return 42", code["text"])
        meta = server.reading_meta(self.dirs["paper"])
        prompt = context.build_system(self.dirs["paper"], meta, server.settings())
        self.assertIn("同一工作的联合材料：SuperMimic", prompt)
        self.assertIn("site unique evidence", prompt)
        self.assertIn("code unique evidence", prompt)
        self.assertNotIn("other unique evidence", prompt)
        self.assertNotIn("site private discussion", prompt)
        ws = context.Workspace(self.dirs["paper"], meta)
        self.assertIn(self.dirs["site"], ws.extra_dirs)
        self.assertIn(self.source, ws.extra_dirs)
        self.assertEqual(self.client.get("/api/papers/paper/tree?path=materials").status_code, 200)

    def test_unselected_and_traversing_materials_are_denied(self):
        self.merge()
        for path in ("materials/other/paper.txt", "materials/site/../../other/paper.txt", "materials/site/../paper.txt"):
            self.assertEqual(self.client.get("/api/papers/paper/text", query_string={"path": path}).status_code, 400)
        meta = server.reading_meta(self.dirs["paper"])
        ws = context.Workspace(self.dirs["paper"], meta)
        result, _ = ws.run("read_text", {"path": "materials/other/paper.txt"})
        self.assertIn("出错", result)
        self.assertNotIn("other unique evidence", result)
        with self.client.get("/files/paper/materials/site/figures/demo.png") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/files/paper/materials/other/meta.json").status_code, 404)

    def test_imported_metadata_cannot_grant_work_access(self):
        file = self.dirs["other"] / "meta.json"
        meta = json.loads(file.read_text(encoding="utf-8"))
        meta["_work_members"] = [{"path": str(self.dirs["site"]), "slug": "site", "kind": "website"}]
        file.write_text(json.dumps(meta), encoding="utf-8")
        self.assertNotIn("_work_members", server.reading_meta(self.dirs["other"]))
        self.assertEqual(self.client.get("/api/papers/other/text?path=materials/site/website.md").status_code, 400)

    def test_cross_material_images_work_in_notes_and_export(self):
        self.merge()
        before = (self.dirs["site"] / "notes.json").read_bytes()
        image = "![Evidence](materials/site/figures/demo.png)"
        self.assertEqual(self.client.put("/api/papers/paper/notes", json={"sections": {"s1": image}}).status_code, 200)
        self.assertIn("data:image/png;base64,", (self.dirs["paper"] / "精读笔记.html").read_text(encoding="utf-8"))
        self.assertIn("data:image/png;base64,", self.client.get("/api/papers/paper/export").get_data(as_text=True))
        self.assertEqual((self.dirs["site"] / "notes.json").read_bytes(), before)

    def test_invalid_merge_conflict_edit_and_settings_protection(self):
        for body in ({"slugs": ["paper"]}, {"slugs": ["paper", "paper"]}, {"slugs": ["paper", "missing"]},
                     {"slugs": ["paper", "site"], "primary_slug": "other"}):
            self.assertEqual(self.client.post("/api/work-groups", json=body).status_code, 400)
        group = self.merge()
        self.assertEqual(self.client.post("/api/work-groups", json={"slugs": ["site", "code"]}).status_code, 409)
        self.assertEqual(self.client.put("/api/work-groups/" + group["id"], json={"title": "New work", "slugs": ["paper", "code"], "primary_slug": "code"}).status_code, 200)
        self.assertIsNone(self.client.get("/api/papers/site").get_json()["work_group"])
        self.assertEqual(self.client.get("/api/papers/code").get_json()["work_group"]["primary_slug"], "code")
        self.client.post("/api/settings", json={"work_groups": []})
        self.assertEqual(len(server.settings()["work_groups"]), 1)

    def test_trash_whole_work_and_restore_in_one_step(self):
        group = self.merge(["paper", "site", "code"])
        before = self.all_files()
        self.assertEqual(self.client.post(f"/api/work-groups/{group['id']}/trash").status_code, 200)
        self.assertEqual([p["slug"] for p in self.client.get("/api/papers").get_json()["papers"]], ["other"])
        items = self.client.get("/api/trash").get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["kind"], "work")
        self.assertEqual(len(items[0]["paths"]), 3)
        self.assertEqual(self.client.post(f"/api/trash/{items[0]['id']}/restore").status_code, 200)
        self.assertEqual(len(self.client.get("/api/papers/paper").get_json()["work_group"]["members"]), 3)
        self.assertEqual(self.all_files(), before)

    def test_reimport_one_member_of_recycled_work_keeps_others_recycled(self):
        group = self.merge()
        self.client.post(f"/api/work-groups/{group['id']}/trash")
        server.register_extra({"dest": str(self.dirs["site"])})
        self.assertEqual(self.client.get("/api/papers/site").status_code, 200)
        self.assertEqual(self.client.get("/api/papers/paper").status_code, 404)
        remaining = self.client.get("/api/trash").get_json()["items"][0]
        self.assertEqual(remaining["paths"], [str(self.dirs["paper"])])
        self.client.post(f"/api/trash/{remaining['id']}/restore")
        self.assertEqual(len(self.client.get("/api/papers/paper").get_json()["work_group"]["members"]), 2)

    def test_recycled_member_is_not_available_for_shared_tools(self):
        group = self.merge()
        item = self.client.delete("/api/papers/site").get_json()["item"]
        self.assertEqual(self.client.get("/api/papers/paper/text?path=materials/site/website.md").status_code, 400)
        view = self.client.get("/api/papers/paper").get_json()["work_group"]
        self.assertEqual(view["missing_count"], 1)
        self.assertEqual(self.client.put(f"/api/work-groups/{group['id']}", json={"title": "Renamed", "slugs": ["paper"]}).status_code, 200)
        self.client.post(f"/api/trash/{item['id']}/restore")
        self.assertEqual(self.client.get("/api/papers/paper/text?path=materials/site/website.md").status_code, 200)


if __name__ == "__main__":
    unittest.main()
