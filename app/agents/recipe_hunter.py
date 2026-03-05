import json
import re

import anthropic

from app.agents.types import MoodAnalysis, RakutenRecipe, RecipeHunterResult
from app.config import settings
from app.tools.rakuten_recipe import RAKUTEN_TOOLS, execute_tool_call

MODEL = "claude-haiku-4-5-20250501"

SYSTEM_PROMPT = """You are a recipe hunting specialist. Your job is to find the best recipes
from Rakuten Recipe API that match the user's mood and preferences.

The mood analysis already provides the target category IDs. Use the tool to:
1. Call rakuten_category_ranking for EACH of the target_categories provided (one call per category)
2. Collect all recipes from the results
3. Return the combined results

IMPORTANT: Do NOT fetch the category list. Use the category IDs given in the user message directly.
Call rakuten_category_ranking for each category ID exactly once.

Return your final result as a JSON object with this exact structure:
{
  "recipes": [
    {
      "recipe_id": "string",
      "recipe_title": "string",
      "recipe_url": "string",
      "food_image_url": "string or null",
      "recipe_description": "string or null",
      "recipe_material": ["ingredient1", "ingredient2"],
      "recipe_indication": "string or null",
      "recipe_cost": "string or null",
      "rank": "string or null",
      "category_name": "string or null"
    }
  ],
  "searched_categories": ["category_id1", "category_id2"]
}

Return ONLY the JSON object, no other text."""


async def run_recipe_hunter(mood: MoodAnalysis) -> RecipeHunterResult:
    """Worker A: Hunt for recipes matching the mood analysis using Rakuten API."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    user_message = f"""Find recipes that match this mood analysis:
- Mood keywords: {', '.join(mood.mood_keywords)}
- Food keywords: {', '.join(mood.food_keywords)}
- Target categories: {', '.join(mood.target_categories)}
- Constraints: cooking time={mood.constraints.max_cooking_time}, cost={mood.constraints.max_cost}

Search for recipes in categories that best match this mood."""

    messages = [{"role": "user", "content": user_message}]
    searched_categories: list[str] = []

    try:
        while True:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=RAKUTEN_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_input = block.input
                        if block.name == "rakuten_category_ranking":
                            category_id = tool_input.get("category_id", "")
                            if category_id:
                                searched_categories.append(category_id)

                        result_str = await execute_tool_call(block.name, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
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
                        return RecipeHunterResult(
                            recipes=[],
                            searched_categories=searched_categories,
                            error_message="Failed to parse recipe hunter response",
                        )

                recipes = [
                    RakutenRecipe(**recipe_data)
                    for recipe_data in result_data.get("recipes", [])
                ]
                searched_cats = result_data.get("searched_categories", searched_categories)

                return RecipeHunterResult(
                    recipes=recipes,
                    searched_categories=searched_cats,
                )

    except Exception as e:
        return RecipeHunterResult(
            recipes=[],
            searched_categories=searched_categories,
            error_message=str(e),
        )
