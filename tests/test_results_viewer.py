"""Read-only loading and viewer interaction tests using an isolated database."""

import json
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from src.eval.results_reader import read_history, read_results


class ResultsViewerTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "results #1.db"
        with closing(sqlite3.connect(self.path)) as con, con:
            con.executescript("""
                CREATE TABLE golden_runs (id INTEGER PRIMARY KEY, started_at TEXT, completed_at TEXT,
                    model TEXT, golden_path TEXT, corpus_dir TEXT, entry_limit INTEGER,
                    settings_json TEXT, judge_settings_json TEXT, summary_json TEXT);
                CREATE TABLE golden_results (id INTEGER PRIMARY KEY, run_id INTEGER, result_json TEXT);
            """)
            con.execute("INSERT INTO golden_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                1, "2026-10-11T10:00:00+00:00", "2026-10-11T10:01:00+00:00", "gpt-4o-mini",
                "golden.jsonl", "corpus", None,
                json.dumps({"rag": {"retrieval": {"top_k": 8, "rerank_enabled": False}}}), "{}",
                json.dumps({"total": 2, "passed": 1, "pass_rate": 0.5}),
            ))
            for index, passed in enumerate([False, True], 1):
                row = dict(id=f"Q00{index}", question=f"Question {index}", answer_text=f"Answer {index}",
                           expected_behavior="Supported facts", judge_reasoning="Review evidence",
                           pass_fail=passed, evaluation_type="retrieval", document="source.txt")
                con.execute("INSERT INTO golden_results VALUES (?, ?, ?)", (index, 1, json.dumps(row)))

    def test_loading_does_not_modify_database(self):
        before = self.path.read_bytes()
        history = read_history(self.path)
        self.assertEqual(history["golden_runs"][0]["settings"]["rag"]["retrieval"]["top_k"], 8)
        self.assertEqual(history["runs"], [])
        self.assertEqual(len(read_results(self.path, 1)), 2)
        self.assertEqual(read_results(self.path, 999), [])
        self.assertEqual(read_results(self.path, 1, golden=False), [])
        self.assertEqual(self.path.read_bytes(), before)
        missing = self.path.parent / "missing.db"
        with self.assertRaises(FileNotFoundError):
            read_history(missing)
        self.assertFalse(missing.exists())

    def test_filters_and_details(self):
        try:
            from streamlit.testing.v1 import AppTest
        except ImportError:
            self.skipTest("Streamlit is not installed in this environment")
        app = Path(__file__).resolve().parents[1] / "api/results_viewer.py"
        at = AppTest.from_file(str(app), default_timeout=30).run()
        at.sidebar.text_input[0].set_value(str(self.path)).run()
        self.assertFalse(at.exception)
        self.assertFalse(at.error)
        self.assertEqual(at.selectbox[1].options, ["Q001"])
        at.radio[0].set_value("All").run()
        self.assertEqual(at.selectbox[1].options, ["Q001", "Q002"])
        at.radio[0].set_value("Passed").run()
        self.assertEqual(at.selectbox[1].options, ["Q002"])
        next(widget for widget in at.text_input if widget.label.startswith("Search questions")).set_value("no matching question").run()
        self.assertFalse(at.exception)
        self.assertTrue(any("No questions match" in info.value for info in at.info))
        at.sidebar.text_input[0].set_value(str(self.path.parent / "missing.db")).run()
        self.assertFalse(at.exception)
        self.assertTrue(at.error)


if __name__ == "__main__":
    unittest.main()
