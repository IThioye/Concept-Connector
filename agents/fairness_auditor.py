from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Iterable, List


class FairnessAuditor:
    """Compute lightweight, explainable fairness metrics for generated artefacts."""

    @staticmethod
    def _discipline_diversity(connection: Dict[str, Any]) -> Dict[str, Any]:
        disciplines: Iterable[str] = connection.get("disciplines", []) if isinstance(connection, dict) else []
        disciplines = [d.lower() for d in disciplines if isinstance(d, str) and d]
        total = len(list(disciplines))
        distinct = len(set(disciplines))
        value = round(distinct / total, 2) if total else 0.0
        return {
            "label": "Discipline diversity",
            "value": value,
            "detail": f"{distinct} unique disciplines across {total} steps" if total else "No disciplines supplied",
        }

    @staticmethod
    def _language_accessibility(explanations: Any) -> Dict[str, Any]:
        if not explanations:
            return {
                "label": "Language accessibility",
                "value": 0.0,
                "detail": "No explanation text available",
            }

        if isinstance(explanations, list):
            text = " ".join(explanations)
        else:
            text = str(explanations)

        words = [w.strip(".,;:!?()").lower() for w in text.split() if w]
        if not words:
            return {
                "label": "Language accessibility",
                "value": 0.0,
                "detail": "Explanation was empty",
            }

        short_words = sum(1 for w in words if len(w) <= 6)
        ratio = round(short_words / len(words), 2)
        detail = f"{short_words}/{len(words)} words are short (<=6 chars)"
        return {
            "label": "Language accessibility",
            "value": ratio,
            "detail": detail,
        }

    @staticmethod
    def _analogy_variety(analogies: Any) -> Dict[str, Any]:
        if not analogies:
            return {
                "label": "Analogy variety",
                "value": 0.0,
                "detail": "No analogies generated",
            }

        if isinstance(analogies, str):
            lines = [line.strip("- ") for line in analogies.splitlines() if line.strip()]
        else:
            lines = [str(item).strip("- ") for item in analogies if item]

        if not lines:
            return {
                "label": "Analogy variety",
                "value": 0.0,
                "detail": "No analogies generated",
            }

        starters = [line.split()[0].lower() for line in lines if line.split()]
        counts = Counter(starters)
        unique = len(counts)
        variety = round(unique / len(lines), 2)
        detail = f"{unique} unique starting metaphors across {len(lines)} analogies"
        return {
            "label": "Analogy variety",
            "value": variety,
            "detail": detail,
        }

    def evaluate(self, connection: Dict[str, Any], explanations: Any, analogies: Any) -> Dict[str, Any]:
        base_connection = connection
        if isinstance(connection, list) and connection:
            base_connection = connection[0]
        elif not isinstance(connection, dict):
            base_connection = {}

        metrics: List[Dict[str, Any]] = [
            self._discipline_diversity(base_connection or {}),
            self._language_accessibility(explanations),
            self._analogy_variety(analogies),
        ]

        valid_values = [m["value"] for m in metrics if isinstance(m.get("value"), (int, float))]
        overall = round(sum(valid_values) / len(valid_values), 2) if valid_values else 0.0

        return {
            "overall": overall,
            "metrics": metrics,
        }
