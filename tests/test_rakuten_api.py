"""Tests for Rakuten Recipe API tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.rakuten_recipe import (
    RAKUTEN_TOOLS,
    execute_tool_call,
    fetch_category_ranking,
)


@pytest.fixture
def mock_ranking_response() -> dict:
    return {
        "result": [
            {
                "recipeId": 1234567,
                "recipeTitle": "簡単チキンカレー",
                "recipeUrl": "https://recipe.rakuten.co.jp/recipe/1234567/",
                "foodImageUrl": "https://example.com/image.jpg",
                "recipeDescription": "子供も大人も大好きなカレー",
                "recipeMaterial": ["鶏肉", "玉ねぎ", "カレールー"],
                "recipeIndication": "約30分",
                "recipeCost": "300円前後",
                "rank": "1",
                "categoryName": "カレー",
            }
        ]
    }


@pytest.mark.asyncio
async def test_fetch_category_ranking(mock_ranking_response: dict) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_ranking_response
    mock_response.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient") as mock_client_class,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await fetch_category_ranking(category_id="34")

    assert "result" in result
    assert len(result["result"]) > 0


@pytest.mark.asyncio
async def test_execute_tool_call_ranking(mock_ranking_response: dict) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_ranking_response
    mock_response.raise_for_status = MagicMock()

    with (
        patch("httpx.AsyncClient") as mock_client_class,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await execute_tool_call("rakuten_category_ranking", {"category_id": "34"})

    parsed = json.loads(result)
    assert "result" in parsed


@pytest.mark.asyncio
async def test_execute_tool_call_error_handling() -> None:
    with patch(
        "app.tools.rakuten_recipe.fetch_category_ranking",
        side_effect=Exception("API Error"),
    ):
        result = await execute_tool_call("rakuten_category_ranking", {"category_id": "34"})

    parsed = json.loads(result)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_execute_tool_call_unknown_tool() -> None:
    result = await execute_tool_call("unknown_tool", {})
    parsed = json.loads(result)
    assert "error" in parsed


def test_rakuten_tools_structure() -> None:
    assert len(RAKUTEN_TOOLS) == 1
    tool = RAKUTEN_TOOLS[0]
    assert tool["name"] == "rakuten_category_ranking"
    assert "description" in tool
    assert "input_schema" in tool
    assert tool["input_schema"]["type"] == "object"
