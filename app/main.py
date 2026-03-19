import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.agents.orchestrator import run_orchestrator
from app.config import settings

logger = logging.getLogger(__name__)

# Resolve paths relative to project root (works both locally and on Vercel)
BASE_DIR = Path(__file__).parent.parent

app = FastAPI(title="MoodMeshi", version="1.0.0")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


_WEB_USER_COOKIE = "moodmeshi_uid"


def _get_or_create_user_id(request: Request) -> tuple[str, bool]:
    """Return (user_id, is_new). is_new=True when a new UUID was generated."""
    uid = request.cookies.get(_WEB_USER_COOKIE)
    if uid:
        return uid, False
    return str(uuid.uuid4()), True


@app.post("/suggest")
async def suggest(request: Request, mood: str = Form(...)) -> StreamingResponse:
    if not mood or not mood.strip():
        async def error_gen():
            yield f'data: {json.dumps({"type": "error", "message": "気分を入力してください。"}, ensure_ascii=False)}\n\n'
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    user_id, is_new_user = _get_or_create_user_id(request)

    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress_callback(phase: str, message: str) -> None:
        await queue.put({"type": "progress", "phase": phase, "message": message})

    async def event_generator():
        async def run() -> None:
            try:
                result, log, session_id = await run_orchestrator(
                    mood.strip(),
                    progress_callback,
                    user_id=user_id,
                )
                meal_id_map: dict[int, int] = {}
                if session_id and settings.DATABASE_URL:
                    from app.database import repository
                    meals = await repository.get_session_meals(session_id)
                    meal_id_map = {m.rank: m.id for m in meals}
                html = templates.env.get_template("result.html").render(
                    result=result, log=log, meal_id_map=meal_id_map
                )
                await queue.put({"type": "complete", "html": html})
            except Exception as e:
                logger.exception("Error in /suggest: %s", e)
                await queue.put({"type": "error", "message": str(e)})
            finally:
                await queue.put(None)

        asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    response = StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    if is_new_user:
        response.set_cookie(
            _WEB_USER_COOKIE,
            user_id,
            max_age=60 * 60 * 24 * 365,  # 1 year
            httponly=True,
            samesite="lax",
        )
    return response


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/health/rakuten")
async def health_rakuten() -> JSONResponse:
    """Test Rakuten Recipe API connectivity."""
    try:
        from app.tools.rakuten_recipe import fetch_category_ranking
        result = await fetch_category_ranking(category_id="34")
        count = len(result.get("result", []))
        return JSONResponse({"ok": True, "recipe_count": count, "sample_title": result.get("result", [{}])[0].get("recipeTitle", "") if count > 0 else None})
    except Exception as e:
        logger.exception("Rakuten API health check failed")
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/health/db")
async def health_db() -> JSONResponse:
    """Check database connectivity and return detailed status for debugging."""
    if not settings.DATABASE_URL:
        return JSONResponse({"ok": False, "error": "DATABASE_URL is not set"})
    from app.database.connection import check_db_connection
    ok, error = await check_db_connection()
    return JSONResponse({"ok": ok, "error": error or None, "url_prefix": settings.DATABASE_URL[:30] + "..."})


@app.get("/history")
async def history(request: Request) -> JSONResponse:
    """Return recent search sessions for the current web user."""
    if not settings.DATABASE_URL:
        return JSONResponse({"sessions": []})

    try:
        user_id, _ = _get_or_create_user_id(request)
        from app.database import repository
        sessions = await repository.get_recent_sessions(user_id, limit=5)
        data = [
            {
                "id": s.id,
                "user_input": s.user_input,
                "mood_keywords": s.mood_keywords,
                "created_at": s.created_at.isoformat(),
                "meal_titles": s.meal_titles,
            }
            for s in sessions
        ]
        return JSONResponse({"sessions": data})
    except Exception as e:
        logger.exception("Error in GET /history: %s", e)
        return JSONResponse({"sessions": [], "error": str(e)})


class FavoriteToggleRequest(BaseModel):
    meal_id: int


@app.post("/favorites/toggle")
async def favorites_toggle(request: Request, body: FavoriteToggleRequest) -> JSONResponse:
    """Toggle favorite state for a meal."""
    if not settings.DATABASE_URL:
        return JSONResponse({"is_favorited": False})

    try:
        from app.database import repository
        new_state = await repository.toggle_favorite(body.meal_id)
        return JSONResponse({"is_favorited": new_state})
    except Exception as e:
        logger.exception("Error in POST /favorites/toggle: %s", e)
        return JSONResponse({"is_favorited": False, "error": str(e)})


@app.get("/preferences")
async def get_preferences(request: Request) -> JSONResponse:
    """Return current user preferences."""
    if not settings.DATABASE_URL:
        return JSONResponse({"allergy_notes": None, "preference_notes": None, "db_available": False})

    try:
        user_id, _ = _get_or_create_user_id(request)
        from app.database import repository
        prefs = await repository.get_user_prefs(user_id)
        return JSONResponse({
            "allergy_notes": prefs.allergy_notes if prefs else None,
            "preference_notes": prefs.preference_notes if prefs else None,
            "db_available": True,
        })
    except Exception as e:
        logger.exception("Error in GET /preferences: %s", e)
        return JSONResponse({"allergy_notes": None, "preference_notes": None, "db_available": False, "error": str(e)})


class PreferencesRequest(BaseModel):
    allergy_notes: str
    preference_notes: str


@app.post("/preferences")
async def save_preferences(request: Request, body: PreferencesRequest) -> JSONResponse:
    """Save user preferences."""
    if not settings.DATABASE_URL:
        return JSONResponse({"ok": False})

    try:
        user_id, _ = _get_or_create_user_id(request)
        from app.database import repository
        ok = await repository.upsert_user_prefs(
            user_id,
            allergy_notes=body.allergy_notes or None,
            preference_notes=body.preference_notes or None,
        )
        return JSONResponse({"ok": ok})
    except Exception as e:
        logger.exception("Error in POST /preferences: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})


@app.get("/favorites")
async def favorites(request: Request) -> JSONResponse:
    """Return favorited meals for the current web user."""
    if not settings.DATABASE_URL:
        return JSONResponse({"meals": []})

    try:
        user_id, _ = _get_or_create_user_id(request)
        from app.database import repository
        meals = await repository.get_favorited_meals(user_id)
        data = [
            {
                "id": m.id,
                "recipe_title": m.recipe_title,
                "recipe_url": m.recipe_url,
                "food_image_url": m.food_image_url,
                "why_recommended": m.why_recommended,
                "category_name": m.category_name,
                "created_at": m.created_at.isoformat(),
            }
            for m in meals
        ]
        return JSONResponse({"meals": data})
    except Exception as e:
        logger.exception("Error in GET /favorites: %s", e)
        return JSONResponse({"meals": [], "error": str(e)})


# Mount Slack event endpoint only when credentials are configured
if settings.SLACK_BOT_TOKEN and settings.SLACK_SIGNING_SECRET:
    from app.slack_bot import bolt_handler

    @app.post("/slack/events")
    async def slack_events(req: Request) -> object:
        return await bolt_handler.handle(req)
