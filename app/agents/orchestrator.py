import asyncio
import json
import re

import anthropic

from app.agents.nutrition_advisor import run_nutrition_advisor
from app.agents.recipe_hunter import run_recipe_hunter
from app.agents.seasonal_sommelier import run_seasonal_sommelier
from app.agents.types import (
    FinalProposal,
    MealConstraints,
    MoodAnalysis,
    NutritionAdvice,
    ProposedMeal,
    RakutenRecipe,
    RecipeHunterResult,
    SeasonalRecommendation,
)
from app.config import settings

ORCHESTRATOR_MODEL = "claude-sonnet-4-20250514"

PHASE1_SYSTEM = """You are a mood analysis expert. Analyze the user's mood input and extract
structured information for meal recommendation.

Return a JSON object with this exact structure:
{
  "raw_input": "original user text",
  "mood_keywords": ["keyword1", "keyword2"],
  "food_keywords": ["food1", "food2"],
  "target_categories": ["category_id1", "category_id2"],
  "constraints": {
    "max_cooking_time": "30分 or null",
    "max_cost": "500円 or null",
    "preference_notes": "notes or null"
  }
}

For target_categories, use Rakuten Recipe category IDs. Common ones:
- 30 (ご飯もの), 31 (パスタ), 32 (麺・粉物), 33 (汁物), 34 (おかず(肉)), 35 (おかず(野菜))
- 36 (おかず(魚)), 37 (おかず(豆腐・卵)), 38 (おかず(その他)), 39 (お弁当のおかず)
- 40 (鍋料理), 41 (サラダ), 42 (おつまみ), 43 (デザート・おやつ), 44 (ドリンク)
- 45 (スープ), 46 (パン), 47 (ピザ)

Choose 2-3 categories that best match the mood.
Return ONLY the JSON object, no other text."""

PHASE3_SYSTEM = """You are MoodMeshi's AI chef and meal proposal specialist.
Your job is to synthesize information from multiple specialists and create personalized meal proposals.

IMPORTANT: You MUST always return exactly 3 proposals. If no Rakuten recipes are available,
create fictional but realistic Japanese recipe proposals based on the mood, nutrition, and seasonal information.

Create a final proposal in JSON format:
{
  "greeting": "Warm, personalized greeting acknowledging the user's mood (in Japanese)",
  "proposals": [
    {
      "rank": 1,
      "recipe": {
        "recipe_id": "string (use empty string if creating fictional recipe)",
        "recipe_title": "string (required, cannot be null)",
        "recipe_url": "string (use empty string if no URL available)",
        "food_image_url": null,
        "recipe_description": "string or null",
        "recipe_material": ["ingredient1", "ingredient2"],
        "recipe_indication": "string or null",
        "recipe_cost": "string or null",
        "rank": "string or null",
        "category_name": "string or null"
      },
      "why_recommended": "Why this recipe matches the mood (in Japanese)",
      "nutrition_point": "Key nutrition highlight (in Japanese)",
      "seasonal_point": "Seasonal connection (in Japanese)",
      "arrange_tip": "Optional cooking tip (in Japanese)"
    }
  ],
  "closing_message": "Encouraging closing message (in Japanese)"
}

CRITICAL RULES:
- Always return exactly 3 proposals
- recipe_title and recipe_url must be strings (use empty string "" if no value, never null)
- recipe_id must be a string (use empty string "" if no value, never null)
- All other string fields can be null
Return ONLY the JSON object, no other text."""


def _default_nutrition_advice() -> NutritionAdvice:
    return NutritionAdvice(
        mood_based_nutrients=["ビタミンB群", "マグネシウム"],
        recommended_ingredients=["野菜", "魚"],
        avoid_ingredients=[],
        advice_text="バランスの良い食事を心がけましょう。",
    )


def _default_seasonal_recommendation() -> SeasonalRecommendation:
    import datetime
    today = datetime.date.today()
    return SeasonalRecommendation(
        current_season="春",
        seasonal_ingredients=["タケノコ", "春キャベツ"],
        seasonal_dishes=["竹の子ご飯"],
        seasonal_note="旬の食材をお楽しみください。",
        reference_date=today.strftime("%Y-%m-%d"),
    )


async def _phase1_analyze_mood(client: anthropic.AsyncAnthropic, user_input: str) -> MoodAnalysis:
    """Phase 1: Analyze user mood and extract structured information."""
    response = await client.messages.create(
        model=ORCHESTRATOR_MODEL,
        max_tokens=1024,
        system=PHASE1_SYSTEM,
        messages=[{"role": "user", "content": f"Analyze this mood: {user_input}"}],
    )

    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    try:
        data = json.loads(text_content.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text_content, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Failed to parse mood analysis: {text_content}")

    constraints = MealConstraints(**data.get("constraints", {}))

    return MoodAnalysis(
        raw_input=user_input,
        mood_keywords=data.get("mood_keywords", []),
        food_keywords=data.get("food_keywords", []),
        target_categories=data.get("target_categories", ["34", "35"]),
        constraints=constraints,
    )


async def _phase3_integrate(
    client: anthropic.AsyncAnthropic,
    mood: MoodAnalysis,
    hunter_result: RecipeHunterResult,
    nutrition: NutritionAdvice,
    seasonal: SeasonalRecommendation,
) -> FinalProposal:
    """Phase 3: Integrate all worker results into final proposal."""
    has_recipes = len(hunter_result.recipes) > 0
    recipe_context = (
        f"Available Rakuten recipes ({len(hunter_result.recipes)} found):\n"
        + json.dumps([r.model_dump() for r in hunter_result.recipes[:15]], ensure_ascii=False, indent=2)
        if has_recipes
        else "No Rakuten recipes available. Please create 3 fictional but realistic Japanese recipe proposals."
    )

    context = f"""User mood: {mood.raw_input}
Mood keywords: {', '.join(mood.mood_keywords)}

{recipe_context}

Nutrition advice:
- Key nutrients: {', '.join(nutrition.mood_based_nutrients)}
- Recommended ingredients: {', '.join(nutrition.recommended_ingredients)}
- Avoid: {', '.join(nutrition.avoid_ingredients)}
- Advice: {nutrition.advice_text}

Seasonal information:
- Current season: {seasonal.current_season}
- Seasonal ingredients: {', '.join(seasonal.seasonal_ingredients)}
- Recommended dishes: {', '.join(seasonal.seasonal_dishes)}
- Note: {seasonal.seasonal_note}

{"Select 3 recipes from the available list" if has_recipes else "Create 3 fictional recipe proposals"} and make personalized proposals."""

    response = await client.messages.create(
        model=ORCHESTRATOR_MODEL,
        max_tokens=4096,
        system=PHASE3_SYSTEM,
        messages=[{"role": "user", "content": context}],
    )

    text_content = ""
    for block in response.content:
        if hasattr(block, "text"):
            text_content += block.text

    try:
        data = json.loads(text_content.strip())
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text_content, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Failed to parse final proposal: {text_content}")

    proposals = []
    for p in data.get("proposals", []):
        recipe_data = p.get("recipe", {})
        # Ensure required string fields are never None
        recipe_data["recipe_id"] = recipe_data.get("recipe_id") or ""
        recipe_data["recipe_title"] = recipe_data.get("recipe_title") or ""
        recipe_data["recipe_url"] = recipe_data.get("recipe_url") or ""
        recipe = RakutenRecipe(**recipe_data)
        proposal = ProposedMeal(
            rank=p.get("rank", len(proposals) + 1),
            recipe=recipe,
            why_recommended=p.get("why_recommended", ""),
            nutrition_point=p.get("nutrition_point", ""),
            seasonal_point=p.get("seasonal_point", ""),
            arrange_tip=p.get("arrange_tip"),
        )
        proposals.append(proposal)

    return FinalProposal(
        greeting=data.get("greeting", f"{mood.raw_input}の気分に合わせたレシピをご提案します。"),
        proposals=proposals,
        closing_message=data.get("closing_message", "今日も美味しい食事をお楽しみください！"),
    )


async def run_orchestrator(user_input: str) -> FinalProposal:
    """Orchestrator: Coordinate all workers and produce final meal proposals."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Phase 1: Analyze mood
    mood = await _phase1_analyze_mood(client, user_input)

    # Phase 2: Run workers in parallel
    results = await asyncio.gather(
        run_recipe_hunter(mood),
        run_nutrition_advisor(mood),
        run_seasonal_sommelier(mood),
        return_exceptions=True,
    )

    hunter_result = results[0] if not isinstance(results[0], Exception) else RecipeHunterResult(
        recipes=[], searched_categories=[], error_message=str(results[0])
    )
    nutrition = results[1] if not isinstance(results[1], Exception) else _default_nutrition_advice()
    seasonal = results[2] if not isinstance(results[2], Exception) else _default_seasonal_recommendation()

    # Phase 3: Integrate results
    final_proposal = await _phase3_integrate(client, mood, hunter_result, nutrition, seasonal)
    return final_proposal
