import datetime
import json
import re

import anthropic

from app.agents.types import MoodAnalysis, SeasonalRecommendation
from app.config import settings

MODEL = "claude-haiku-4-5-20250501"

SYSTEM_PROMPT = """You are a seasonal food specialist who knows which ingredients and dishes
are best in each season in Japan.

Analyze the current season and mood to provide seasonal food recommendations in JSON format:
{
  "current_season": "春/夏/秋/冬",
  "seasonal_ingredients": ["ingredient1", "ingredient2"],
  "seasonal_dishes": ["dish1", "dish2"],
  "seasonal_note": "Note about seasonal recommendations in Japanese",
  "reference_date": "YYYY-MM-DD"
}

Return ONLY the JSON object, no other text. Use Japanese for all text fields."""


def _get_season(date: datetime.date) -> str:
    """Determine Japanese season from date."""
    month = date.month
    if month in (3, 4, 5):
        return "春"
    elif month in (6, 7, 8):
        return "夏"
    elif month in (9, 10, 11):
        return "秋"
    else:
        return "冬"


async def run_seasonal_sommelier(mood: MoodAnalysis) -> SeasonalRecommendation:
    """Worker C: Provide seasonal food recommendations based on current date and mood."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    today = datetime.date.today()
    today_str = today.strftime("%Y-%m-%d")
    season = _get_season(today)

    user_message = f"""Today is {today_str} (current season: {season}).

Provide seasonal food recommendations for this mood:
- Raw input: {mood.raw_input}
- Mood keywords: {', '.join(mood.mood_keywords)}

Consider what seasonal ingredients and dishes would best comfort or energize
the person based on their current mood and the time of year."""

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
                return _default_recommendation(today_str, season)

        return SeasonalRecommendation(
            current_season=result_data.get("current_season", season),
            seasonal_ingredients=result_data.get("seasonal_ingredients", []),
            seasonal_dishes=result_data.get("seasonal_dishes", []),
            seasonal_note=result_data.get("seasonal_note", ""),
            reference_date=result_data.get("reference_date", today_str),
        )

    except Exception:
        return _default_recommendation(today_str, season)


def _default_recommendation(today_str: str, season: str) -> SeasonalRecommendation:
    seasonal_defaults = {
        "春": {
            "ingredients": ["タケノコ", "春キャベツ", "菜の花", "あさり"],
            "dishes": ["竹の子ご飯", "春キャベツの炒め物"],
        },
        "夏": {
            "ingredients": ["トマト", "ナス", "ゴーヤ", "とうもろこし"],
            "dishes": ["冷や汁", "ゴーヤチャンプルー"],
        },
        "秋": {
            "ingredients": ["さつまいも", "きのこ", "栗", "さんま"],
            "dishes": ["さんまの塩焼き", "きのこご飯"],
        },
        "冬": {
            "ingredients": ["大根", "白菜", "ぶり", "牡蠣"],
            "dishes": ["おでん", "鍋料理"],
        },
    }
    defaults = seasonal_defaults.get(season, seasonal_defaults["冬"])

    return SeasonalRecommendation(
        current_season=season,
        seasonal_ingredients=defaults["ingredients"],
        seasonal_dishes=defaults["dishes"],
        seasonal_note=f"{season}の旬の食材を使った料理をお楽しみください。",
        reference_date=today_str,
    )
