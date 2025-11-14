import asyncio
import copy
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

from agents.connection_finder import ConnectionFinder
from agents.explanation_builder import ExplanationBuilder
from agents.analogy_generator import AnalogyGenerator
from agents.bias_monitor import BiasMonitor


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
        self._cache = _LRUCache(maxsize=cache_size)

    async def prepare_context(self, concept_a, concept_b, level, session_id=None):
        if session_id is None:
            history = []
        else:
            history = await asyncio.to_thread(self.memory.last_queries, session_id, 3)
        return {
            "history": history,
            "level": level,
            "session_id": session_id,
            "concept_a": concept_a,
            "concept_b": concept_b,
        }

    async def process_query_async(self, concept_a, concept_b, level, session_id=None):
        cache_key = (concept_a.lower(), concept_b.lower(), level.lower() if isinstance(level, str) else level)
        cached = self._cache.get(cache_key)
        if cached:
            await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, cached)
            return cached

        ctx = await self.prepare_context(concept_a, concept_b, level, session_id)
        connections = await self.connection_finder.find(concept_a, concept_b, level, ctx)

        explanations_task = asyncio.create_task(self.explainer.build(connections, level))
        analogies_task = asyncio.create_task(self.analogies.generate(connections if connections else None, level))
        explanations, analogies = await asyncio.gather(explanations_task, analogies_task)

        review = await self.bias.review({
            'connections': connections,
            'explanations': explanations,
            'analogies': analogies
        })

        result = {
            "connections": connections,
            "explanations": explanations,
            "analogies": analogies,
            "review": review["raw"],
        }
        await asyncio.to_thread(self.memory.save_interaction, session_id, concept_a, concept_b, result)
        self._cache.set(cache_key, result)
        return result

    def process_query(self, concept_a, concept_b, level, session_id=None):
        return asyncio.run(self.process_query_async(concept_a, concept_b, level, session_id=session_id))
