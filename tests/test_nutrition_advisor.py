"""Tests for NutritionAdvisor worker agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.nutrition_advisor import run_nutrition_advisor
from app.agents.types import MealConstraints, MoodAnalysis, NutritionAdvice


@pytest.fixture
def sample_mood() -> MoodAnalysis:
    return MoodAnalysis(
        raw_input="元気いっぱい",
        mood_keywords=["元気", "活力"],
        food_keywords=["ガッツリ", "タンパク質"],
        target_categories=["34"],
        constraints=MealConstraints(),
    )


@pytest.fixture
def mock_nutrition_response() -> dict:
    return {
        "mood_based_nutrients": ["タンパク質", "鉄分", "ビタミンB12"],
        "recommended_ingredients": ["鶏肉", "赤身肉", "豆類", "ほうれん草"],
        "avoid_ingredients": ["重たい揚げ物"],
        "advice_text": "元気な気分に合わせて、タンパク質豊富な食材を取り入れましょう。",
    }


@pytest.mark.asyncio
async def test_nutrition_advisor_returns_advice(
    sample_mood: MoodAnalysis,
    mock_nutrition_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = json.dumps(mock_nutrition_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_nutrition_advisor(sample_mood)

    assert isinstance(result, NutritionAdvice)


@pytest.mark.asyncio
async def test_nutrition_advisor_mood_based_nutrients_non_empty(
    sample_mood: MoodAnalysis,
    mock_nutrition_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = json.dumps(mock_nutrition_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_nutrition_advisor(sample_mood)

    assert len(result.mood_based_nutrients) > 0
    assert "タンパク質" in result.mood_based_nutrients


@pytest.mark.asyncio
async def test_nutrition_advisor_error_handling(sample_mood: MoodAnalysis) -> None:
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        result = await run_nutrition_advisor(sample_mood)

    assert isinstance(result, NutritionAdvice)
    assert len(result.mood_based_nutrients) > 0
