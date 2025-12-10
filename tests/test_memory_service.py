# tests/test_memory_service.py
import pytest
import os
import tempfile
from services.memory_service import MemoryService, ConnectionPool


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)
    os.rmdir(temp_dir)


@pytest.fixture
def memory_service(temp_db):
    """Create a memory service with temporary database."""
    service = MemoryService(db_path=temp_db, pool_size=3)
    yield service
    service.close()


def test_connection_pool_acquire_release():
    """Test connection pool acquire and release."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = os.path.join(temp_dir, "test.db")
        pool = ConnectionPool(db_path, pool_size=2)
        
        # Acquire connections
        conn1 = pool.acquire()
        conn2 = pool.acquire()
        
        assert len(pool._in_use) == 2
        assert len(pool._pool) == 0
        
        # Release one
        pool.release(conn1)
        
        assert len(pool._in_use) == 1
        assert len(pool._pool) == 1
        
        # Clean up
        pool.release(conn2)
        pool.close_all()


def test_save_and_retrieve_interaction(memory_service):
    """Test saving and retrieving interactions."""
    result = {
        "connections": {"path": ["A", "B"]},
        "explanations": "Test explanation",
        "analogies": ["analogy1"]
    }
    
    # Save interaction
    row_id = memory_service.save_interaction(
        session_id="test-session",
        concept_a="Concept A",
        concept_b="Concept B",
        result_json=result
    )
    
    assert row_id > 0
    
    # Retrieve recent results
    results = memory_service.recent_results("test-session", limit=5)
    
    assert len(results) == 1
    assert results[0]['concept_a'] == "Concept A"
    assert results[0]['concept_b'] == "Concept B"


def test_feedback_storage(memory_service):
    """Test feedback storage and retrieval."""
    # Save feedback
    feedback_id = memory_service.save_feedback(
        session_id="test-session",
        connection_id="A → B",
        rating=5,
        comments="Great explanation!"
    )
    
    assert feedback_id > 0
    
    # Retrieve feedback
    feedback = memory_service.recent_feedback("test-session", limit=5)
    
    assert len(feedback) == 1
    assert feedback[0]['rating'] == 5
    assert feedback[0]['comments'] == "Great explanation!"


def test_session_stats(memory_service):
    """Test session statistics calculation."""
    session_id = "test-session"
    
    # Add some interactions
    for i in range(3):
        memory_service.save_interaction(
            session_id=session_id,
            concept_a=f"A{i}",
            concept_b=f"B{i}",
            result_json={"test": "data"}
        )
    
    # Add some feedback
    memory_service.save_feedback(session_id=session_id, rating=5)
    memory_service.save_feedback(session_id=session_id, rating=4)
    memory_service.save_feedback(session_id=session_id, rating=3)
    
    stats = memory_service.get_session_stats(session_id)
    
    assert stats['query_count'] == 3
    assert stats['feedback_count'] == 3
    assert stats['avg_rating'] == 4.0
    assert stats['min_rating'] == 3
    assert stats['max_rating'] == 5


def test_search_interactions(memory_service):
    """Test searching interactions by concept."""
    # Add interactions
    memory_service.save_interaction("s1", "Photosynthesis", "Solar Panels", {})
    memory_service.save_interaction("s2", "Neural Networks", "Brain", {})
    memory_service.save_interaction("s3", "Photosynthesis", "Biology", {})
    
    # Search for "Photosynthesis"
    results = memory_service.search_interactions(concept_search="Photosynthesis")
    
    assert len(results) == 2
    assert all("Photosynthesis" in (r['concept_a'], r['concept_b']) for r in results)


def test_cleanup_old_sessions(memory_service):
    """Test cleanup of old sessions."""
    from datetime import datetime, timedelta
    
    # Mock old timestamp by directly inserting
    with memory_service._get_connection() as conn:
        cur = conn.cursor()
        old_timestamp = (datetime.utcnow() - timedelta(days=100)).isoformat()
        
        cur.execute(
            "INSERT INTO conversations(session_id, concept_a, concept_b, result_json, timestamp) VALUES(?,?,?,?,?)",
            ("old-session", "A", "B", "{}", old_timestamp)
        )
    
    # Add recent interaction
    memory_service.save_interaction("recent-session", "X", "Y", {})
    
    # Cleanup sessions older than 90 days
    deleted = memory_service.cleanup_old_sessions(days_old=90)
    
    assert deleted == 1
    
    # Verify old session is gone but recent one remains
    results = memory_service.search_interactions()
    assert len(results) == 1
    assert results[0]['session_id'] == "recent-session"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])