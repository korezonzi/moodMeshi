import asyncio
import json
import logging
import re
from typing import Awaitable, Callable

import anthropic

from app.agents.nutrition_advisor import run_nutrition_advisor
from app.agents.recipe_hunter import run_recipe_hunter
from app.agents.seasonal_sommelier import run_seasonal_sommelier
from app.agents.types import (
    AgentLog,
    FinalProposal,
    MealConstraints,
    MoodAnalysis,
    NutritionAdvice,
    ProcessingLog,
    ProposedMeal,
    RakutenRecipe,
    RecipeHunterResult,
    SeasonalRecommendation,
)
from app.config import settings

logger = logging.getLogger(__name__)

ORCHESTRATOR_MODEL = "claude-haiku-4-5-20251001"

ProgressCallback = Callable[[str, str], Awaitable[None]]

CATEGORY_NAME_MAP: dict[str, str] = {
    "30": "ご飯もの", "31": "パスタ", "32": "麺・粉物", "33": "汁物",
    "34": "おかず(肉)", "35": "おかず(野菜)", "36": "おかず(魚)",
    "37": "おかず(豆腐・卵)", "38": "おかず(その他)", "39": "お弁当のおかず",
    "40": "鍋料理", "41": "サラダ", "42": "おつまみ",
    "43": "デザート・おやつ", "44": "ドリンク", "45": "スープ",
    "46": "パン", "47": "ピザ",
}

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

IMPORTANT: You MUST always return exactly 6 proposals. If no Rakuten recipes are available,
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
  "closing_message": "Encouraging closing message (in Japanese)",
  "context_summary": "なぜこれらの料理を選んだか・どの観点を重視したかを2〜3文の自然な日本語で"
}

CRITICAL RULES:
- Always return exactly 6 proposals (rank 1 through 6)
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
        context_summary=data.get("context_summary", ""),
    )


def _build_processing_log(
    mood: MoodAnalysis,
    hunter: RecipeHunterResult,
    nutrition: NutritionAdvice,
    seasonal: SeasonalRecommendation,
) -> ProcessingLog:
    """Build a human-readable processing log from agent results."""
    # Phase 1
    cat_names = [CATEGORY_NAME_MAP.get(c, c) for c in mood.target_categories]
    phase1 = (
        f"ユーザーの「{mood.raw_input}」という気分をAIが分析しました。"
        f"「{'」「'.join(mood.mood_keywords)}」というキーワードを抽出し、"
        f"「{'」「'.join(cat_names)}」のカテゴリで料理を探すよう判断しました。"
    )
    if mood.constraints.max_cooking_time:
        phase1 += f"調理時間は{mood.constraints.max_cooking_time}以内という条件も考慮しました。"

    # Phase 2 — Recipe Hunter
    searched = [CATEGORY_NAME_MAP.get(c, c) for c in hunter.searched_categories] or cat_names
    recipe_count = len(hunter.recipes)
    hunter_action = f"「{'」「'.join(searched)}」のカテゴリで楽天レシピの人気ランキングを検索しました"
    hunter_result = (
        f"{recipe_count}件のレシピが見つかりました。タイトル・材料・調理時間などの情報を収集しました。"
        if recipe_count > 0
        else "レシピの取得中にエラーが発生したため、AIが独自のレシピ案を生成しました。"
    )

    # Phase 2 — Nutrition Advisor
    nutrients = "・".join(nutrition.mood_based_nutrients) if nutrition.mood_based_nutrients else "各種ビタミン"
    ingredients = "・".join(nutrition.recommended_ingredients[:3]) if nutrition.recommended_ingredients else "バランスの良い食材"
    nutrition_action = f"「{mood.raw_input}」という気分のときに必要な栄養素を分析しました"
    nutrition_result = f"「{nutrients}」を重点的に補うことを推奨。{ingredients}などを使った料理が適していると判断しました。"

    # Phase 2 — Seasonal Sommelier
    season = seasonal.current_season
    season_ingredients = "・".join(seasonal.seasonal_ingredients[:3]) if seasonal.seasonal_ingredients else "旬の食材"
    ref_date = seasonal.reference_date if isinstance(seasonal.reference_date, str) else ""
    seasonal_action = f"本日（{ref_date}）の季節「{season}」に合う食材を調査しました"
    seasonal_result = f"「{season_ingredients}」などの旬の食材を使うことを推奨しました。"

    agent_logs = [
        AgentLog(
            agent_name="🔍 レシピハンター",
            role="楽天レシピAPIを活用してレシピを検索するエージェント",
            action=hunter_action,
            result_summary=hunter_result,
        ),
        AgentLog(
            agent_name="🥗 栄養アドバイザー",
            role="気分と栄養の関係を分析し、摂るべき栄養素を特定するエージェント",
            action=nutrition_action,
            result_summary=nutrition_result,
        ),
        AgentLog(
            agent_name="🌸 季節ソムリエ",
            role="旬の食材・料理を推奨するエージェント",
            action=seasonal_action,
            result_summary=seasonal_result,
        ),
    ]

    # Phase 3
    phase3 = (
        f"3つのエージェントの情報を統合し、最終提案を生成しました。"
        f"{recipe_count}件のレシピ候補から、栄養・季節・気分の3つの観点を組み合わせて3つを厳選し、"
        f"それぞれに推奨理由・栄養ポイント・季節のポイントを付け加えました。"
    )

    return ProcessingLog(
        phase1_summary=phase1,
        agent_logs=agent_logs,
        phase3_summary=phase3,
    )


async def run_orchestrator(
    user_input: str,
    progress_callback: ProgressCallback | None = None,
    user_id: str | None = None,
    slack_channel_id: str | None = None,
) -> tuple[FinalProposal, ProcessingLog]:
    """Orchestrator: Coordinate all workers and produce final meal proposals."""
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def cb(phase: str, message: str) -> None:
        if progress_callback:
            await progress_callback(phase, message)

    # Prepend user preferences to input when available
    effective_input = user_input
    if settings.DATABASE_URL and user_id:
        try:
            from app.database import repository
            prefs = await repository.get_user_prefs(user_id)
            if prefs:
                if prefs.allergy_notes:
                    effective_input += f"\n(アレルギー: {prefs.allergy_notes})"
                if prefs.preference_notes:
                    effective_input += f"\n(好み: {prefs.preference_notes})"
        except Exception:
            logger.exception("Failed to load user prefs for user %s", user_id)

    # Phase 1: Analyze mood
    await cb("phase1", "気分を分析中...")
    mood = await _phase1_analyze_mood(client, effective_input)

    # Phase 2: Run workers in parallel
    async def run_recipe_hunter_with_cb() -> RecipeHunterResult:
        await cb("phase2_recipe", "レシピを探しています...")
        return await run_recipe_hunter(mood)

    async def run_nutrition_advisor_with_cb() -> NutritionAdvice:
        await cb("phase2_nutrition", "栄養を分析中...")
        return await run_nutrition_advisor(mood)

    async def run_seasonal_sommelier_with_cb() -> SeasonalRecommendation:
        await cb("phase2_seasonal", "季節の食材を確認中...")
        return await run_seasonal_sommelier(mood)

    results = await asyncio.gather(
        run_recipe_hunter_with_cb(),
        run_nutrition_advisor_with_cb(),
        run_seasonal_sommelier_with_cb(),
        return_exceptions=True,
    )

    hunter_result = results[0] if not isinstance(results[0], Exception) else RecipeHunterResult(
        recipes=[], searched_categories=[], error_message=str(results[0])
    )
    nutrition = results[1] if not isinstance(results[1], Exception) else _default_nutrition_advice()
    seasonal = results[2] if not isinstance(results[2], Exception) else _default_seasonal_recommendation()

    # Phase 3: Integrate results
    await cb("phase3", "最終提案を生成中...")
    final_proposal = await _phase3_integrate(client, mood, hunter_result, nutrition, seasonal)
    processing_log = _build_processing_log(mood, hunter_result, nutrition, seasonal)

    # Persist session non-fatally
    if settings.DATABASE_URL and user_id:
        try:
            from app.database import repository
            await repository.save_session(
                user_id=user_id,
                user_input=user_input,
                mood=mood,
                proposal=final_proposal,
                slack_channel_id=slack_channel_id,
            )
        except Exception:
            logger.exception("Failed to save session for user %s", user_id)

    return final_proposal, processing_log
