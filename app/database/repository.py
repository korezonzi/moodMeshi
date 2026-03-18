"""CRUD functions for MoodMeshi database."""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.types import FinalProposal, MoodAnalysis
from app.database.connection import _get_session_factory
from app.database.models import ProposedMealRecord, SearchSession, UserPreference

logger = logging.getLogger(__name__)


@dataclass
class SessionSummary:
    id: int
    user_input: str
    mood_keywords: list[str]
    created_at: datetime
    meal_titles: list[str]


@dataclass
class FavoriteMeal:
    id: int
    recipe_title: str
    recipe_url: str | None
    food_image_url: str | None
    why_recommended: str | None
    category_name: str | None
    created_at: datetime


async def save_session(
    user_id: str,
    user_input: str,
    mood: MoodAnalysis,
    proposal: FinalProposal,
    slack_channel_id: str | None = None,
) -> int | None:
    """Save a search session and its proposed meals. Returns session ID or None on error."""
    factory = _get_session_factory()
    if factory is None:
        return None

    try:
        async with factory() as session:
            db_session = SearchSession(
                user_id=user_id,
                slack_channel_id=slack_channel_id,
                user_input=user_input,
                mood_keywords=mood.mood_keywords,
                target_categories=mood.target_categories,
                greeting=proposal.greeting,
                closing_message=proposal.closing_message,
                context_summary=proposal.context_summary,
            )
            session.add(db_session)
            await session.flush()  # get db_session.id

            for meal in proposal.proposals:
                recipe = meal.recipe
                meal_record = ProposedMealRecord(
                    session_id=db_session.id,
                    rank=meal.rank,
                    recipe_id=recipe.recipe_id or None,
                    recipe_title=recipe.recipe_title or "",
                    recipe_url=recipe.recipe_url or None,
                    food_image_url=recipe.food_image_url or None,
                    recipe_description=recipe.recipe_description or None,
                    recipe_indication=recipe.recipe_indication or None,
                    recipe_cost=recipe.recipe_cost or None,
                    category_name=recipe.category_name or None,
                    why_recommended=meal.why_recommended or None,
                    nutrition_point=meal.nutrition_point or None,
                    seasonal_point=meal.seasonal_point or None,
                    arrange_tip=meal.arrange_tip or None,
                )
                session.add(meal_record)

            await session.commit()
            return db_session.id
    except Exception:
        logger.exception("Failed to save session for user %s", user_id)
        return None


async def get_recent_sessions(user_id: str, limit: int = 5) -> list[SessionSummary]:
    """Get recent search sessions for a user."""
    factory = _get_session_factory()
    if factory is None:
        return []

    try:
        async with factory() as session:
            stmt = (
                select(SearchSession)
                .where(SearchSession.user_id == user_id)
                .order_by(SearchSession.created_at.desc())
                .limit(limit)
                .options(selectinload(SearchSession.meals))
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            summaries = []
            for row in rows:
                titles = [m.recipe_title for m in sorted(row.meals, key=lambda x: x.rank)]
                summaries.append(
                    SessionSummary(
                        id=row.id,
                        user_input=row.user_input,
                        mood_keywords=row.mood_keywords or [],
                        created_at=row.created_at,
                        meal_titles=titles,
                    )
                )
            return summaries
    except Exception:
        logger.exception("Failed to get sessions for user %s", user_id)
        return []


async def get_session_meals(session_id: int) -> list[ProposedMealRecord]:
    """Get all proposed meals for a session."""
    factory = _get_session_factory()
    if factory is None:
        return []

    try:
        async with factory() as session:
            stmt = (
                select(ProposedMealRecord)
                .where(ProposedMealRecord.session_id == session_id)
                .order_by(ProposedMealRecord.rank)
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())
    except Exception:
        logger.exception("Failed to get meals for session %s", session_id)
        return []


async def toggle_favorite(meal_id: int) -> bool:
    """Toggle is_favorited for a meal. Returns new favorited state or False on error."""
    factory = _get_session_factory()
    if factory is None:
        return False

    try:
        async with factory() as session:
            stmt = select(ProposedMealRecord).where(ProposedMealRecord.id == meal_id)
            result = await session.execute(stmt)
            meal = result.scalar_one_or_none()
            if meal is None:
                return False
            meal.is_favorited = not meal.is_favorited
            await session.commit()
            return meal.is_favorited
    except Exception:
        logger.exception("Failed to toggle favorite for meal %s", meal_id)
        return False


async def get_favorited_meals(user_id: str) -> list[FavoriteMeal]:
    """Get all favorited meals for a user."""
    factory = _get_session_factory()
    if factory is None:
        return []

    try:
        async with factory() as session:
            stmt = (
                select(ProposedMealRecord)
                .join(SearchSession, ProposedMealRecord.session_id == SearchSession.id)
                .where(SearchSession.user_id == user_id)
                .where(ProposedMealRecord.is_favorited == True)  # noqa: E712
                .order_by(ProposedMealRecord.created_at.desc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            return [
                FavoriteMeal(
                    id=row.id,
                    recipe_title=row.recipe_title,
                    recipe_url=row.recipe_url,
                    food_image_url=row.food_image_url,
                    why_recommended=row.why_recommended,
                    category_name=row.category_name,
                    created_at=row.created_at,
                )
                for row in rows
            ]
    except Exception:
        logger.exception("Failed to get favorited meals for user %s", user_id)
        return []


async def upsert_user_prefs(
    user_id: str,
    allergy_notes: str | None = None,
    preference_notes: str | None = None,
) -> bool:
    """Create or update user preferences. Returns True on success."""
    factory = _get_session_factory()
    if factory is None:
        return False

    try:
        async with factory() as session:
            stmt = select(UserPreference).where(UserPreference.user_id == user_id)
            result = await session.execute(stmt)
            prefs = result.scalar_one_or_none()

            if prefs is None:
                prefs = UserPreference(
                    user_id=user_id,
                    allergy_notes=allergy_notes,
                    preference_notes=preference_notes,
                )
                session.add(prefs)
            else:
                if allergy_notes is not None:
                    prefs.allergy_notes = allergy_notes
                if preference_notes is not None:
                    prefs.preference_notes = preference_notes

            await session.commit()
            return True
    except Exception:
        logger.exception("Failed to upsert prefs for user %s", user_id)
        return False


async def get_user_prefs(user_id: str) -> UserPreference | None:
    """Get user preferences. Returns None if not found or DB unavailable."""
    factory = _get_session_factory()
    if factory is None:
        return None

    try:
        async with factory() as session:
            stmt = select(UserPreference).where(UserPreference.user_id == user_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
    except Exception:
        logger.exception("Failed to get prefs for user %s", user_id)
        return None
