import sqlite3, json


class ProfileService:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)


    def get_profile(self, session_id):
        cur = self.conn.cursor()
        cur.execute("SELECT knowledge_level, preferred_examples FROM user_profiles WHERE session_id=?", (session_id,))
        row = cur.fetchone()
        return {"session_id": session_id, "knowledge_level": (row[0] if row else "intermediate"), "preferred_examples": (row[1] if row else None)}


def upsert_profile(self, data):
    cur = self.conn.cursor()
    cur.execute(
    "INSERT INTO user_profiles(session_id, knowledge_level, preferred_examples) VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET knowledge_level=excluded.knowledge_level, preferred_examples=excluded.preferred_examples",
    (data.get("session_id"), data.get("knowledge_level", "intermediate"), data.get("preferred_examples")),
    )
    self.conn.commit()