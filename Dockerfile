# Klyvion — production image (CPU inference)
# Build:  docker build -t klyvion .
# Run:    docker run -p 8000:8000 -v klyvion-data:/data klyvion
FROM python:3.11-slim

# ffmpeg: decode user-uploaded MP3/FLAC samples; libsndfile: soundfile backend
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only torch keeps the image ~5 GB smaller than the CUDA build
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml README.md LICENSE ./
COPY klyvion ./klyvion
RUN pip install --no-cache-dir ".[neural,server]"

# Pre-download the XTTS v2 model into the image layer so the first user
# request isn't a 2 GB download. Accept the CPML license non-interactively.
ENV COQUI_TOS_AGREED=1
RUN python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"

ENV KLYVION_DATA_DIR=/data \
    KLYVION_OUTPUT_DIR=/tmp/outputs \
    KLYVION_DEVICE=cpu \
    KLYVION_MAX_TEXT_LEN=500
VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
  CMD curl -sf http://localhost:8000/healthz || exit 1

CMD ["python", "-m", "uvicorn", "--factory", "klyvion.api.server:create_app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
