import sqlite3


class ProfileService:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._ensure_columns()

    def _ensure_columns(self):
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(user_profiles)")
        columns = {row[1] for row in cur.fetchall()}

        additions = []
        if "education_level" not in columns:
            additions.append(("education_level", "TEXT"))
        if "education_system" not in columns:
            additions.append(("education_system", "TEXT"))
        if "concept_a_knowledge" not in columns:
            additions.append(("concept_a_knowledge", "INTEGER"))
        if "concept_b_knowledge" not in columns:
            additions.append(("concept_b_knowledge", "INTEGER"))

        for column, col_type in additions:
            cur.execute(f"ALTER TABLE user_profiles ADD COLUMN {column} {col_type}")

        if additions:
            self.conn.commit()

    def get_profile(self, session_id):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT knowledge_level, preferred_examples, education_level, education_system, "
            "concept_a_knowledge, concept_b_knowledge FROM user_profiles WHERE session_id=?",
            (session_id,),
        )
        row = cur.fetchone()
        return {
            "session_id": session_id,
            "knowledge_level": (row[0] if row and row[0] else "intermediate"),
            "preferred_examples": (row[1] if row else None),
            "education_level": (row[2] if row and row[2] else None),
            "education_system": (row[3] if row and row[3] else None),
            "concept_a_knowledge": (row[4] if row and row[4] is not None else 0),
            "concept_b_knowledge": (row[5] if row and row[5] is not None else 0),
        }

    def upsert_profile(self, data):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO user_profiles(
                session_id,
                knowledge_level,
                preferred_examples,
                education_level,
                education_system,
                concept_a_knowledge,
                concept_b_knowledge
            ) VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
                knowledge_level=excluded.knowledge_level,
                preferred_examples=excluded.preferred_examples,
                education_level=excluded.education_level,
                education_system=excluded.education_system,
                concept_a_knowledge=excluded.concept_a_knowledge,
                concept_b_knowledge=excluded.concept_b_knowledge
            """,
            (
                data.get("session_id"),
                data.get("knowledge_level", "intermediate"),
                data.get("preferred_examples"),
                data.get("education_level"),
                data.get("education_system"),
                int(data.get("concept_a_knowledge", 0) or 0),
                int(data.get("concept_b_knowledge", 0) or 0),
            ),
        )
        self.conn.commit()
