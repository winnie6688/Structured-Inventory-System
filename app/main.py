from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as inventory_router
from app.config import settings

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(inventory_router)
app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
async def index_page() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")
