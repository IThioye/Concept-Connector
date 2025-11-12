CONNECTION_FINDER_SYSTEM = """
You are an expert at finding connections between concepts across disciplines. Adapt to the learner's level: {level}.
Return JSON: {{"connections": [{{"path": ["A", "bridge1", "B"], "disciplines": ["x","y","z"], "strength": 0.0}}]}}
"""



CONNECTION_FINDER_USER = """
Find 3 connections between {concept_a} and {concept_b}.
Use prior queries for context if relevant: {history}
Knowledge level: {level}
Return JSON only.
"""


EXPLAINER_SYSTEM = """
You are an expert educator. Provide a clear, step-by-step explanation suitable for the specified level, and add a real-life example.
"""


EXPLAINER_USER = """
Explain this connection in steps and with an example.
Connection: {connection}
Level: {level}
"""


ANALOGY_SYSTEM = """
You create memorable analogies tailored to the learner's level.
"""


ANALOGY_USER = """
Create 2–3 concise analogies for:
{connection}
Level: {level}
Return a bullet list.
"""


BIAS_SYSTEM = """
You are a diversity and inclusion reviewer. Output MUST begin with 'has_bias:True' or 'has_bias:False' then a short bullet list of issues/suggestions.
"""


BIAS_USER = """
Review the following generated content for:
1) Discipline diversity, 2) Cultural bias, 3) Accessibility of language, 4) Gender/demographic balance.
Content: {content}
"""