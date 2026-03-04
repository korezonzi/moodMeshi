"""Tests for SeasonalSommelier worker agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.seasonal_sommelier import run_seasonal_sommelier
from app.agents.types import MealConstraints, MoodAnalysis, SeasonalRecommendation


@pytest.fixture
def sample_mood() -> MoodAnalysis:
    return MoodAnalysis(
        raw_input="なんか寂しい",
        mood_keywords=["寂しい", "孤独"],
        food_keywords=["温まる", "ほっとする"],
        target_categories=["40", "33"],
        constraints=MealConstraints(),
    )


@pytest.fixture
def mock_seasonal_response() -> dict:
    return {
        "current_season": "冬",
        "seasonal_ingredients": ["大根", "白菜", "ぶり", "牡蠣", "ゆず"],
        "seasonal_dishes": ["おでん", "鍋料理", "ぶり大根"],
        "seasonal_note": "冬の旬の食材で体を温め、寂しい気持ちを癒しましょう。",
        "reference_date": "2026-03-04",
    }


@pytest.mark.asyncio
async def test_seasonal_sommelier_returns_recommendation(
    sample_mood: MoodAnalysis,
    mock_seasonal_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = json.dumps(mock_seasonal_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_seasonal_sommelier(sample_mood)

    assert isinstance(result, SeasonalRecommendation)


@pytest.mark.asyncio
async def test_seasonal_sommelier_reference_date_set(
    sample_mood: MoodAnalysis,
    mock_seasonal_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_text_block = MagicMock()
    mock_text_block.text = json.dumps(mock_seasonal_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_seasonal_sommelier(sample_mood)

    assert result.reference_date != ""
    parts = result.reference_date.split("-")
    assert len(parts) == 3
    assert len(parts[0]) == 4


@pytest.mark.asyncio
async def test_seasonal_sommelier_error_handling(sample_mood: MoodAnalysis) -> None:
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        result = await run_seasonal_sommelier(sample_mood)

    assert isinstance(result, SeasonalRecommendation)
    assert result.current_season in ["春", "夏", "秋", "冬"]
    assert result.reference_date != ""
