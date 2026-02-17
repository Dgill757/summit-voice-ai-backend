"""
Content Quality Scoring Service
Analyzes content for human-like quality and platform compliance
"""
from typing import Dict, Any
import re
import os
from anthropic import Anthropic


class ContentScorer:
    """Scores content for human-likeness and quality"""

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic = Anthropic(api_key=api_key) if api_key else None

    def score_content(self, content: str, platform: str) -> Dict[str, Any]:
        """
        Score content for human-likeness and platform compliance

        Returns:
        {
            "human_score": 85,  # 0-100, higher is more human
            "issues": ["list of issues"],
            "character_count": 150,
            "platform_compliant": True,
            "emoji_count": 0,
            "mdash_count": 0,
            "ai_indicators": ["list of AI-like phrases"]
        }
        """

        # Count characters
        char_count = len(content)

        # Platform limits
        platform_limits = {
            "linkedin": 3000,
            "twitter": 280,
            "facebook": 63206,
            "instagram": 2200
        }

        # Check emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "]+",
            flags=re.UNICODE
        )
        emoji_count = len(emoji_pattern.findall(content))

        # Check for em-dashes
        mdash_count = content.count('—')

        # Check AI indicators
        ai_phrases = [
            "delve", "leverage", "cutting-edge", "revolutionize",
            "game-changer", "unlock", "dive deep", "it's important to note",
            "at the end of the day", "in today's fast-paced world"
        ]

        ai_indicators = [phrase for phrase in ai_phrases if phrase.lower() in content.lower()]

        # Calculate base human score
        human_score = 100

        # Penalties
        if emoji_count > 0:
            human_score -= emoji_count * 5

        if mdash_count > 0:
            human_score -= mdash_count * 3

        if len(ai_indicators) > 0:
            human_score -= len(ai_indicators) * 10

        # Use Claude to analyze for AI patterns
        ai_score = self._analyze_with_ai(content)
        human_score = min(human_score, ai_score)

        # Ensure score is 0-100
        human_score = max(0, min(100, human_score))

        # Check platform compliance
        max_chars = platform_limits.get(platform.lower(), 10000)
        platform_compliant = char_count <= max_chars

        # Collect issues
        issues = []
        if emoji_count > 0:
            issues.append(f"Contains {emoji_count} emojis (should be 0)")
        if mdash_count > 0:
            issues.append(f"Contains {mdash_count} em-dashes (should be 0)")
        if ai_indicators:
            issues.append(f"Contains AI phrases: {', '.join(ai_indicators)}")
        if not platform_compliant:
            issues.append(f"Too long for {platform} ({char_count}/{max_chars} chars)")

        return {
            "human_score": human_score,
            "issues": issues,
            "character_count": char_count,
            "max_characters": max_chars,
            "platform_compliant": platform_compliant,
            "emoji_count": emoji_count,
            "mdash_count": mdash_count,
            "ai_indicators": ai_indicators,
            "recommendation": "approve" if human_score >= 70 and not issues else "revise"
        }

    def _analyze_with_ai(self, content: str) -> int:
        """Use Claude to analyze content for AI patterns"""

        try:
            if self.anthropic is None:
                return 75
            message = self.anthropic.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=200,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze this content and rate how human it sounds on a scale of 0-100.

Content: "{content}"

Consider:
- Natural language flow
- Conversational tone
- Lack of corporate jargon
- Personal voice
- Specific details vs generic statements

Respond with ONLY a number 0-100. No explanation."""
                }]
            )

            score_text = message.content[0].text.strip()
            score_match = re.search(r'\d+', score_text)
            if not score_match:
                return 75
            score = int(score_match.group())
            return max(0, min(100, score))

        except Exception:
            # Fallback if API fails
            return 75

