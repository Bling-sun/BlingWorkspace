import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "web"))
import history
import server


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paper = self.root / "example"
        self.paper.mkdir()
        (self.paper / "meta.json").write_text('{"title":"Example"}', encoding="utf-8")
        self.client = server.app.test_client()
        for p in (patch.object(server, "roots", return_value=(self.root, [])),
                  patch.object(server, "settings", return_value={"provider": "mock"}),
                  patch.object(server.context, "build_system", return_value="test")):
            p.start()
            self.addCleanup(p.stop)

    def talk(self, text="Question", regenerate=False):
        with patch.object(server.llm, "stream", return_value=iter([{"type": "text", "text": text + " answer"}])):
            response = self.client.post('/api/papers/example/chat', json={"text": text, "regenerate": regenerate})
            self.assertEqual(response.status_code, 200)
            return response.get_data(as_text=True)

    def test_regeneration_keeps_both_answers_and_survives_reload(self):
        self.talk("First")
        self.talk("Second", regenerate=True)
        versions = history.listing(self.paper)
        self.assertEqual(len(versions), 3)
        answers = [history.load(self.paper, x["id"])["messages"][-1]["content"] for x in versions]
        self.assertIn("First answer", answers)
        self.assertIn("Second answer", answers)
        self.assertEqual(server.load_discussion(self.paper)[-1]["content"], "Second answer")
        # API reads from disk, not process memory.
        self.assertEqual(len(self.client.get('/api/papers/example/history').get_json()["items"]), 3)

    def test_delete_and_notes_changes_are_recoverable_in_history(self):
        self.talk()
        mid = server.load_discussion(self.paper)[-1]["id"]
        self.client.delete('/api/papers/example/messages/' + mid)
        backup = next(x for x in history.listing(self.paper) if x["reason"] == "before_delete")
        self.assertEqual(history.load(self.paper, backup["id"])["messages"][-1]["id"], mid)
        self.client.put('/api/papers/example/notes', json={"sections": {"basic": "Old notes"}})
        self.client.put('/api/papers/example/notes', json={"sections": {"basic": "New notes"}})
        notes = [history.load(self.paper, x["id"])["notes"]["sections"]["basic"] for x in history.listing(self.paper)]
        self.assertIn("Old notes", notes)
        self.assertIn("New notes", notes)

    def test_legacy_discussion_migrates_once(self):
        server.save_discussion(self.paper, [{"role": "user", "content": "Earlier discussion"}])
        for _ in range(2):
            items = self.client.get('/api/papers/example/history').get_json()["items"]
            self.assertEqual(len(items), 1)
        detail = self.client.get('/api/papers/example/history/' + items[0]["id"]).get_json()
        self.assertEqual(detail["messages"][0]["content"], "Earlier discussion")
        self.assertEqual(self.client.get('/api/papers/example/history/not-a-version').status_code, 404)

    def test_stopping_stream_saves_partial_without_yielding_on_close(self):
        captured = []
        with patch.object(server.llm, "stream", return_value=iter([{"type": "text", "text": "partial"}, {"type": "text", "text": "rest"}])):
            stream = server.run_stream(self.paper, "example", [], lambda text, tools, err: captured.append((text, err)))
            next(stream)
            stream.close()
        self.assertEqual(captured[0][0], "partial")
        self.assertIn("中断", captured[0][1])

    def test_failed_atomic_write_preserves_previous_file(self):
        path = self.paper / 'discussion.json'
        history.write_json(path, {"messages": ["original"]})
        with patch.object(history.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaises(OSError):
                history.write_json(path, {"messages": ["new"]})
        self.assertEqual(json.loads(path.read_text(encoding='utf-8'))["messages"], ["original"])
        self.assertFalse(list(self.paper.glob('.saving-*')))


if __name__ == '__main__':
    unittest.main()
