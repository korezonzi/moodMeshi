from pydantic import BaseModel, Field


class MealConstraints(BaseModel):
    max_cooking_time: str | None = Field(
        default=None, description="Maximum cooking time (e.g., '30分')"
    )
    max_cost: str | None = Field(
        default=None, description="Maximum cost per meal (e.g., '500円')"
    )
    preference_notes: str | None = Field(
        default=None, description="Additional preference notes"
    )


class MoodAnalysis(BaseModel):
    raw_input: str = Field(description="Original user input text")
    mood_keywords: list[str] = Field(description="Extracted mood keywords")
    food_keywords: list[str] = Field(description="Food-related keywords from input")
    target_categories: list[str] = Field(
        description="Rakuten recipe category IDs to search"
    )
    constraints: MealConstraints = Field(description="Meal constraints derived from mood")


class RakutenRecipe(BaseModel):
    recipe_id: str = Field(default="", description="Rakuten recipe ID")
    recipe_title: str = Field(default="", description="Recipe title")
    recipe_url: str = Field(default="", description="URL to the recipe page")
    food_image_url: str | None = Field(default=None, description="Recipe image URL")
    recipe_description: str | None = Field(default=None, description="Recipe description")
    recipe_material: list[str] = Field(
        default_factory=list, description="List of ingredients"
    )
    recipe_indication: str | None = Field(
        default=None, description="Cooking time indication"
    )
    recipe_cost: str | None = Field(default=None, description="Cost indication")
    rank: str | None = Field(default=None, description="Ranking position")
    category_name: str | None = Field(default=None, description="Category name")


class RecipeHunterResult(BaseModel):
    recipes: list[RakutenRecipe] = Field(
        default_factory=list, description="Found recipes"
    )
    searched_categories: list[str] = Field(
        default_factory=list, description="Categories that were searched"
    )
    error_message: str | None = Field(
        default=None, description="Error message if any"
    )


class NutritionAdvice(BaseModel):
    mood_based_nutrients: list[str] = Field(
        default_factory=list,
        description="Nutrients recommended based on mood",
    )
    recommended_ingredients: list[str] = Field(
        default_factory=list,
        description="Ingredients recommended for the mood",
    )
    avoid_ingredients: list[str] = Field(
        default_factory=list,
        description="Ingredients to avoid for the mood",
    )
    advice_text: str = Field(
        default="", description="Overall nutrition advice text"
    )


class SeasonalRecommendation(BaseModel):
    current_season: str = Field(description="Current season (春/夏/秋/冬)")
    seasonal_ingredients: list[str] = Field(
        default_factory=list, description="Seasonal ingredients"
    )
    seasonal_dishes: list[str] = Field(
        default_factory=list, description="Recommended seasonal dishes"
    )
    seasonal_note: str = Field(
        default="", description="Additional note about seasonal recommendations"
    )
    reference_date: str = Field(description="Date used as reference (YYYY-MM-DD)")


class ProposedMeal(BaseModel):
    rank: int = Field(description="Proposal rank (1-3)")
    recipe: RakutenRecipe = Field(description="The proposed recipe")
    why_recommended: str = Field(description="Reason for recommendation based on mood")
    nutrition_point: str = Field(description="Nutrition highlight")
    seasonal_point: str = Field(description="Seasonal highlight")
    arrange_tip: str | None = Field(
        default=None, description="Arrangement tip for the recipe"
    )


class FinalProposal(BaseModel):
    greeting: str = Field(description="Personalized greeting based on mood")
    proposals: list[ProposedMeal] = Field(
        description="List of 3 proposed meals"
    )
    closing_message: str = Field(description="Closing message with encouragement")


class AgentLog(BaseModel):
    agent_name: str = Field(description="Agent display name (e.g., 'レシピハンター')")
    role: str = Field(description="Agent's role description")
    action: str = Field(description="What the agent did")
    result_summary: str = Field(description="Summary of the agent's result")


class ProcessingLog(BaseModel):
    phase1_summary: str = Field(description="Phase 1 mood analysis summary")
    agent_logs: list[AgentLog] = Field(description="Phase 2 per-agent logs")
    phase3_summary: str = Field(description="Phase 3 integration summary")
