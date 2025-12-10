# tests/test_orchestrator.py
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from agents.orchestrator import Orchestrator, MetricsCollector, RateLimiter, RetryStrategy


class MockMemory:
    def last_queries(self, session_id, limit):
        return []
    
    def save_interaction(self, session_id, concept_a, concept_b, result):
        pass
    
    def recent_feedback(self, session_id, limit):
        return []


class MockProfiles:
    def get_profile(self, session_id):
        return {
            "knowledge_level": "intermediate",
            "education_level": None,
            "education_system": None,
            "concept_a_knowledge": 0,
            "concept_b_knowledge": 0,
        }


@pytest.fixture
def orchestrator():
    memory = MockMemory()
    profiles = MockProfiles()
    return Orchestrator(memory=memory, profiles=profiles, enable_metrics=True)


@pytest.mark.asyncio
async def test_cache_hit(orchestrator):
    """Test that cache returns previously computed results."""
    # First call - cache miss
    with patch.object(orchestrator.connection_finder, 'find', new_callable=AsyncMock) as mock_find, \
         patch.object(orchestrator.explainer, 'build', new_callable=AsyncMock) as mock_build, \
         patch.object(orchestrator.bias, 'review', new_callable=AsyncMock) as mock_bias, \
         patch.object(orchestrator.reviewer, 'evaluate', new_callable=AsyncMock) as mock_review:
        
        mock_find.return_value = {"path": ["A", "B"], "disciplines": ["cs", "math"], "strength": 0.9}
        mock_build.return_value = {"explanation": "Test explanation", "analogies": ["analogy1"]}
        mock_bias.return_value = {"has_bias": False, "raw": []}
        mock_review.return_value = {"level_alignment": True, "issues": []}
        
        result1 = await orchestrator.process_query_async("A", "B", "intermediate")
        
        assert mock_find.call_count == 1
        assert orchestrator.metrics.cache_misses == 1
        assert orchestrator.metrics.cache_hits == 0
    
    # Second call with same params - cache hit
    result2 = await orchestrator.process_query_async("A", "B", "intermediate")
    
    assert result1 == result2
    assert orchestrator.metrics.cache_hits == 1
    # Connection finder should not be called again
    assert mock_find.call_count == 1


@pytest.mark.asyncio
async def test_retry_logic_with_strategies(orchestrator):
    """Test that retry logic uses different strategies."""
    with patch.object(orchestrator.connection_finder, 'find', new_callable=AsyncMock) as mock_find, \
         patch.object(orchestrator.explainer, 'build', new_callable=AsyncMock) as mock_build, \
         patch.object(orchestrator.bias, 'review', new_callable=AsyncMock) as mock_bias, \
         patch.object(orchestrator.reviewer, 'evaluate', new_callable=AsyncMock) as mock_review:
        
        mock_find.return_value = {"path": ["A", "B"], "disciplines": ["cs", "math"], "strength": 0.9}
        mock_build.return_value = {"explanation": "Test explanation", "analogies": ["analogy1"]}
        
        # First review: fail, second: fail, third: pass
        mock_bias.side_effect = [
            {"has_bias": True, "raw": ["Issue 1"]},
            {"has_bias": True, "raw": ["Issue 2"]},
            {"has_bias": False, "raw": []}
        ]
        mock_review.return_value = {"level_alignment": True, "issues": []}
        
        result = await orchestrator.process_query_async("A", "B", "intermediate", session_id="test")
        
        # Should have retried twice
        assert mock_bias.call_count == 3
        assert mock_build.call_count == 3
        assert result.get('mitigated') == True
        assert result.get('retry_strategy_used') == 'simplification'


@pytest.mark.asyncio
async def test_max_retries_abort(orchestrator):
    """Test that mitigation aborts after MAX_RETRIES."""
    with patch.object(orchestrator.connection_finder, 'find', new_callable=AsyncMock) as mock_find, \
         patch.object(orchestrator.explainer, 'build', new_callable=AsyncMock) as mock_build, \
         patch.object(orchestrator.bias, 'review', new_callable=AsyncMock) as mock_bias, \
         patch.object(orchestrator.reviewer, 'evaluate', new_callable=AsyncMock) as mock_review:
        
        mock_find.return_value = {"path": ["A", "B"], "disciplines": ["cs", "math"], "strength": 0.9}
        mock_build.return_value = {"explanation": "Test explanation", "analogies": ["analogy1"]}
        
        # Always fail
        mock_bias.return_value = {"has_bias": True, "raw": ["Persistent issue"]}
        mock_review.return_value = {"level_alignment": True, "issues": []}
        
        result = await orchestrator.process_query_async("A", "B", "intermediate", session_id="test")
        
        # Should try: initial + MAX_RETRIES attempts
        expected_attempts = 1 + orchestrator.MAX_RETRIES
        assert mock_bias.call_count == expected_attempts
        
        # Should still have bias flag
        assert result.get('bias_flag') == True
        
        # Check timeline for abort message
        timeline = result.get('progress', [])
        abort_stages = [s for s in timeline if s.get('stage') == 'mitigation_aborted']
        assert len(abort_stages) == 1


@pytest.mark.asyncio
async def test_safe_narrative_generation_fallback(orchestrator):
    """Test that narrative generation has proper fallbacks."""
    with patch.object(orchestrator.connection_finder, 'find', new_callable=AsyncMock) as mock_find, \
         patch.object(orchestrator.explainer, 'build', new_callable=AsyncMock) as mock_build, \
         patch.object(orchestrator.bias, 'review', new_callable=AsyncMock) as mock_bias, \
         patch.object(orchestrator.reviewer, 'evaluate', new_callable=AsyncMock) as mock_review:
        
        mock_find.return_value = {"path": ["A", "B"], "disciplines": ["cs", "math"], "strength": 0.9}
        
        # Explanation builder returns None (simulating failure)
        mock_build.return_value = None
        
        mock_bias.return_value = {"has_bias": False, "raw": []}
        mock_review.return_value = {"level_alignment": True, "issues": []}
        
        result = await orchestrator.process_query_async("A", "B", "intermediate", session_id="test")
        
        # Should have fallback explanation
        assert result.get('explanations') is not None
        assert "unable to generate" in result.get('explanations').lower()


def test_metrics_collector():
    """Test metrics collection and aggregation."""
    metrics = MetricsCollector()
    
    # Record some data
    metrics.record_cache_hit()
    metrics.record_cache_hit()
    metrics.record_cache_miss()
    
    metrics.record_retry(1, True)
    metrics.record_retry(2, False)
    
    metrics.record_stage_duration('connection', 1.5)
    metrics.record_stage_duration('connection', 2.0)
    metrics.record_stage_duration('narrative', 3.2)
    
    metrics.record_agent_failure('bias_monitor')
    
    summary = metrics.get_summary()
    
    # Verify calculations
    assert summary['cache_hit_rate'] == 0.67  # 2/3
    assert summary['avg_retries'] == 1.5  # (1+2)/2
    assert summary['mitigation_success_rate'] == 0.5  # 1/2
    assert summary['avg_stage_durations']['connection'] == 1.75  # (1.5+2.0)/2
    assert summary['avg_stage_durations']['narrative'] == 3.2
    assert summary['agent_failures']['bias_monitor'] == 1


@pytest.mark.asyncio
async def test_rate_limiter():
    """Test rate limiting functionality."""
    limiter = RateLimiter(max_requests=3, time_window=1)
    
    # Should allow first 3 requests immediately
    start = asyncio.get_event_loop().time()
    await limiter.acquire()
    await limiter.acquire()
    await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert elapsed < 0.1  # Should be nearly instant
    
    # 4th request should be delayed
    start = asyncio.get_event_loop().time()
    await limiter.acquire()
    elapsed = asyncio.get_event_loop().time() - start
    
    assert elapsed >= 1.0  # Should wait for window to clear


def test_retry_strategy_selection(orchestrator):
    """Test that correct retry strategies are selected."""
    assert orchestrator._get_retry_strategy(1) == RetryStrategy.EMPHASIS
    assert orchestrator._get_retry_strategy(2) == RetryStrategy.SIMPLIFICATION
    assert orchestrator._get_retry_strategy(3) == RetryStrategy.RESTRUCTURE


@pytest.mark.asyncio
async def test_prepare_context_with_overrides(orchestrator):
    """Test that profile overrides are applied correctly."""
    ctx = await orchestrator.prepare_context(
        "A", "B", "advanced",
        session_id="test",
        profile_overrides={
            "education_level": "PhD",
            "concept_a_knowledge": 5
        }
    )
    
    assert ctx['profile']['education_level'] == "PhD"
    assert ctx['profile']['concept_a_knowledge'] == 5
    assert ctx['level'] == "advanced"


