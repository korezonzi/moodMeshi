import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
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


@app.post("/suggest")
async def suggest(request: Request, mood: str = Form(...)) -> StreamingResponse:
    if not mood or not mood.strip():
        async def error_gen():
            yield f'data: {json.dumps({"type": "error", "message": "気分を入力してください。"}, ensure_ascii=False)}\n\n'
        return StreamingResponse(error_gen(), media_type="text/event-stream")

    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def progress_callback(phase: str, message: str) -> None:
        await queue.put({"type": "progress", "phase": phase, "message": message})

    async def event_generator():
        async def run() -> None:
            try:
                result, log = await run_orchestrator(mood.strip(), progress_callback)
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

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
