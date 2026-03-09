import asyncio
import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

RAKUTEN_RECIPE_BASE_URL = "https://openapi.rakuten.co.jp/recipems/api/Recipe"

# Rakuten Recipe API allows ~1 req/sec; keep a safe margin
# Origin must match the domain registered in Rakuten Developer Dashboard.
# Set APP_ORIGIN env var for local development (e.g. http://localhost:8000).
RAKUTEN_RATE_LIMIT_SLEEP = 1.2
RAKUTEN_MAX_RETRIES = 2


async def fetch_category_ranking(category_id: str = "") -> dict:
    """Fetch Rakuten recipe ranking for a category, with rate-limit retry."""
    params: dict = {
        "applicationId": settings.RAKUTEN_APP_ID,
        "formatVersion": "2",
    }
    # accessKey is only required for browser-side (JavaScript) calls
    if settings.RAKUTEN_ACCESS_KEY:
        params["accessKey"] = settings.RAKUTEN_ACCESS_KEY
    if category_id:
        params["categoryId"] = category_id

    url = f"{RAKUTEN_RECIPE_BASE_URL}/CategoryRanking/20170426"

    # Origin header is only meaningful for browser-side requests
    headers = {"Origin": settings.APP_ORIGIN} if settings.RAKUTEN_ACCESS_KEY else {}

    for attempt in range(RAKUTEN_MAX_RETRIES + 1):
        await asyncio.sleep(RAKUTEN_RATE_LIMIT_SLEEP)
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, params=params, headers=headers)

        if response.status_code == 429 and attempt < RAKUTEN_MAX_RETRIES:
            wait = 2.0 * (attempt + 1)
            logger.warning(
                "Rakuten 429 for category=%s, retrying in %.1fs (attempt %d/%d)",
                category_id, wait, attempt + 1, RAKUTEN_MAX_RETRIES,
            )
            await asyncio.sleep(wait)
            continue

        if response.status_code != 200:
            logger.error(
                "Rakuten CategoryRanking returned %s for category=%s: %s",
                response.status_code, category_id, response.text[:500],
            )
        response.raise_for_status()
        return response.json()

    raise RuntimeError(f"Rakuten API rate limit exceeded for category={category_id}")


# Tool definitions exposed to the Claude agent
RAKUTEN_TOOLS: list[dict] = [
    {
        "name": "rakuten_category_ranking",
        "description": (
            "Fetch the recipe ranking for a specific Rakuten Recipe category. "
            "Returns top recipes with title, URL, image, description, and ingredients. "
            "Call this once per category. Do NOT call it multiple times for the same category."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category_id": {
                    "type": "string",
                    "description": (
                        "Rakuten Recipe category ID. Common IDs: "
                        "30=ご飯もの, 31=パスタ, 32=麺・粉物, 33=汁物, 34=おかず(肉), "
                        "35=おかず(野菜), 36=おかず(魚), 37=おかず(豆腐・卵), 40=鍋料理, "
                        "41=サラダ, 43=デザート, 44=ドリンク, 45=スープ. "
                        "Use the IDs provided in the mood analysis."
                    ),
                }
            },
            "required": ["category_id"],
        },
    },
]


async def execute_tool_call(tool_name: str, tool_input: dict) -> str:
    """Execute a Rakuten API tool call and return result as JSON string."""
    try:
        if tool_name == "rakuten_category_ranking":
            category_id = tool_input.get("category_id", "")
            result = await fetch_category_ranking(category_id=category_id)
            return json.dumps(result, ensure_ascii=False)

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        logger.error("Rakuten API tool call failed [%s]: %s", tool_name, e, exc_info=True)
        return json.dumps({"error": str(e)})
