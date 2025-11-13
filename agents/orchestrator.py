from agents.connection_finder import ConnectionFinder
from agents.explanation_builder import ExplanationBuilder
from agents.analogy_generator import AnalogyGenerator
from agents.bias_monitor import BiasMonitor


class Orchestrator:
    def __init__(self, memory, profiles):
        self.memory = memory
        self.profiles = profiles
        self.connection_finder = ConnectionFinder()
        self.explainer = ExplanationBuilder()
        self.analogies = AnalogyGenerator()
        self.bias = BiasMonitor()


    def prepare_context(self, concept_a, concept_b, level, session_id=None):
        history = self.memory.last_queries(session_id, limit=3)
        return {
        "history": history,
        "level": level,
        "session_id": session_id,
        "concept_a": concept_a,
        "concept_b": concept_b,
        }


    def process_query(self, concept_a, concept_b, level, session_id=None):
        ctx = self.prepare_context(concept_a, concept_b, level, session_id)
        connections = self.connection_finder.find(concept_a, concept_b, level, ctx)

        explanations = self.explainer.build(connections, level)

        analogies = self.analogies.generate(connections if connections else None, level)


        review = self.bias.review({
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
        self.memory.save_interaction(session_id, concept_a, concept_b, result)
        return result