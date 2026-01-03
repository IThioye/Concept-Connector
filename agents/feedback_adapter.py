from typing import List, Optional


class FeedbackAdapter:
    """Transform stored learner feedback into lightweight guidance strings."""

    def summarise(self, feedback_rows: List[dict], default_level: str) -> str:
        if not feedback_rows or len(feedback_rows) == 0:
            return "Focus on clarity and discipline balance appropriate for a {level} learner.".format(level=default_level)

        ratings = [row.get("rating") for row in feedback_rows if isinstance(row.get("rating"), (int, float))]
        avg_rating: Optional[float] = sum(ratings) / len(ratings) if ratings else None
        comments = [row.get("comments", "").strip() for row in feedback_rows if row.get("comments")]

        summary_parts: List[str] = []

        if avg_rating is not None:
            if avg_rating < 3:
                summary_parts.append("Learners previously rated clarity low; simplify language and add concrete steps.")
            elif avg_rating < 4:
                summary_parts.append("Maintain clarity and add vivid examples to improve engagement.")
            else:
                summary_parts.append("Past feedback is positive—preserve approachable tone and structured explanations.")

        if comments:
            summary_parts.append("Specific learner notes: " + " | ".join(comments[:3]))

        summary_parts.append(
            "Ensure the response stays aligned with a {level} learner's expectations.".format(level=default_level)
        )

        return " ".join(summary_parts)
