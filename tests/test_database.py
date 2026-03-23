"""Integration tests for database CRUD operations.

These tests require a real PostgreSQL database (Supabase).
Set DATABASE_URL in .env or as an environment variable to run them.
"""

import uuid

import pytest
import pytest_asyncio

from tests.conftest import make_mood, make_proposal, requires_db


@pytest_asyncio.fixture(autouse=True)
async def _setup_tables():
    """Create tables before tests, clean up test data after."""
    from app.database.connection import init_tables

    await init_tables()
    yield


@pytest.fixture()
def test_user_id() -> str:
    """Generate a unique user ID per test to avoid collisions."""
    return f"test-user-{uuid.uuid4().hex[:8]}"


# ── save_session + get_recent_sessions ──


@requires_db
@pytest.mark.asyncio
async def test_save_session_returns_id(test_user_id: str):
    from app.database.repository import save_session

    mood = make_mood()
    proposal = make_proposal()

    session_id = await save_session(test_user_id, mood.raw_input, mood, proposal)

    assert session_id is not None
    assert isinstance(session_id, int)


@requires_db
@pytest.mark.asyncio
async def test_get_recent_sessions(test_user_id: str):
    from app.database.repository import get_recent_sessions, save_session

    mood = make_mood()
    proposal = make_proposal(num_meals=2)
    await save_session(test_user_id, mood.raw_input, mood, proposal)

    sessions = await get_recent_sessions(test_user_id, limit=5)

    assert len(sessions) >= 1
    latest = sessions[0]
    assert latest.user_input == mood.raw_input
    assert latest.mood_keywords == mood.mood_keywords
    assert len(latest.meal_titles) == 2
    assert latest.meal_titles[0] == "テスト料理1"


# ── get_session_meals ──


@requires_db
@pytest.mark.asyncio
async def test_get_session_meals(test_user_id: str):
    from app.database.repository import get_session_meals, save_session

    mood = make_mood()
    proposal = make_proposal(num_meals=3)
    session_id = await save_session(test_user_id, mood.raw_input, mood, proposal)

    meals = await get_session_meals(session_id)

    assert len(meals) == 3
    assert meals[0].rank == 1
    assert meals[2].rank == 3
    assert meals[0].recipe_title == "テスト料理1"


# ── toggle_favorite + get_favorited_meals ──


@requires_db
@pytest.mark.asyncio
async def test_toggle_favorite(test_user_id: str):
    from app.database.repository import get_session_meals, save_session, toggle_favorite

    mood = make_mood()
    proposal = make_proposal(num_meals=1)
    session_id = await save_session(test_user_id, mood.raw_input, mood, proposal)

    meals = await get_session_meals(session_id)
    meal_id = meals[0].id

    # Initially not favorited
    assert meals[0].is_favorited is False

    # Toggle on
    result = await toggle_favorite(meal_id)
    assert result is True

    # Toggle off
    result = await toggle_favorite(meal_id)
    assert result is False


@requires_db
@pytest.mark.asyncio
async def test_get_favorited_meals(test_user_id: str):
    from app.database.repository import (
        get_favorited_meals,
        get_session_meals,
        save_session,
        toggle_favorite,
    )

    mood = make_mood()
    proposal = make_proposal(num_meals=3)
    session_id = await save_session(test_user_id, mood.raw_input, mood, proposal)

    meals = await get_session_meals(session_id)
    # Favorite the first and third meals
    await toggle_favorite(meals[0].id)
    await toggle_favorite(meals[2].id)

    favorites = await get_favorited_meals(test_user_id)

    fav_titles = {f.recipe_title for f in favorites}
    assert "テスト料理1" in fav_titles
    assert "テスト料理3" in fav_titles
    assert len([f for f in favorites if f.recipe_title.startswith("テスト料理")]) >= 2


# ── upsert_user_prefs + get_user_prefs ──


@requires_db
@pytest.mark.asyncio
async def test_upsert_and_get_user_prefs(test_user_id: str):
    from app.database.repository import get_user_prefs, upsert_user_prefs

    # Create
    ok = await upsert_user_prefs(test_user_id, allergy_notes="卵アレルギー")
    assert ok is True

    prefs = await get_user_prefs(test_user_id)
    assert prefs is not None
    assert prefs.allergy_notes == "卵アレルギー"
    assert prefs.preference_notes is None

    # Update
    ok = await upsert_user_prefs(test_user_id, preference_notes="辛いもの好き")
    assert ok is True

    prefs = await get_user_prefs(test_user_id)
    assert prefs.allergy_notes == "卵アレルギー"  # unchanged
    assert prefs.preference_notes == "辛いもの好き"


@requires_db
@pytest.mark.asyncio
async def test_get_user_prefs_not_found(test_user_id: str):
    from app.database.repository import get_user_prefs

    prefs = await get_user_prefs(test_user_id)
    assert prefs is None


# ── check_db_connection ──


@requires_db
@pytest.mark.asyncio
async def test_check_db_connection():
    from app.database.connection import check_db_connection

    is_ok, error = await check_db_connection()
    assert is_ok is True
    assert error == ""
