import sqlite3
import json
import os
from datetime import datetime
from contextlib import contextmanager
from threading import Lock
from typing import Optional, List, Dict, Any


class ConnectionPool:
    """Simple connection pool for SQLite to handle concurrent access."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = []
        self._lock = Lock()
        self._in_use = set()
        
        # Pre-create connections
        for _ in range(pool_size):
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            self._pool.append(conn)
    
    def acquire(self) -> sqlite3.Connection:
        """Get a connection from the pool."""
        with self._lock:
            if not self._pool:
                # If pool is empty, create a new connection temporarily
                conn = sqlite3.connect(self.db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                self._in_use.add(conn)
                return conn
            
            conn = self._pool.pop()
            self._in_use.add(conn)
            return conn
    
    def release(self, conn: sqlite3.Connection):
        """Return a connection to the pool."""
        with self._lock:
            if conn in self._in_use:
                self._in_use.remove(conn)
                
                if len(self._pool) < self.pool_size:
                    self._pool.append(conn)
                else:
                    # Close excess connections
                    conn.close()
    
    def close_all(self):
        """Close all connections in the pool."""
        with self._lock:
            for conn in self._pool:
                conn.close()
            for conn in self._in_use:
                conn.close()
            self._pool.clear()
            self._in_use.clear()


class MemoryService:
    """Enhanced memory service with connection pooling and better error handling."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self.pool = ConnectionPool(db_path, pool_size)
        self._init_schema()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for acquiring and releasing connections."""
        conn = self.pool.acquire()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            self.pool.release(conn)
    
    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Read and execute schema
            schema_path = os.path.join(os.path.dirname(self.db_path), '..', 'database', 'schema.sql')
            if os.path.exists(schema_path):
                cur.executescript(open(schema_path, 'r').read())
            else:
                # Fallback inline schema if file not found
                cur.executescript("""
                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        concept_a TEXT NOT NULL,
                        concept_b TEXT NOT NULL,
                        result_json TEXT,
                        timestamp TEXT NOT NULL
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_conversations_session 
                    ON conversations(session_id, timestamp DESC);
                    
                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT,
                        connection_id TEXT,
                        rating INTEGER,
                        comments TEXT,
                        timestamp TEXT NOT NULL
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_feedback_session 
                    ON feedback(session_id, timestamp DESC);
                    
                    CREATE TABLE IF NOT EXISTS user_profiles (
                        session_id TEXT PRIMARY KEY,
                        knowledge_level TEXT,
                        preferred_examples TEXT,
                        education_level TEXT,
                        education_system TEXT,
                        concept_a_knowledge INTEGER,
                        concept_b_knowledge INTEGER
                    );
                """)
    
    def last_queries(self, session_id: str, limit: int = 3) -> List[Dict[str, str]]:
        """Get recent queries for a session."""
        if not session_id:
            return []
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT concept_a, concept_b 
                FROM conversations 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit)
            )
            rows = cur.fetchall()
            return [{"concept_a": row[0], "concept_b": row[1]} for row in rows]
    
    def save_interaction(
        self, 
        session_id: Optional[str], 
        concept_a: str, 
        concept_b: str, 
        result_json: Dict[str, Any]
    ) -> int:
        """Save an interaction and return the inserted row ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO conversations(session_id, concept_a, concept_b, result_json, timestamp) 
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    concept_a,
                    concept_b,
                    json.dumps(result_json),
                    datetime.utcnow().isoformat()
                )
            )
            return cur.lastrowid
    
    def save_feedback(
        self,
        connection_id: Optional[str] = None,
        rating: Optional[int] = None,
        comments: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """Save user feedback and return the inserted row ID."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO feedback(session_id, connection_id, rating, comments, timestamp) 
                VALUES(?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    connection_id,
                    rating,
                    comments,
                    datetime.utcnow().isoformat()
                )
            )
            return cur.lastrowid
    
    def recent_feedback(self, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent feedback for a session."""
        if not session_id:
            return []
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT rating, comments 
                FROM feedback 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit)
            )
            rows = cur.fetchall()
            return [
                {"rating": row[0], "comments": row[1]}
                for row in rows
                if row[0] is not None or (row[1] and row[1].strip())
            ]
    
    def recent_results(self, session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent results with fairness metrics for a session."""
        if not session_id:
            return []
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT concept_a, concept_b, result_json, timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit)
            )
            
            rows = cur.fetchall()
            results = []
            
            for row in rows:
                concept_a, concept_b, result_json_str, timestamp = row
                
                try:
                    payload = json.loads(result_json_str) if result_json_str else {}
                except json.JSONDecodeError:
                    payload = {}
                
                results.append({
                    "timestamp": timestamp,
                    "concept_a": concept_a,
                    "concept_b": concept_b,
                    "bias_review": payload.get("bias_review", []),
                    "bias_flag": bool(payload.get("bias_flag")),
                    "fairness": payload.get("fairness"),
                })
            
            return results
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get aggregate statistics for a session."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Query count
            cur.execute(
                "SELECT COUNT(*) FROM conversations WHERE session_id = ?",
                (session_id,)
            )
            query_count = cur.fetchone()[0]
            
            # Feedback stats
            cur.execute(
                """
                SELECT 
                    COUNT(*) as feedback_count,
                    AVG(rating) as avg_rating,
                    MIN(rating) as min_rating,
                    MAX(rating) as max_rating
                FROM feedback 
                WHERE session_id = ? AND rating IS NOT NULL
                """,
                (session_id,)
            )
            feedback_row = cur.fetchone()
            
            return {
                "query_count": query_count,
                "feedback_count": feedback_row[0] or 0,
                "avg_rating": round(feedback_row[1], 2) if feedback_row[1] else None,
                "min_rating": feedback_row[2],
                "max_rating": feedback_row[3],
            }
    
    def search_interactions(
        self,
        session_id: Optional[str] = None,
        concept_search: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search interactions by session or concept keywords."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            query = "SELECT id, session_id, concept_a, concept_b, timestamp FROM conversations WHERE 1=1"
            params = []
            
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            
            if concept_search:
                query += " AND (concept_a LIKE ? OR concept_b LIKE ?)"
                search_term = f"%{concept_search}%"
                params.extend([search_term, search_term])
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cur.execute(query, params)
            rows = cur.fetchall()
            
            return [
                {
                    "id": row[0],
                    "session_id": row[1],
                    "concept_a": row[2],
                    "concept_b": row[3],
                    "timestamp": row[4],
                }
                for row in rows
            ]
    
    def cleanup_old_sessions(self, days_old: int = 90) -> int:
        """Delete sessions older than specified days. Returns count of deleted rows."""
        from datetime import timedelta
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days_old)).isoformat()
        
        with self._get_connection() as conn:
            cur = conn.cursor()
            
            # Delete old conversations
            cur.execute(
                "DELETE FROM conversations WHERE timestamp < ?",
                (cutoff_date,)
            )
            conversations_deleted = cur.rowcount
            
            # Delete old feedback
            cur.execute(
                "DELETE FROM feedback WHERE timestamp < ?",
                (cutoff_date,)
            )
            feedback_deleted = cur.rowcount
            
            return conversations_deleted + feedback_deleted
    
    def close(self):
        """Close all connections in the pool."""
        self.pool.close_all()
    
    def __del__(self):
        """Ensure connections are closed on deletion."""
        try:
            self.close()
        except:
            pass