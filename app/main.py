"""DeepLens — FastAPI Backend"""

import os
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from app.analyzer import DeepLensAnalyzer

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
ALLOWED_VIDEO = {"video/mp4", "video/quicktime", "video/x-msvideo", "video/webm", "video/x-matroska"}
ALLOWED = ALLOWED_IMAGE | ALLOWED_VIDEO

app = FastAPI(title="DeepLens", version="1.0.0")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

analyzer = DeepLensAnalyzer()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/logo.svg")
async def logo():
    return FileResponse(Path(__file__).parent / "static" / "logo.svg", media_type="image/svg+xml")


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Accepted images: JPEG, PNG, WebP, BMP, TIFF. "
                   f"Accepted videos: MP4, MOV, AVI, WebM, MKV.",
        )

    ext = Path(file.filename or "upload").suffix or ".bin"
    tmp_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"

    try:
        with open(tmp_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        is_video = file.content_type in ALLOWED_VIDEO
        if is_video:
            result = analyzer.analyze_video(str(tmp_path))
        else:
            result = analyzer.analyze_image(str(tmp_path))

        result["filename"] = file.filename
        return result

    finally:
        if tmp_path.exists():
            tmp_path.unlink()
