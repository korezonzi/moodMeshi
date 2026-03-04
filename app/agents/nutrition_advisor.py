import json
import re

import anthropic

from app.agents.types import MoodAnalysis, NutritionAdvice
from app.config import settings

MODEL = "claude-haiku-4-5-20250501"

SYSTEM_PROMPT = """You are a nutrition specialist who understands the relationship between
mood and nutritional needs.

Analyze the user's mood and provide nutritional advice in JSON format:
{
  "mood_based_nutrients": ["nutrient1", "nutrient2"],
  "recommended_ingredients": ["ingredient1", "ingredient2"],
  "avoid_ingredients": ["ingredient1", "ingredient2"],
  "advice_text": "Overall advice text in Japanese"
}

Return ONLY the JSON object, no other text. Use Japanese for ingredient names and advice."""


async def run_nutrition_advisor(mood: MoodAnalysis) -> NutritionAdvice:
    """Worker B: Provide nutrition advice based on mood analysis."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_message = f"""Analyze the nutritional needs for this mood:
- Raw input: {mood.raw_input}
- Mood keywords: {', '.join(mood.mood_keywords)}
- Food keywords: {', '.join(mood.food_keywords)}

Provide nutritional advice that addresses the emotional and physical needs
suggested by this mood."""

    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        text_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text

        try:
            result_data = json.loads(text_content.strip())
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", text_content, re.DOTALL)
            if match:
                result_data = json.loads(match.group())
            else:
                return _default_advice()

        return NutritionAdvice(
            mood_based_nutrients=result_data.get("mood_based_nutrients", []),
            recommended_ingredients=result_data.get("recommended_ingredients", []),
            avoid_ingredients=result_data.get("avoid_ingredients", []),
            advice_text=result_data.get("advice_text", ""),
        )

    except Exception:
        return _default_advice()


def _default_advice() -> NutritionAdvice:
    return NutritionAdvice(
        mood_based_nutrients=["ビタミンB群", "マグネシウム", "トリプトファン"],
        recommended_ingredients=["野菜", "魚", "豆類"],
        avoid_ingredients=["過度な糖分", "カフェイン"],
        advice_text="バランスの良い食事を心がけましょう。",
    )
