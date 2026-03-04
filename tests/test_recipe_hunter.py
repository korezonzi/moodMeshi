"""Tests for RecipeHunter worker agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.recipe_hunter import run_recipe_hunter
from app.agents.types import MealConstraints, MoodAnalysis, RecipeHunterResult


@pytest.fixture
def sample_mood() -> MoodAnalysis:
    return MoodAnalysis(
        raw_input="疲れた",
        mood_keywords=["疲れ", "癒し"],
        food_keywords=["温かい", "やさしい"],
        target_categories=["33", "40"],
        constraints=MealConstraints(max_cooking_time="30分"),
    )


@pytest.fixture
def mock_final_response() -> dict:
    return {
        "recipes": [
            {
                "recipe_id": "1234567",
                "recipe_title": "簡単豚汁",
                "recipe_url": "https://recipe.rakuten.co.jp/recipe/1234567/",
                "food_image_url": "https://example.com/image.jpg",
                "recipe_description": "体が温まる豚汁",
                "recipe_material": ["豚肉", "大根", "みそ"],
                "recipe_indication": "約20分",
                "recipe_cost": "200円前後",
                "rank": "1",
                "category_name": "汁物",
            }
        ],
        "searched_categories": ["33", "40"],
    }


@pytest.mark.asyncio
async def test_recipe_hunter_returns_result(
    sample_mood: MoodAnalysis,
    mock_final_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_message.stop_reason = "end_turn"
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = json.dumps(mock_final_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_recipe_hunter(sample_mood)

    assert isinstance(result, RecipeHunterResult)


@pytest.mark.asyncio
async def test_recipe_hunter_recipes_non_empty(
    sample_mood: MoodAnalysis,
    mock_final_response: dict,
) -> None:
    mock_message = MagicMock()
    mock_message.stop_reason = "end_turn"
    mock_text_block = MagicMock()
    mock_text_block.type = "text"
    mock_text_block.text = json.dumps(mock_final_response)
    mock_message.content = [mock_text_block]

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(return_value=mock_message)

        result = await run_recipe_hunter(sample_mood)

    assert len(result.recipes) > 0
    assert result.recipes[0].recipe_title == "簡単豚汁"


@pytest.mark.asyncio
async def test_recipe_hunter_error_handling(sample_mood: MoodAnalysis) -> None:
    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        result = await run_recipe_hunter(sample_mood)

    assert isinstance(result, RecipeHunterResult)
    assert result.recipes == []
    assert result.error_message is not None
    assert "API Error" in result.error_message
