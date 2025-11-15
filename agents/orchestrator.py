import asyncio
import asyncio
import copy
import time
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from agents.connection_finder import ConnectionFinder
from agents.explanation_builder import ExplanationBuilder
from agents.bias_monitor import BiasMonitor
from agents.content_reviewer import ContentReviewer
from agents.fairness_auditor import FairnessAuditor
from agents.feedback_adapter import FeedbackAdapter


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
    def __init__(self, memory, profiles, cache_size: int = 32):
        self.memory = memory
        self.profiles = profiles
        self.connection_finder = ConnectionFinder()
        self.explainer = ExplanationBuilder()
        self.bias = BiasMonitor()
        self.reviewer = ContentReviewer()
        self.fairness = FairnessAuditor()
        self.feedback = FeedbackAdapter()
        self._cache = _LRUCache(maxsize=cache_size)

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

    async def process_query_async(self, concept_a, concept_b, level, session_id=None, profile_overrides=None):
        cache_key = (concept_a.lower(), concept_b.lower(), level.lower() if isinstance(level, str) else level)
        cached = self._cache.get(cache_key)
        if cached:
            await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, cached)
            return cached

        timeline = []

        start = time.perf_counter()
        ctx = await self.prepare_context(concept_a, concept_b, level, session_id, profile_overrides=profile_overrides)
        timeline.append(
            {
                "stage": "context",
                "duration": round(time.perf_counter() - start, 3),
                "detail": self._summarise_profile(ctx.get("profile"), level),
            }
        )
        guidance = ctx.get("feedback_guidance", "")
        start = time.perf_counter()
        connections = await self.connection_finder.find(concept_a, concept_b, level, ctx)
        timeline.append(
            {
                "stage": "connection",
                "duration": round(time.perf_counter() - start, 3),
                "detail": self._summarise_connection(connections, concept_a, concept_b),
            }
        )

        profile = ctx.get("profile") or {}
        start = time.perf_counter()
        narrative = await self.explainer.build(
            connections,
            level,
            profile=profile,
            guidance=guidance,
            concept_a=concept_a,
            concept_b=concept_b,
        )
        explanations = narrative.get("explanation")
        analogies = narrative.get("analogies", [])
        timeline.append(
            {
                "stage": "narrative",
                "duration": round(time.perf_counter() - start, 3),
                "detail": self._summarise_narrative(len(analogies)),
            }
        )

        bundle = {
            'connections': connections,
            'explanations': explanations,
            'analogies': analogies
        }

        start = time.perf_counter()
        bias_review = await self.bias.review(bundle)
        content_review = await self.reviewer.evaluate(
            bundle,
            level=level,
            profile=profile,
            concept_a=concept_a,
            concept_b=concept_b,
        )
        fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)
        timeline.append(
            {
                "stage": "review",
                "duration": round(time.perf_counter() - start, 3),
                "detail": self._summarise_review(content_review, bias_review),
            }
        )

        mitigation_triggered = bias_review.get("has_bias") or not content_review.get("level_alignment", True)
        mitigation_guidance = ""
        if mitigation_triggered:
            mitigation_guidance = self._compose_guidance(guidance, content_review, bias_review)
            start = time.perf_counter()
            narrative = await self.explainer.build(
                connections,
                level,
                profile=profile,
                guidance=mitigation_guidance,
                concept_a=concept_a,
                concept_b=concept_b,
            )
            explanations = narrative.get("explanation")
            analogies = narrative.get("analogies", [])
            timeline.append(
                {
                    "stage": "narrative",
                    "duration": round(time.perf_counter() - start, 3),
                    "detail": "Regenerated explanation & analogies with mitigation guidance",
                }
            )
            bundle = {
                'connections': connections,
                'explanations': explanations,
                'analogies': analogies
            }
            start = time.perf_counter()
            bias_review = await self.bias.review(bundle)
            content_review = await self.reviewer.evaluate(
                bundle,
                level=level,
                profile=profile,
                concept_a=concept_a,
                concept_b=concept_b,
            )
            fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)
            timeline.append(
                {
                    "stage": "review",
                    "duration": round(time.perf_counter() - start, 3),
                    "detail": self._summarise_review(content_review, bias_review, post_mitigation=True),
                }
            )

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

        if mitigation_triggered:
            result["mitigated"] = True
            result["mitigation_guidance"] = mitigation_guidance

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

    @staticmethod
    def _compose_guidance(base_guidance: str, content_review, bias_review) -> str:
        suggestions = []
        if base_guidance:
            suggestions.append(base_guidance)
        if content_review and content_review.get("suggested_actions"):
            suggestions.append("Reviewer actions: " + ", ".join(content_review["suggested_actions"]))
        if bias_review and bias_review.get("raw"):
            suggestions.append("Bias adjustments: " + " | ".join(bias_review["raw"]))
        return " ".join(suggestions) or "Rewrite for clarity and inclusivity."

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
