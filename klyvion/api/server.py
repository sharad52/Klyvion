"""HTTP API (FastAPI).

Run with:
    klyvion serve --host 0.0.0.0 --port 8000

Endpoints:
    GET  /voices                 -> list voices
    POST /synthesize             -> JSON {text, voice, language, speed} -> WAV
    POST /voices/{name}          -> multipart file upload -> clone voice
    DELETE /voices/{name}        -> remove a custom voice
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from klyvion import Klyvion

#: Demo-hardening knobs (all overridable via environment)
MAX_TEXT_LEN = int(os.environ.get("KLYVION_MAX_TEXT_LEN", "1000"))
ENABLE_CLONING = os.environ.get("KLYVION_ENABLE_CLONING", "1") == "1"
MAX_UPLOAD_MB = int(os.environ.get("KLYVION_MAX_UPLOAD_MB", "15"))

try:  # imported lazily elsewhere; module-level so FastAPI can resolve types
    from pydantic import BaseModel, Field

    class SynthesizeRequest(BaseModel):
        text: str = Field(..., min_length=1, max_length=MAX_TEXT_LEN)
        voice: str = "woman"
        language: "str | None" = None
        speed: "float | None" = Field(default=None, ge=0.5, le=2.0)

except ImportError:  # pragma: no cover - server extra not installed
    SynthesizeRequest = None  # type: ignore


def create_app():
    from fastapi import FastAPI, HTTPException, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse

    app = FastAPI(
        title="Klyvion API",
        description="Multi-voice text-to-speech with voice cloning.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("KLYVION_CORS_ORIGINS", "*").split(","),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )
    tts = Klyvion()

    webui = Path(__file__).resolve().parent.parent / "webui" / "index.html"

    @app.get("/", include_in_schema=False)
    def home():
        if webui.exists():
            return FileResponse(webui, media_type="text/html")
        raise HTTPException(status_code=404, detail="Web UI not bundled.")

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/voices")
    def list_voices():
        return [
            {
                "name": v.name,
                "kind": v.kind,
                "description": v.description,
            }
            for v in tts.list_voices()
        ]

    @app.post("/synthesize")
    def synthesize(req: SynthesizeRequest):
        try:
            out = tts.speak(
                req.text,
                voice=req.voice,
                language=req.language,
                speed=req.speed,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return FileResponse(out, media_type="audio/wav", filename=out.name)

    @app.post("/voices/{name}")
    async def clone_voice(
        name: str,
        sample: UploadFile = File(...),
        description: str = Form(""),
    ):
        if not ENABLE_CLONING:
            raise HTTPException(
                status_code=403,
                detail="Voice cloning is disabled on this server.",
            )
        payload = await sample.read()
        if len(payload) > MAX_UPLOAD_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"Sample larger than {MAX_UPLOAD_MB} MB.",
            )
        suffix = Path(sample.filename or "sample.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(payload)
            tmp_path = Path(tmp.name)
        try:
            preset = tts.clone_voice(name, tmp_path, description=description)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        finally:
            tmp_path.unlink(missing_ok=True)
        return {"name": preset.name, "kind": preset.kind}

    @app.delete("/voices/{name}")
    def remove_voice(name: str):
        try:
            tts.remove_voice(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        return {"removed": name}

    return app
