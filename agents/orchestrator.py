import asyncio
import copy
import time
from collections import OrderedDict, deque
from typing import Any, Dict, Optional, Tuple
from datetime import datetime
from enum import Enum

from agents.connection_finder import ConnectionFinder
from agents.explanation_builder import ExplanationBuilder
from agents.bias_monitor import BiasMonitor
from agents.content_reviewer import ContentReviewer
from agents.fairness_auditor import FairnessAuditor
from agents.feedback_adapter import FeedbackAdapter


class RetryStrategy(Enum):
    """Different approaches for regenerating content on failure."""
    EMPHASIS = "emphasis"           # First retry: emphasize issues strongly
    SIMPLIFICATION = "simplification"  # Second retry: simplify language
    RESTRUCTURE = "restructure"     # Third retry: complete restructure


class MetricsCollector:
    """Collect operational metrics for monitoring and optimization."""
    
    def __init__(self):
        self.retry_counts = []
        self.stage_durations = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self.mitigation_success_rate = []
        self.agent_failures = {
            'connection_finder': 0,
            'explanation_builder': 0,
            'bias_monitor': 0,
            'content_reviewer': 0
        }
    
    def record_retry(self, count: int, succeeded: bool):
        """Record a retry attempt."""
        self.retry_counts.append(count)
        self.mitigation_success_rate.append(1 if succeeded else 0)
    
    def record_cache_hit(self):
        self.cache_hits += 1
    
    def record_cache_miss(self):
        self.cache_misses += 1
    
    def record_stage_duration(self, stage: str, duration: float):
        if stage not in self.stage_durations:
            self.stage_durations[stage] = []
        self.stage_durations[stage].append(duration)
    
    def record_agent_failure(self, agent_name: str):
        if agent_name in self.agent_failures:
            self.agent_failures[agent_name] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            'cache_hit_rate': round(
                self.cache_hits / (self.cache_hits + self.cache_misses), 2
            ) if (self.cache_hits + self.cache_misses) > 0 else 0,
            'avg_retries': round(
                sum(self.retry_counts) / len(self.retry_counts), 2
            ) if self.retry_counts else 0,
            'mitigation_success_rate': round(
                sum(self.mitigation_success_rate) / len(self.mitigation_success_rate), 2
            ) if self.mitigation_success_rate else 0,
            'avg_stage_durations': {
                stage: round(sum(durations) / len(durations), 2)
                for stage, durations in self.stage_durations.items()
            },
            'agent_failures': self.agent_failures.copy()
        }


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, max_requests: int = 10, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
    
    async def acquire(self):
        """Wait if rate limit would be exceeded."""
        now = time.time()
        
        # Remove old requests outside the time window
        while self.requests and self.requests[0] < now - self.time_window:
            self.requests.popleft()
        
        # If at limit, wait until oldest request expires
        if len(self.requests) >= self.max_requests:
            sleep_time = self.time_window - (now - self.requests[0])
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
                return await self.acquire()  # Recursive call after waiting
        
        self.requests.append(now)


class _LRUCache:
    """Simple in-memory LRU cache for expensive LLM calls."""

    def __init__(self, maxsize: int = 32):
        self.maxsize = maxsize
        self._store: "OrderedDict[Tuple[str, str, str], Dict[str, Any]]" = OrderedDict()

    def get(self, key: Tuple[str, str, str]) -> Optional[Dict[str, Any]]:
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        return copy.deepcopy(self._store[key])

    def set(self, key: Tuple[str, str, str], value: Dict[str, Any]) -> None:
        self._store[key] = copy.deepcopy(value)
        self._store.move_to_end(key)
        if len(self._store) > self.maxsize:
            self._store.popitem(last=False)


class Orchestrator:
    """Enhanced orchestrator with metrics, better retry logic, and rate limiting."""
    
    MAX_RETRIES = 2  # Increased from 1 to allow 3 total attempts

    def __init__(self, memory, profiles, cache_size: int = 32, enable_metrics: bool = True):
        self.memory = memory
        self.profiles = profiles
        self.connection_finder = ConnectionFinder()
        self.explainer = ExplanationBuilder()
        self.bias = BiasMonitor()
        self.reviewer = ContentReviewer()
        self.fairness = FairnessAuditor()
        self.feedback = FeedbackAdapter()
        self._cache = _LRUCache(maxsize=cache_size)
        
        # New additions
        self.metrics = MetricsCollector() if enable_metrics else None
        self.rate_limiter = RateLimiter(max_requests=10, time_window=60)

    async def prepare_context(self, concept_a, concept_b, level, session_id=None, profile_overrides=None):
        if session_id is None:
            history = []
            profile = {
                "knowledge_level": level,
                "education_level": None,
                "education_system": None,
                "concept_a_knowledge": 0,
                "concept_b_knowledge": 0,
            }
            feedback_rows = []
        else:
            history = await asyncio.to_thread(self.memory.last_queries, session_id, 3)
            profile = await asyncio.to_thread(self.profiles.get_profile, session_id)
            feedback_rows = await asyncio.to_thread(self.memory.recent_feedback, session_id, 5)

        if profile_overrides:
            profile = profile or {}
            profile.update({k: v for k, v in profile_overrides.items() if v is not None})

        guidance = self.feedback.summarise(feedback_rows, level)
        return {
            "history": history,
            "level": level,
            "session_id": session_id,
            "concept_a": concept_a,
            "concept_b": concept_b,
            "profile": profile,
            "feedback_guidance": guidance,
        }

    def _get_retry_strategy(self, retry_count: int) -> RetryStrategy:
        """Determine which retry strategy to use based on attempt number."""
        if retry_count == 1:
            return RetryStrategy.EMPHASIS
        elif retry_count == 2:
            return RetryStrategy.SIMPLIFICATION
        else:
            return RetryStrategy.RESTRUCTURE

    def _compose_guidance_with_strategy(
        self, 
        base_guidance: str, 
        content_review: Dict[str, Any], 
        bias_review: Dict[str, Any],
        strategy: RetryStrategy
    ) -> str:
        """Compose mitigation guidance with retry strategy applied."""
        suggestions = []
        
        # Strategy-specific prefixes
        strategy_prefixes = {
            RetryStrategy.EMPHASIS: "CRITICAL: Address the following issues with high priority. ",
            RetryStrategy.SIMPLIFICATION: "SIMPLIFY: Use simpler language and clearer structure. ",
            RetryStrategy.RESTRUCTURE: "RESTRUCTURE: Completely reorganize the explanation with a fresh approach. "
        }
        
        prefix = strategy_prefixes.get(strategy, "")
        if prefix:
            suggestions.append(prefix)
        
        if base_guidance:
            suggestions.append(base_guidance)
        
        if content_review and content_review.get("suggested_actions"):
            suggestions.append("Reviewer actions: " + ", ".join(content_review["suggested_actions"]))
        
        if bias_review and bias_review.get("raw"):
            suggestions.append("Bias adjustments: " + " | ".join(bias_review["raw"]))
        
        return " ".join(suggestions) or "Rewrite for clarity and inclusivity."

    async def _safe_generate_narrative(
        self,
        connections: Dict[str, Any],
        level: str,
        profile: Dict[str, Any],
        guidance: str,
        concept_a: str,
        concept_b: str
    ) -> Tuple[Optional[str], list]:
        """Generate narrative with error handling and fallbacks."""
        try:
            await self.rate_limiter.acquire()  # Rate limiting
            
            narrative = await self.explainer.build(
                connections,
                level,
                profile=profile,
                guidance=guidance,
                concept_a=concept_a,
                concept_b=concept_b,
            )
            
            narrative = narrative or {}
            explanations = narrative.get("explanation")
            analogies = narrative.get("analogies", [])
            
            # CRITICAL: Validate explanations
            if not explanations or not str(explanations).strip():
                if self.metrics:
                    self.metrics.record_agent_failure('explanation_builder')
                
                explanations = (
                    f"The connection between {concept_a} and {concept_b} involves shared principles "
                    f"that bridge these concepts through their underlying mechanisms."
                )
            
            return explanations, analogies
            
        except Exception as e:
            if self.metrics:
                self.metrics.record_agent_failure('explanation_builder')
            
            # Fallback explanation
            return (
                f"Unable to generate detailed explanation at this time. "
                f"{concept_a} and {concept_b} are related through conceptual bridges.",
                []
            )

    async def process_query_async(self, concept_a, concept_b, level, session_id=None, profile_overrides=None):
        level_key = level.lower() if isinstance(level, str) else str(level).lower()
        cache_key = (concept_a.lower(), concept_b.lower(), level_key)
        
        # Check cache
        cached = self._cache.get(cache_key)
        if cached:
            if self.metrics:
                self.metrics.record_cache_hit()
            await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, cached)
            return cached
        
        if self.metrics:
            self.metrics.record_cache_miss()

        timeline = []

        # Context preparation
        start = time.perf_counter()
        ctx = await self.prepare_context(concept_a, concept_b, level, session_id, profile_overrides=profile_overrides)
        duration = time.perf_counter() - start
        timeline.append({
            "stage": "context",
            "duration": round(duration, 3),
            "detail": self._summarise_profile(ctx.get("profile"), level),
        })
        if self.metrics:
            self.metrics.record_stage_duration('context', duration)
        
        guidance = ctx.get("feedback_guidance", "")
        
        # Connection finding
        start = time.perf_counter()
        await self.rate_limiter.acquire()
        connections = await self.connection_finder.find(concept_a, concept_b, level, ctx)
        duration = time.perf_counter() - start
        timeline.append({
            "stage": "connection",
            "duration": round(duration, 3),
            "detail": self._summarise_connection(connections, concept_a, concept_b),
        })
        if self.metrics:
            self.metrics.record_stage_duration('connection', duration)

        # Initial narrative generation
        profile = ctx.get("profile") or {}
        start = time.perf_counter()
        explanations, analogies = await self._safe_generate_narrative(
            connections, level, profile, guidance, concept_a, concept_b
        )
        duration = time.perf_counter() - start
        timeline.append({
            "stage": "narrative",
            "duration": round(duration, 3),
            "detail": self._summarise_narrative(len(analogies)),
        })
        if self.metrics:
            self.metrics.record_stage_duration('narrative', duration)

        bundle = {
            'connections': connections,
            'explanations': explanations,
            'analogies': analogies
        }

        # Parallel review
        start = time.perf_counter()
        bias_review_task = self.bias.review(bundle)
        content_review_task = self.reviewer.evaluate(
            bundle,
            level=level,
            profile=profile,
            concept_a=concept_a,
            concept_b=concept_b,
        )
        
        bias_review, content_review = await asyncio.gather(bias_review_task, content_review_task)
        
        fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)
        duration = time.perf_counter() - start
        timeline.append({
            "stage": "review",
            "duration": round(duration, 3),
            "detail": self._summarise_review(content_review, bias_review),
        })
        if self.metrics:
            self.metrics.record_stage_duration('review', duration)

        # Mitigation loop
        mitigation_triggered = bias_review.get("has_bias") or not content_review.get("level_alignment", True)
        mitigation_guidance = ""
        retry_count = 0
        
        while mitigation_triggered:
            if retry_count >= self.MAX_RETRIES:
                timeline.append({
                    "stage": "mitigation_aborted",
                    "duration": 0.0,
                    "detail": f"Mitigation aborted after {self.MAX_RETRIES} retries. Content remains unaligned or biased.",
                })
                if self.metrics:
                    self.metrics.record_retry(retry_count, False)
                break
            
            retry_count += 1
            strategy = self._get_retry_strategy(retry_count)
            
            mitigation_guidance = self._compose_guidance_with_strategy(
                guidance, content_review, bias_review, strategy
            )
            
            # Regenerate with strategy
            start = time.perf_counter()
            explanations, analogies = await self._safe_generate_narrative(
                connections, level, profile, mitigation_guidance, concept_a, concept_b
            )
            duration = time.perf_counter() - start
            timeline.append({
                "stage": "narrative",
                "duration": round(duration, 3),
                "detail": f"Regenerated explanation (Retry {retry_count}/{self.MAX_RETRIES}, strategy: {strategy.value})",
            })
            
            bundle = {
                'connections': connections,
                'explanations': explanations,
                'analogies': analogies
            }
            
            # Re-review
            start = time.perf_counter()
            bias_review_task = self.bias.review(bundle)
            content_review_task = self.reviewer.evaluate(
                bundle,
                level=level,
                profile=profile,
                concept_a=concept_a,
                concept_b=concept_b,
            )
            
            bias_review, content_review = await asyncio.gather(bias_review_task, content_review_task)
            fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)
            duration = time.perf_counter() - start
            timeline.append({
                "stage": "review",
                "duration": round(duration, 3),
                "detail": self._summarise_review(content_review, bias_review, post_mitigation=True),
            })

            mitigation_triggered = bias_review.get("has_bias") or not content_review.get("level_alignment", True)
            
            # If we've succeeded, record it
            if not mitigation_triggered:
                if self.metrics:
                    self.metrics.record_retry(retry_count, True)
                break

        result = {
            "connections": connections,
            "explanations": explanations,
            "analogies": analogies,
            "bias_review": bias_review.get("raw", []),
            "bias_flag": bool(bias_review.get("has_bias")),
            "content_review": content_review,
            "fairness": fairness_metrics,
            "feedback_guidance": guidance,
            "progress": timeline,
        }

        if retry_count > 0:
            result["mitigated"] = True
            result["mitigation_guidance"] = mitigation_guidance
            result["retry_strategy_used"] = self._get_retry_strategy(retry_count).value

        await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, result)
        self._cache.set(cache_key, result)
        return result

    def process_query(self, concept_a, concept_b, level, session_id=None, profile_overrides=None):
        return asyncio.run(
            self.process_query_async(
                concept_a,
                concept_b,
                level,
                session_id=session_id,
                profile_overrides=profile_overrides,
            )
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get operational metrics summary."""
        if not self.metrics:
            return {}
        return self.metrics.get_summary()

    @staticmethod
    def _summarise_profile(profile: Optional[Dict[str, Any]], level: Any) -> str:
        if not profile:
            return f"Profile: level={level}, default preferences applied"
        return (
            f"Profile gathered: level={level}, edu={profile.get('education_level') or 'n/a'}, "
            f"system={profile.get('education_system') or 'n/a'}"
        )

    @staticmethod
    def _summarise_connection(connection: Optional[Dict[str, Any]], concept_a: str, concept_b: str) -> str:
        if not connection:
            return f"No bridge identified between {concept_a} and {concept_b}"
        path = connection.get("path") if isinstance(connection, dict) else connection
        if isinstance(path, list):
            return f"Mapped {len(path)} concepts linking {concept_a} ↔ {concept_b}"
        return "Connection generated"

    @staticmethod
    def _summarise_narrative(analogy_count: int) -> str:
        return f"Produced explanation with {analogy_count} analogies"

    @staticmethod
    def _summarise_review(content_review: Dict[str, Any], bias_review: Dict[str, Any], *, post_mitigation: bool = False) -> str:
        status = "post-mitigation" if post_mitigation else "initial"
        alignment = "aligned" if content_review.get("level_alignment", True) else "needs adjustment"
        bias_status = "bias flagged" if bias_review.get("has_bias") else "no bias issues"
        return f"{status} review: {alignment}, {bias_status}"