# Klyvion

**Open Source AI Text-to-Speech Engine** — multi-voice synthesis with
zero-shot voice cloning, in Python.

[![CI](https://github.com/sharad52/klyvion/actions/workflows/ci.yml/badge.svg)](https://github.com/sharad52/klyvion/actions)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

## Features

- 🎙️ Built-in voice presets: `man`, `woman`, `boy`, `girl`
- 🧬 **Custom voices**: upload a 6–30 second recording and speak in that voice
- 🖥️ Three interfaces: Python API, CLI, and an HTTP REST server (FastAPI)
- 🔌 Pluggable engines: neural **XTTS v2** (default) or a lightweight offline
  `pyttsx3` fallback — adding a new backend (Piper, Bark, or your own
  C/C++ engine via pybind11) means implementing one small class
- 🌍 **English in v0.1**, multilingual-ready: the XTTS engine speaks 17
  languages, and enabling one is often a one-line change — see
  [docs/EXTENDING_LANGUAGES.md](docs/EXTENDING_LANGUAGES.md)

## Installation

```bash
# Full neural engine with voice cloning (recommended, needs ~2 GB model download)
pip install "klyvion[neural]"

# Lightweight offline engine only (no cloning, robotic voices, zero downloads)
pip install "klyvion[lite]"

# Everything including the HTTP server
pip install "klyvion[all]"
```

From source:

```bash
git clone https://github.com/sharad52/klyvion
cd klyvion
pip install -e ".[all,dev]"
```

> **GPU**: XTTS runs on CPU but a CUDA GPU is ~10× faster. Set
> `KLYVION_DEVICE=cuda` or leave the default `auto`.

## Quick start

### Python

```python
from klyvion import Klyvion

tts = Klyvion()

# Preset voices
tts.speak("Hello, welcome to Klyvion!", voice="man",   out_path="man.wav")
tts.speak("Hello, welcome to Klyvion!", voice="girl",  out_path="girl.wav")

# Clone a custom voice from a user recording (6–30 s of clean speech)
tts.clone_voice("alex", "recordings/alex_sample.wav")
tts.speak("Hi, this is my cloned voice.", voice="alex", out_path="alex.wav")
```

### CLI

```bash
klyvion say "Hello world" --voice woman -o hello.wav
klyvion say-file article.txt --voice man
klyvion clone alex ./alex_sample.wav
klyvion say "I sound like Alex now" --voice alex
klyvion voices          # list presets + custom voices
klyvion languages --all # language support status
klyvion remove alex
```

### HTTP server

```bash
klyvion serve --host 0.0.0.0 --port 8000
```

```bash
# List voices
curl http://localhost:8000/voices

# Synthesize
curl -X POST http://localhost:8000/synthesize \
     -H "Content-Type: application/json" \
     -d '{"text": "Hello from the API", "voice": "woman"}' \
     --output hello.wav

# Upload a sample to create a custom voice
curl -X POST http://localhost:8000/voices/alex \
     -F "sample=@alex_sample.wav" \
     -F "description=Alex's voice"

# Use it
curl -X POST http://localhost:8000/synthesize \
     -d '{"text": "Cloned!", "voice": "alex"}' \
     -H "Content-Type: application/json" --output alex.wav
```

Interactive API docs are served at `http://localhost:8000/docs`.

## How voice cloning works

The default engine is **XTTS v2**, a multilingual zero-shot TTS model. "Zero-shot"
means no training loop: the model conditions on your reference recording at
inference time. Klyvion cleans the uploaded sample (mono, resample to
22.05 kHz, silence trimming, loudness normalization) and stores it under
`~/.klyvion/voices/` together with a JSON registry, so custom voices persist
across sessions.

The `boy` and `girl` presets are adult studio speakers with a small pitch shift
applied in post-processing, since XTTS ships no child speakers.

**Tips for good clones**

- 6–30 seconds of a *single* speaker, no music or background noise
- Natural, expressive speech beats flat reading
- 16-bit WAV or FLAC at ≥16 kHz works best (MP3 is accepted)

## Configuration

Environment variables (all optional):

| Variable                | Default        | Meaning                          |
|-------------------------|----------------|----------------------------------|
| `KLYVION_ENGINE`     | `xtts`         | `xtts` or `pyttsx3`              |
| `KLYVION_DEVICE`     | `auto`         | `auto`, `cpu`, `cuda`            |
| `KLYVION_DATA_DIR`   | `~/.klyvion`| Cloned-voice storage             |
| `KLYVION_OUTPUT_DIR` | `./outputs`    | Default synthesis output dir     |
| `KLYVION_LANGUAGE`   | `en`           | Default language code            |

## Project structure

```
klyvion/
├── klyvion/
│   ├── core.py               # Klyvion facade (main entry class)
│   ├── config.py             # Settings (env-var overridable)
│   ├── cli.py                # `klyvion` command
│   ├── engine/
│   │   ├── base.py           # TTSEngine abstract interface
│   │   ├── xtts_engine.py    # neural engine (cloning)
│   │   └── pyttsx3_engine.py # offline fallback
│   ├── voices/
│   │   ├── registry.py       # presets + persisted custom voices
│   │   └── cloning.py        # sample validation & cleanup
│   ├── audio/
│   │   └── processing.py     # resample, trim, normalize, pitch shift
│   └── api/
│       └── server.py         # FastAPI app
│   └── languages.py          # language registry (en enabled; 16 more ready)
├── docs/
│   └── EXTENDING_LANGUAGES.md# how to add a language (3-tier guide)
├── tests/                    # pytest suite (no model download needed)
├── examples/                 # runnable scripts
├── pyproject.toml
└── LICENSE                   # Apache-2.0 (see model-license note below)
```

## Adding a new engine

Implement `klyvion.engine.base.TTSEngine` (two methods) and register it in
`klyvion/engine/__init__.py`. This is also the seam for a native C/C++
engine: expose your `synthesize()` through pybind11 or ctypes and wrap it in a
subclass — nothing else in the project needs to change.

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

The test suite uses a fake engine, so it runs in seconds without downloading
any models.

## Streaming API

> 🚧 **Planned for v0.2.** Today `/synthesize` returns a complete WAV.
> Streaming (chunked audio over HTTP / WebSocket, so playback starts before
> synthesis finishes) is tracked in the v0.2 milestone — follow
> `feature/streaming-api`. The `TTSEngine` interface will gain an optional
> `synthesize_stream()` capability; engines that don't implement it keep
> working unchanged.

## Benchmarks

Reproducible latency numbers live in [benchmarks/](benchmarks/). Rough
expectations for XTTS v2: ~1–3 s per sentence on a modern GPU, ~20–60 s per
paragraph on a 4-vCPU server. Run `python benchmarks/bench_synthesis.py` on
your hardware and PRs with results tables are welcome.

## Roadmap

| Milestone | Focus |
|-----------|-------|
| **v0.1** (now) | Core API/CLI/server, 4 presets, cloning, English |
| **v0.2** | Streaming API, first Tier-A language pack (es/fr/de/hi), CHANGELOG automation |
| **v0.5** | Multi-engine routing (Piper for non-XTTS languages), per-session voice scoping |
| **v1.0** | Stable API, benchmark suite, PyPI release, signed releases |

## Deployment

A production deployment guide (Docker + nginx + HTTPS on a custom
subdomain, with rate limiting and abuse notes) lives in
[deploy/DEPLOYMENT.md](deploy/DEPLOYMENT.md). The HTTP server bundles a
ready-to-use web UI at `/`.

## Licensing

The Klyvion **source code** is Apache-2.0-licensed. Note that the optional XTTS v2
**model weights** downloaded by the neural engine are covered by the Coqui
Public Model License (CPML), which limits commercial use of the weights.
If you need a fully permissive stack for commercial deployment, plug in an
Apache/Apache-2.0-licensed engine (e.g. Piper) via the engine interface above.

## Ethics

Only clone voices you have permission to use. Cloning someone's voice without
consent may be illegal in your jurisdiction and is against the spirit of this
project. Consider disclosing when audio is synthetic.

## Contributing

Issues and PRs are welcome! Branch from `develop`, follow
[Conventional Commits](https://www.conventionalcommits.org/), and run
`make check` before submitting. Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).
Security reports go through [SECURITY.md](SECURITY.md), never public issues.
