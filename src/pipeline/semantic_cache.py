"""Persistent SQLite semantic answer cache, following the Week 10 helpers."""
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import time


class SemanticCache:
    def __init__(self, db_path="data/semantic_cache.db"):
        self.db_path = Path(db_path)

    def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("""CREATE TABLE IF NOT EXISTS query_cache (
            id TEXT PRIMARY KEY, scope TEXT NOT NULL, question TEXT NOT NULL,
            embedding_json TEXT NOT NULL, answer_json TEXT NOT NULL,
            created_ts REAL NOT NULL, hit_count INTEGER NOT NULL DEFAULT 0,
            last_hit_ts REAL)""")
        conn.execute("CREATE INDEX IF NOT EXISTS query_cache_scope ON query_cache(scope)")
        return conn

    def clear(self):
        conn = self._connect()
        try:
            with conn:
                return conn.execute("DELETE FROM query_cache").rowcount
        finally:
            conn.close()

    def lookup(self, scope, question, vector, *, threshold, ttl):
        if not self._valid_vector(vector):
            return None, None
        conn = self._connect()
        try:
            with conn:
                now = time.time()
                conn.execute("DELETE FROM query_cache WHERE created_ts <= ?", (now - ttl,))
                best, score = None, -1.0
                for row_id, embedding, answer in conn.execute(
                    "SELECT id, embedding_json, answer_json FROM query_cache WHERE scope = ?", (scope,)
                ):
                    other = json.loads(embedding)
                    if len(vector) != len(other) or not self._valid_vector(other):
                        continue
                    denominator = math.sqrt(sum(x*x for x in vector) * sum(x*x for x in other))
                    similarity = sum(a*b for a, b in zip(vector, other)) / denominator
                    if similarity >= threshold and similarity > score:
                        best, score = (row_id, answer), similarity
                if best is None:
                    return None, None
                conn.execute("UPDATE query_cache SET hit_count = hit_count + 1, last_hit_ts = ? WHERE id = ?",
                             (now, best[0]))
                return json.loads(best[1]), score
        finally:
            conn.close()

    @staticmethod
    def _valid_vector(vector):
        return bool(vector) and all(math.isfinite(x) for x in vector) and any(vector)

    def store(self, scope, question, vector, answer, *, max_entries):
        if not self._valid_vector(vector):
            return
        key = hashlib.sha256(json.dumps([scope, question.strip().lower()]).encode()).hexdigest()
        payload = answer.model_dump(mode="json") if hasattr(answer, "model_dump") else answer
        conn = self._connect()
        try:
            with conn:
                conn.execute("""INSERT OR REPLACE INTO query_cache
                    (id, scope, question, embedding_json, answer_json, created_ts)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (key, scope, question, json.dumps(vector), json.dumps(payload), time.time()))
                conn.execute("""DELETE FROM query_cache WHERE id NOT IN
                    (SELECT id FROM query_cache ORDER BY created_ts DESC, rowid DESC LIMIT ?)""",
                    (max_entries,))
        finally:
            conn.close()
