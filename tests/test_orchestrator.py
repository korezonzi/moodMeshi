"""Tests for the Orchestrator agent."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.orchestrator import run_orchestrator
from app.agents.types import FinalProposal, ProcessingLog


@pytest.fixture
def mock_mood_analysis_response() -> dict:
    return {
        "raw_input": "疲れた",
        "mood_keywords": ["疲れ", "癒し", "休息"],
        "food_keywords": ["温かい", "やさしい"],
        "target_categories": ["33", "40"],
        "constraints": {
            "max_cooking_time": "30分",
            "max_cost": None,
            "preference_notes": None,
        },
    }


@pytest.fixture
def mock_final_proposal_response() -> dict:
    return {
        "greeting": "お疲れ様です！今日も一日頑張りましたね。",
        "proposals": [
            {
                "rank": 1,
                "recipe": {
                    "recipe_id": "1111111",
                    "recipe_title": "温かい豚汁",
                    "recipe_url": "https://recipe.rakuten.co.jp/recipe/1111111/",
                    "food_image_url": None,
                    "recipe_description": "疲れた体に優しい豚汁",
                    "recipe_material": ["豚肉", "大根", "みそ"],
                    "recipe_indication": "約20分",
                    "recipe_cost": "200円前後",
                    "rank": "1",
                    "category_name": "汁物",
                },
                "why_recommended": "疲れた時は温かい汁物が一番です",
                "nutrition_point": "豚肉のビタミンB1が疲労回復に効果的",
                "seasonal_point": "冬の大根が甘くなっています",
                "arrange_tip": "七味唐辛子を加えると体が温まります",
            },
            {
                "rank": 2,
                "recipe": {
                    "recipe_id": "2222222",
                    "recipe_title": "簡単鍋料理",
                    "recipe_url": "https://recipe.rakuten.co.jp/recipe/2222222/",
                    "food_image_url": None,
                    "recipe_description": "具だくさんの鍋",
                    "recipe_material": ["白菜", "豆腐", "鶏肉"],
                    "recipe_indication": "約25分",
                    "recipe_cost": "300円前後",
                    "rank": "2",
                    "category_name": "鍋料理",
                },
                "why_recommended": "鍋料理は体を温め、心もほぐします",
                "nutrition_point": "豆腐のタンパク質が疲労回復を助けます",
                "seasonal_point": "冬の白菜が美味しい季節です",
                "arrange_tip": None,
            },
            {
                "rank": 3,
                "recipe": {
                    "recipe_id": "3333333",
                    "recipe_title": "炊き込みご飯",
                    "recipe_url": "https://recipe.rakuten.co.jp/recipe/3333333/",
                    "food_image_url": None,
                    "recipe_description": "ふっくら炊き込みご飯",
                    "recipe_material": ["米", "鶏肉", "にんじん"],
                    "recipe_indication": "約40分",
                    "recipe_cost": "250円前後",
                    "rank": "3",
                    "category_name": "ご飯もの",
                },
                "why_recommended": "心が落ち着く和食の定番",
                "nutrition_point": "糖質で脳のエネルギーを補給",
                "seasonal_point": "秋の味覚をご飯で楽しめます",
                "arrange_tip": "昆布だしを使うと旨みが増します",
            },
        ],
        "closing_message": "ゆっくり食事を楽しんで、今日の疲れを癒してください！",
    }


@pytest.mark.asyncio
async def test_orchestrator_returns_final_proposal(
    mock_mood_analysis_response: dict,
    mock_final_proposal_response: dict,
) -> None:
    mock_phase1 = MagicMock()
    mock_phase1.content = [MagicMock(text=json.dumps(mock_mood_analysis_response))]

    mock_phase3 = MagicMock()
    mock_phase3.content = [MagicMock(text=json.dumps(mock_final_proposal_response))]

    mock_hunter = MagicMock(recipes=[], searched_categories=[], error_message=None)
    mock_nutrition = MagicMock(
        mood_based_nutrients=["ビタミンB1"],
        recommended_ingredients=["豚肉"],
        avoid_ingredients=[],
        advice_text="疲労回復に効果的な食材を摂りましょう。",
    )
    mock_seasonal = MagicMock(
        current_season="冬",
        seasonal_ingredients=["大根"],
        seasonal_dishes=["鍋料理"],
        seasonal_note="冬の旬を楽しみましょう。",
        reference_date="2026-03-05",
    )

    with (
        patch("anthropic.AsyncAnthropic") as mock_anthropic,
        patch("app.agents.orchestrator.run_recipe_hunter", return_value=mock_hunter),
        patch("app.agents.orchestrator.run_nutrition_advisor", return_value=mock_nutrition),
        patch("app.agents.orchestrator.run_seasonal_sommelier", return_value=mock_seasonal),
    ):
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=[mock_phase1, mock_phase3])

        result, log = await run_orchestrator("疲れた")

    assert isinstance(result, FinalProposal)
    assert isinstance(log, ProcessingLog)


@pytest.mark.asyncio
async def test_orchestrator_proposals_count(
    mock_mood_analysis_response: dict,
    mock_final_proposal_response: dict,
) -> None:
    mock_phase1 = MagicMock()
    mock_phase1.content = [MagicMock(text=json.dumps(mock_mood_analysis_response))]

    mock_phase3 = MagicMock()
    mock_phase3.content = [MagicMock(text=json.dumps(mock_final_proposal_response))]

    mock_hunter = MagicMock(recipes=[], searched_categories=[], error_message=None)
    mock_nutrition = MagicMock(
        mood_based_nutrients=["ビタミンB1"],
        recommended_ingredients=[],
        avoid_ingredients=[],
        advice_text="",
    )
    mock_seasonal = MagicMock(
        current_season="冬",
        seasonal_ingredients=[],
        seasonal_dishes=[],
        seasonal_note="",
        reference_date="2026-03-05",
    )

    with (
        patch("anthropic.AsyncAnthropic") as mock_anthropic,
        patch("app.agents.orchestrator.run_recipe_hunter", return_value=mock_hunter),
        patch("app.agents.orchestrator.run_nutrition_advisor", return_value=mock_nutrition),
        patch("app.agents.orchestrator.run_seasonal_sommelier", return_value=mock_seasonal),
    ):
        mock_client = AsyncMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create = AsyncMock(side_effect=[mock_phase1, mock_phase3])

        result, log = await run_orchestrator("疲れた")

    assert len(result.proposals) == 3
