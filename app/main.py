import asyncio
import json
import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
                result, log = await run_orchestrator(
                    mood.strip(),
                    progress_callback,
                    user_id=user_id,
                )
                html = templates.env.get_template("result.html").render(
                    result=result, log=log
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


@app.get("/history")
async def history(request: Request) -> JSONResponse:
    """Return recent search sessions for the current web user."""
    if not settings.DATABASE_URL:
        return JSONResponse({"sessions": []})

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


@app.get("/favorites")
async def favorites(request: Request) -> JSONResponse:
    """Return favorited meals for the current web user."""
    if not settings.DATABASE_URL:
        return JSONResponse({"meals": []})

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


# Mount Slack event endpoint only when credentials are configured
if settings.SLACK_BOT_TOKEN and settings.SLACK_SIGNING_SECRET:
    from app.slack_bot import bolt_handler

    @app.post("/slack/events")
    async def slack_events(req: Request) -> object:
        return await bolt_handler.handle(req)
