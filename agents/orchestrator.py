import asyncio
import copy
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from agents.connection_finder import ConnectionFinder
from agents.explanation_builder import ExplanationBuilder
from agents.analogy_generator import AnalogyGenerator
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
        self.analogies = AnalogyGenerator()
        self.bias = BiasMonitor()
        self.reviewer = ContentReviewer()
        self.fairness = FairnessAuditor()
        self.feedback = FeedbackAdapter()
        self._cache = _LRUCache(maxsize=cache_size)

    async def prepare_context(self, concept_a, concept_b, level, session_id=None):
        if session_id is None:
            history = []
            profile = {"knowledge_level": level}
            feedback_rows = []
        else:
            history = await asyncio.to_thread(self.memory.last_queries, session_id, 3)
            profile = await asyncio.to_thread(self.profiles.get_profile, session_id)
            feedback_rows = await asyncio.to_thread(self.memory.recent_feedback, session_id, 5)

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

    async def process_query_async(self, concept_a, concept_b, level, session_id=None):
        cache_key = (concept_a.lower(), concept_b.lower(), level.lower() if isinstance(level, str) else level)
        cached = self._cache.get(cache_key)
        if cached:
            await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, cached)
            return cached

        ctx = await self.prepare_context(concept_a, concept_b, level, session_id)
        guidance = ctx.get("feedback_guidance", "")
        connections = await self.connection_finder.find(concept_a, concept_b, level, ctx)

        explanations_task = asyncio.create_task(self.explainer.build(connections, level, guidance=guidance))
        analogies_task = asyncio.create_task(self.analogies.generate(connections if connections else None, level, guidance=guidance))
        explanations, analogies = await asyncio.gather(explanations_task, analogies_task)

        bundle = {
            'connections': connections,
            'explanations': explanations,
            'analogies': analogies
        }

        bias_review = await self.bias.review(bundle)
        content_review = await self.reviewer.evaluate(bundle, level=level)
        fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)

        mitigation_triggered = bias_review.get("has_bias") or not content_review.get("level_alignment", True)
        mitigation_guidance = ""
        if mitigation_triggered:
            mitigation_guidance = self._compose_guidance(guidance, content_review, bias_review)
            explanations, analogies = await asyncio.gather(
                self.explainer.build(connections, level, guidance=mitigation_guidance),
                self.analogies.generate(connections if connections else None, level, guidance=mitigation_guidance),
            )
            bundle = {
                'connections': connections,
                'explanations': explanations,
                'analogies': analogies
            }
            content_review = await self.reviewer.evaluate(bundle, level=level)
            fairness_metrics = self.fairness.evaluate(connections or {}, explanations, analogies)

        result = {
            "connections": connections,
            "explanations": explanations,
            "analogies": analogies,
            "bias_review": bias_review.get("raw", []),
            "bias_flag": bool(bias_review.get("has_bias")),
            "content_review": content_review,
            "fairness": fairness_metrics,
            "feedback_guidance": guidance,
        }

        if mitigation_triggered:
            result["mitigated"] = True
            result["mitigation_guidance"] = mitigation_guidance

        await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, result)
        self._cache.set(cache_key, result)
        return result

    def process_query(self, concept_a, concept_b, level, session_id=None):
        return asyncio.run(self.process_query_async(concept_a, concept_b, level, session_id=session_id))

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
