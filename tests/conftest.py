"""Pytest configuration and shared fixtures."""

import os

# Set dummy env vars before any app module is imported
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")
os.environ.setdefault("RAKUTEN_APP_ID", "dummy_app_id")
os.environ.setdefault("RAKUTEN_ACCESS_KEY", "dummy_access_key")

import pytest

from app.agents.types import (
    FinalProposal,
    MealConstraints,
    MoodAnalysis,
    ProposedMeal,
    RakutenRecipe,
)


from app.config import settings

DB_AVAILABLE = bool(settings.DATABASE_URL)

requires_db = pytest.mark.skipif(not DB_AVAILABLE, reason="DATABASE_URL not set")


def make_mood(
    raw_input: str = "疲れたからがっつり食べたい",
    mood_keywords: list[str] | None = None,
    food_keywords: list[str] | None = None,
    target_categories: list[str] | None = None,
) -> MoodAnalysis:
    return MoodAnalysis(
        raw_input=raw_input,
        mood_keywords=mood_keywords or ["疲れ", "がっつり"],
        food_keywords=food_keywords or ["肉"],
        target_categories=target_categories or ["10"],
        constraints=MealConstraints(),
    )


def make_proposal(
    num_meals: int = 2,
    greeting: str = "お疲れさまです！",
    closing_message: str = "楽しんでください！",
) -> FinalProposal:
    meals = []
    for i in range(1, num_meals + 1):
        meals.append(
            ProposedMeal(
                rank=i,
                recipe=RakutenRecipe(
                    recipe_id=f"r{i}",
                    recipe_title=f"テスト料理{i}",
                    recipe_url=f"https://example.com/recipe/{i}",
                    food_image_url=f"https://example.com/img/{i}.jpg",
                    recipe_description=f"テスト説明{i}",
                ),
                why_recommended=f"理由{i}",
                nutrition_point=f"栄養{i}",
                seasonal_point=f"旬{i}",
            )
        )
    return FinalProposal(
        greeting=greeting,
        proposals=meals,
        closing_message=closing_message,
        context_summary="テスト用コンテキスト",
    )
