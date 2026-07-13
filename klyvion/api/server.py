"""HTTP API (FastAPI).

Run with:
    klyvion serve --host 0.0.0.0 --port 8000

Endpoints:
    GET  /voices                 -> list voices
    POST /synthesize             -> JSON {text, voice, ...} -> {audio_id, urls}
    GET  /audio/{id}             -> stream generated audio for preview (open)
    GET  /download/{id}          -> download the WAV (login required)
    POST /voices/{name}          -> multipart file upload -> clone voice
    DELETE /voices/{name}        -> remove a custom voice
    /auth/*                      -> registration, login, Google OAuth, logout

Anyone may generate and preview audio; downloading the file requires a logged-in
session (username/password or Google). See :mod:`klyvion.auth`.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import uuid
from pathlib import Path

from klyvion import Klyvion

logger = logging.getLogger(__name__)

#: Demo-hardening knobs (all overridable via environment)
MAX_TEXT_LEN = int(os.environ.get("KLYVION_MAX_TEXT_LEN", "1000"))
ENABLE_CLONING = os.environ.get("KLYVION_ENABLE_CLONING", "1") == "1"
MAX_UPLOAD_MB = int(os.environ.get("KLYVION_MAX_UPLOAD_MB", "15"))

#: Generated-clip identifiers: a voice slug plus a random suffix. The regex is
#: also the guard against path traversal when resolving a clip back to a file.
_AUDIO_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,80}$")

try:  # imported lazily elsewhere; module-level so FastAPI can resolve types
    from pydantic import BaseModel, Field

    class SynthesizeRequest(BaseModel):
        text: str = Field(..., min_length=1, max_length=MAX_TEXT_LEN)
        voice: str = "woman"
        language: "str | None" = None
        speed: "float | None" = Field(default=None, ge=0.5, le=2.0)

except ImportError:  # pragma: no cover - server extra not installed
    SynthesizeRequest = None  # type: ignore


def _new_audio_id(voice: str) -> str:
    """Return a fresh, filesystem-safe id for one generated clip."""
    slug = re.sub(r"[^a-zA-Z0-9_\-]", "", voice)[:32] or "audio"
    return f"{slug}-{uuid.uuid4().hex[:12]}"


def create_app(tts: Klyvion | None = None):
    """Build the FastAPI app.

    Args:
        tts: an optional pre-built :class:`~klyvion.core.Klyvion` facade. Tests
            inject one backed by a fake engine and a temp data dir; in
            production it is created from process settings.
    """
    from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
    from starlette.middleware.sessions import SessionMiddleware

    from klyvion.auth import AuthService, User, build_auth_router
    from klyvion.auth.router import current_user_dependency

    tts = tts or Klyvion()
    settings = tts.settings

    app = FastAPI(
        title="Klyvion API",
        description="Multi-voice text-to-speech with voice cloning.",
        version="0.1.0",
    )

    # Session middleware backs the Google OAuth state/nonce round-trip. Reuse
    # the same secret as the session tokens; fall back to an ephemeral one.
    secret_key = settings.secret_key or AuthService.generate_secret()
    if not settings.secret_key:
        logger.warning(
            "KLYVION_SECRET_KEY is not set — using an ephemeral key. "
            "Sessions will not survive a server restart."
        )
    app.add_middleware(SessionMiddleware, secret_key=secret_key, same_site="lax")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("KLYVION_CORS_ORIGINS", "*").split(","),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    auth_service = AuthService.from_settings(settings, secret_key=secret_key)
    app.include_router(build_auth_router(auth_service, settings))
    get_current_user = current_user_dependency(auth_service)

    webui = Path(__file__).resolve().parent.parent / "webui" / "index.html"

    def _resolve_clip(audio_id: str) -> Path:
        if not _AUDIO_ID_RE.match(audio_id):
            raise HTTPException(status_code=400, detail="Invalid audio id.")
        out_dir = settings.output_dir.resolve()
        path = (out_dir / f"{audio_id}.wav").resolve()
        if out_dir not in path.parents or not path.exists():
            raise HTTPException(status_code=404, detail="Audio not found or expired.")
        return path

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
            {"name": v.name, "kind": v.kind, "description": v.description}
            for v in tts.list_voices()
        ]

    @app.post("/synthesize")
    def synthesize(req: SynthesizeRequest):
        """Generate audio and return its ids. Open to everyone."""
        audio_id = _new_audio_id(req.voice)
        out = settings.output_dir / f"{audio_id}.wav"
        try:
            tts.speak(
                req.text,
                voice=req.voice,
                out_path=out,
                language=req.language,
                speed=req.speed,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {
            "audio_id": audio_id,
            "preview_url": f"/audio/{audio_id}",
            "download_url": f"/download/{audio_id}",
        }

    @app.get("/audio/{audio_id}")
    def preview_audio(audio_id: str):
        """Stream a clip inline for in-browser playback. Open to everyone."""
        return FileResponse(_resolve_clip(audio_id), media_type="audio/wav")

    @app.get("/download/{audio_id}")
    def download_audio(audio_id: str, user: User = Depends(get_current_user)):
        """Download a clip as a file attachment. Requires a logged-in session."""
        path = _resolve_clip(audio_id)
        return FileResponse(path, media_type="audio/wav", filename=f"{audio_id}.wav")

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
