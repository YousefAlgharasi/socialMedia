import json
import re
from typing import List, Dict, Any

class HighlightDetector:
    """
    Analyzes timestamped speech transcripts to identify the most engaging,
    viral, or insightful segments for Shorts/Reels (30 to 60 seconds).
    """

    def __init__(self, target_clip_duration_range=(30, 60)):
        self.min_duration, self.max_duration = target_clip_duration_range

    def detect_highlights_heuristic(self, transcript_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Heuristic-based highlight detection:
        Scores segments based on:
        - Question hooks ('how', 'why', 'what if', 'secret')
        - High keyword density and emotional/energy words
        - Cohesive start and end sentence boundaries
        """
        highlights = []
        if not transcript_segments:
            return highlights

        hook_keywords = [
            "secret", "mistake", "how to", "why you", "never", "best", "worst",
            "crazy", "insane", "truth", "revealed", "stop doing", "tip", "hack",
            "money", "future", "important", "remember", "problem", "solution"
        ]

        current_clip = []
        current_duration = 0.0

        for seg in transcript_segments:
            text = seg.get("text", "").lower()
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            dur = end - start

            current_clip.append(seg)
            current_duration += dur

            if current_duration >= self.min_duration:
                # Calculate hook score
                combined_text = " ".join(s.get("text", "") for s in current_clip)
                score = 0
                for kw in hook_keywords:
                    if kw in combined_text.lower():
                        score += 1

                # Generate a suggested title
                first_sentence = combined_text.split(".")[0].strip()
                suggested_title = (first_sentence[:60] + "...") if len(first_sentence) > 60 else first_sentence

                highlights.append({
                    "start_time": current_clip[0].get("start", 0.0),
                    "end_time": current_clip[-1].get("end", 0.0),
                    "duration": round(current_duration, 2),
                    "score": score,
                    "title": suggested_title or "Engaging Moment",
                    "transcript_snippet": combined_text[:200] + "..."
                })

                # Reset or slide forward
                current_clip = []
                current_duration = 0.0

                if len(highlights) >= 5:
                    break

        # Sort highlights by score descending
        highlights.sort(key=lambda x: x["score"], reverse=True)
        return highlights

highlight_detector = HighlightDetector()
