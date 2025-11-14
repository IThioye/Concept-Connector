import sqlite3, json, os
from datetime import datetime


class MemoryService:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()

    def _init_schema(self):
        cur = self.conn.cursor()
        cur.executescript(open("database/schema.sql", "r").read())
        self.conn.commit()

    def last_queries(self, session_id, limit=3):
        if session_id is None:
            return []
        cur = self.conn.cursor()
        cur.execute(
            "SELECT concept_a, concept_b FROM conversations WHERE session_id=? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        )
        rows = cur.fetchall()
        return [
            {"concept_a": row[0], "concept_b": row[1]}
            for row in rows
        ]

    def save_interaction(self, session_id, concept_a, concept_b, result_json):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO conversations(session_id, concept_a, concept_b, result_json, timestamp) VALUES(?,?,?,?,?)",
            (session_id, concept_a, concept_b, json.dumps(result_json), datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def save_feedback(self, connection_id=None, rating=None, comments=None, session_id=None):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO feedback(session_id, connection_id, rating, comments, timestamp) VALUES(?,?,?,?,?)",
            (session_id, connection_id, rating, comments, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
