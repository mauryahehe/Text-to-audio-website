"""Text-to-Voice converter: FastAPI backend using edge-tts. No database, nothing stored."""
from pathlib import Path

import edge_tts
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent
MAX_CHARS = 5000  # keep free hosting from being overloaded

app = FastAPI(title="Text to Voice")
_voices_cache = None


class TTSRequest(BaseModel):
    text: str
    voice: str = "en-US-AriaNeural"
    rate: int = Field(0, ge=-50, le=100)   # speed change in %
    pitch: int = Field(0, ge=-50, le=50)   # pitch change in Hz


@app.get("/")
async def home():
    # Used when running locally. On Vercel, files in public/ are served directly.
    return FileResponse(BASE_DIR / "public" / "index.html")


@app.get("/api/voices")
async def voices():
    global _voices_cache
    if _voices_cache is None:
        raw = await edge_tts.list_voices()
        _voices_cache = [
            {
                "name": v["ShortName"],
                "locale": v["Locale"],
                "gender": v["Gender"],
                "label": v.get("FriendlyName", v["ShortName"]),
            }
            for v in raw
        ]
        _voices_cache.sort(key=lambda v: (v["locale"], v["name"]))
    return _voices_cache


@app.post("/api/tts")
async def tts(req: TTSRequest):
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "Text is empty.")
    if len(text) > MAX_CHARS:
        raise HTTPException(400, f"Text too long. Max {MAX_CHARS} characters.")

    communicate = edge_tts.Communicate(
        text,
        req.voice,
        rate=f"{req.rate:+d}%",
        pitch=f"{req.pitch:+d}Hz",
    )

    audio = bytearray()
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    except Exception as e:
        raise HTTPException(502, f"Speech generation failed: {e}")

    if not audio:
        raise HTTPException(502, "No audio was generated. Try a different voice or text.")

    return Response(
        content=bytes(audio),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )
