PRAGMA journal_mode=WAL;


CREATE TABLE IF NOT EXISTS conversations (
id INTEGER PRIMARY KEY,
session_id TEXT,
concept_a TEXT,
concept_b TEXT,
result_json TEXT,
timestamp TEXT
);


CREATE TABLE IF NOT EXISTS user_profiles (
id INTEGER PRIMARY KEY,
session_id TEXT UNIQUE,
knowledge_level TEXT,
preferred_examples TEXT
);


CREATE TABLE IF NOT EXISTS feedback (
id INTEGER PRIMARY KEY,
session_id TEXT,
connection_id TEXT,
rating INTEGER,
comments TEXT,
timestamp TEXT
);