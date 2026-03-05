import json

import httpx

from app.config import settings

RAKUTEN_RECIPE_BASE_URL = "https://openapi.rakuten.co.jp/recipems/api/Recipe"
RAKUTEN_REFERER = "https://moodmeshi.vercel.app"
RAKUTEN_HEADERS = {"Referer": RAKUTEN_REFERER}


async def fetch_category_list(category_type: str = "large") -> dict:
    """Fetch Rakuten recipe categories."""
    params = {
        "applicationId": settings.RAKUTEN_APP_ID,
        "accessKey": settings.RAKUTEN_ACCESS_KEY,
        "formatVersion": "2",
        "categoryType": category_type,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{RAKUTEN_RECIPE_BASE_URL}/CategoryList/20170426",
            params=params,
            headers=RAKUTEN_HEADERS,
        )
        response.raise_for_status()
        return response.json()


async def fetch_category_ranking(category_id: str = "") -> dict:
    """Fetch Rakuten recipe ranking for a category."""
    params = {
        "applicationId": settings.RAKUTEN_APP_ID,
        "accessKey": settings.RAKUTEN_ACCESS_KEY,
        "formatVersion": "2",
    }
    if category_id:
        params["categoryId"] = category_id

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"{RAKUTEN_RECIPE_BASE_URL}/CategoryRanking/20170426",
            params=params,
            headers=RAKUTEN_HEADERS,
        )
        response.raise_for_status()
        return response.json()


RAKUTEN_TOOLS: list[dict] = [
    {
        "name": "rakuten_category_list",
        "description": (
            "Fetch the list of Rakuten recipe categories. "
            "Use this to discover available category IDs before fetching rankings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category_type": {
                    "type": "string",
                    "enum": ["large", "medium", "small"],
                    "description": "Category hierarchy level",
                }
            },
            "required": [],
        },
    },
    {
        "name": "rakuten_category_ranking",
        "description": (
            "Fetch the recipe ranking for a specific Rakuten category. "
            "Returns top recipes with title, URL, image, description, and ingredients."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category_id": {
                    "type": "string",
                    "description": (
                        "Category ID to fetch ranking for. "
                        "Leave empty for overall ranking."
                    ),
                }
            },
            "required": [],
        },
    },
]


async def execute_tool_call(tool_name: str, tool_input: dict) -> str:
    """Execute a Rakuten API tool call and return result as JSON string."""
    try:
        if tool_name == "rakuten_category_list":
            category_type = tool_input.get("category_type", "large")
            result = await fetch_category_list(category_type=category_type)
            return json.dumps(result, ensure_ascii=False)

        if tool_name == "rakuten_category_ranking":
            category_id = tool_input.get("category_id", "")
            result = await fetch_category_ranking(category_id=category_id)
            return json.dumps(result, ensure_ascii=False)

        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})
