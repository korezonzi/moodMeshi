import logging
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.agents.orchestrator import run_orchestrator

logger = logging.getLogger(__name__)

# Resolve paths relative to project root (works both locally and on Vercel)
BASE_DIR = Path(__file__).parent.parent

app = FastAPI(title="MoodMeshi", version="1.0.0")

app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/suggest", response_class=HTMLResponse)
async def suggest(request: Request, mood: str = Form(...)) -> HTMLResponse:
    try:
        result = await run_orchestrator(mood)
        return templates.TemplateResponse(
            "result.html",
            {"request": request, "result": result},
        )
    except Exception as e:
        logger.exception("Error in /suggest: %s", e)
        return HTMLResponse(
            content=f'<div class="error-message">エラーが発生しました: {e}</div>',
            status_code=500,
        )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
