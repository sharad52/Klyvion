# CLAUDE.md — Klyvion project context

This file summarizes everything decided and built so far, so any AI assistant
(Claude Code in VS Code) or new contributor has full context. Keep it in the
repo root and update it as the project evolves.

## What Klyvion is

Open-source (Apache-2.0) multi-voice **text-to-speech** toolkit in Python with
**zero-shot voice cloning**. Built to be published on GitHub and demoed live
at **https://klyvion.sharadbhandari.com.np**, linked from the portfolio
https://sharadbhandari.com.np.

The name was originally "VoiceForge"; it was fully renamed to **Klyvion**
(package, class, CLI, env vars, UI, docs). If any "voiceforge" string ever
appears, it's a bug.

## Current status (v0.1.0)

- ✅ 16/16 pytest tests passing (fast; no model download needed — uses a FakeEngine)
- ✅ CLI, Python API, and FastAPI HTTP server all working
- ✅ Web UI bundled and served at `/` by the API server
- ✅ English only (by design); 16 more languages pre-registered but disabled
- ✅ Docker + nginx + deployment guide written; **not yet deployed**
- ❌ Not yet pushed to GitHub; placeholder URLs `github.com/sharad52/klyvion`
  must be replaced with the real repo
- ❌ PyPI name availability not yet checked

## Architecture

```
klyvion/
├── klyvion/
│   ├── core.py                # Klyvion facade — main entry class
│   ├── config.py              # Settings; env vars prefixed KLYVION_
│   ├── languages.py           # language registry (en enabled; validate/normalize hooks)
│   ├── cli.py                 # `klyvion` command (argparse)
│   ├── engine/
│   │   ├── base.py            # TTSEngine ABC — THE extension seam
│   │   ├── xtts_engine.py     # default: Coqui XTTS v2 (neural, cloning, 17 langs)
│   │   └── pyttsx3_engine.py  # offline fallback, no cloning
│   ├── voices/
│   │   ├── registry.py        # presets man/woman/boy/girl + custom voices (JSON persisted)
│   │   └── cloning.py         # validates/cleans uploaded samples (6–30 s)
│   ├── audio/processing.py    # librosa/soundfile: resample, trim, normalize, pitch shift
│   ├── api/server.py          # FastAPI app (create_app factory)
│   └── webui/index.html       # single-file web UI (dark studio theme, ember accent,
│                              #   live waveform via Web Audio API)
├── tests/                     # pytest; FakeEngine, no downloads
├── examples/                  # basic_usage.py, clone_voice.py, api_client.py
├── docs/EXTENDING_LANGUAGES.md# 3-tier guide for adding languages
├── deploy/
│   ├── DEPLOYMENT.md          # full VPS deploy guide (see below)
│   └── nginx.conf             # reverse proxy with rate limiting
├── Dockerfile                 # CPU torch; bakes 2 GB XTTS model into image
├── docker-compose.yml         # binds 127.0.0.1:8000; klyvion-data volume
└── .github/workflows/ci.yml   # ruff + pytest on 3.10/3.11/3.12
```

## Key design decisions (and why)

1. **XTTS v2 as default engine** — writing a cloning-capable neural TTS from
   scratch is a research project; XTTS gives zero-shot cloning (6–30 s
   sample, no training) and 17 languages. The heavy DSP already runs in
   C++/CUDA under PyTorch.
2. **Engine abstraction (`engine/base.py`)** — two abstract methods
   (`synthesize`, `available_speakers`). New backends (Piper, Bark, a custom
   C++ engine via pybind11) = one subclass + one line in
   `engine/__init__.py::_REGISTRY`. Nothing else changes.
3. **boy/girl presets** — XTTS has no child speakers, so these are adult
   studio speakers ("Craig Gutsy", "Daisy Studious") with a +2.5–3 semitone
   pitch shift applied post-synthesis in `audio/processing.py`.
4. **English-only launch** — every synthesis call passes through
   `languages.validate()`; disabled languages raise `LanguageNotEnabledError`
   with a pointer to the guide. Tier A languages (all 16 XTTS-native) are a
   one-line enable + listen-test. Tier B adds a text normalizer via
   `register_normalizer()`. Tier C (e.g. Nepali) needs a new engine — Piper
   is the recommended path.
5. **Licensing nuance** — source is Apache-2.0, but XTTS v2 *model weights* are
   Coqui Public Model License (non-commercial for the weights). Noted in
   LICENSE and README. Fully-permissive alternative: swap in Piper.
6. **Voice storage** — cloned voices persist in `KLYVION_DATA_DIR`
   (default `~/.klyvion`, `/data` in Docker) with a JSON index. Cloned
   voices are currently **global across all users** of a server instance.

## Interfaces

```bash
# CLI
klyvion say "Hello" --voice man -o hello.wav
klyvion say-file article.txt --voice woman
klyvion clone alex ./sample.wav
klyvion voices
klyvion languages --all
klyvion remove alex
klyvion serve --host 0.0.0.0 --port 8000
```

```python
# Python
from klyvion import Klyvion
tts = Klyvion()
tts.speak("Hello", voice="girl", out_path="out.wav")
tts.clone_voice("alex", "sample.wav")
tts.speak("Cloned!", voice="alex")
```

HTTP: `GET /voices`, `POST /synthesize` (JSON → WAV), `POST /voices/{name}`
(multipart upload → clone), `DELETE /voices/{name}`, `GET /healthz`,
web UI at `/`, docs at `/docs`.

## Environment variables

| Var | Default | Notes |
|-----|---------|-------|
| `KLYVION_ENGINE` | `xtts` | or `pyttsx3` |
| `KLYVION_DEVICE` | `auto` | `cpu`/`cuda` |
| `KLYVION_DATA_DIR` | `~/.klyvion` | cloned voices |
| `KLYVION_OUTPUT_DIR` | `./outputs` | |
| `KLYVION_LANGUAGE` | `en` | |
| `KLYVION_MAX_TEXT_LEN` | `1000` (Docker: `500`) | API cap |
| `KLYVION_ENABLE_CLONING` | `1` | `0` = presets-only public demo |
| `KLYVION_MAX_UPLOAD_MB` | `15` | |
| `KLYVION_CORS_ORIGINS` | `*` | set to real domains in prod |

## Dev workflow

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # fast: tests only, no model
pytest -q                        # must stay green (16 tests)
ruff check . && black .          # before committing

pip install -e ".[all]"          # full: neural engine (~2 GB model on first use)
```

Known gotchas already fixed — don't reintroduce:
- FastAPI + `from __future__ import annotations`: pydantic request models must
  live at **module level** in `api/server.py`, not inside `create_app()`.
- docker-compose binds `127.0.0.1:8000` on purpose — only nginx is public.

## Deployment plan (see deploy/DEPLOYMENT.md for full detail)

Target: `klyvion.sharadbhandari.com.np` on a ~$10/mo VPS (needs 6–8 GB RAM;
CPU synthesis ≈ 20–60 s/paragraph — acceptable for a portfolio demo).

1. DNS: A record `klyvion` → VPS IP (Cloudflare proxy recommended)
2. VPS: ufw (22/80/443) + Docker
3. `docker compose build && docker compose up -d` (model baked into image;
   `COQUI_TOS_AGREED=1`)
4. nginx from `deploy/nginx.conf` — **keep the 6 req/min rate limit on
   /synthesize**; it's what protects the CPU
5. `certbot --nginx -d klyvion.sharadbhandari.com.np`
6. Portfolio nav: `<a href="https://klyvion.sharadbhandari.com.np">Klyvion — open-source TTS & voice cloning</a>`
   plus a "runs on a small CPU server, ~30 s per synthesis" note
7. Consider launching with `KLYVION_ENABLE_CLONING=0` (clones are global);
   free $0 alternative: Hugging Face Gradio Space + Cloudflare redirect

## Repo governance (adopted from the spec)

- **License: Apache-2.0** (switched from MIT). XTTS *weights* remain CPML — note kept in LICENSE/README.
- **Branches:** `main` (protected, releases only) ← `develop` (PRs land here) ← `feature/*`, `bugfix/*`, `hotfix/*`, `experiment/*`.
- **Merges:** squash + rebase only; PR titles must be valid Conventional Commits (they become the squash message).
- **Commits:** Conventional Commits (`feat(api): ...`, `fix(audio): ...`, `perf(tts): ...`); `!` + `BREAKING CHANGE:` footer for breaking.
- **CI status checks** (all required on `main`): `Lint` (ruff+black), `Type Check` (mypy), `Tests` (3.10/3.11/3.12), `Build`, `Security Scan` (bandit+pip-audit). All pass as of this commit — keep them green.
- **Community files:** issue forms (bug/feature/docs/perf; security routed to private advisories), PR template, CODEOWNERS (`* @sharad52`), SECURITY.md, CODE_OF_CONDUCT.md (Contributor Covenant 2.1 by reference), CHANGELOG.md (Keep a Changelog), dependabot (pip/actions/docker weekly), FUNDING.yml (commented until accounts exist).
- **Server-side setup** (labels, branch creation/protection, merge strategy, discussions, security features, milestones) is scripted: `REPO=sharad52/klyvion bash scripts/setup_github.sh`. Approval count defaults to 0 (solo maintainer can't approve own PRs); raise with `APPROVALS=2` when co-maintainers exist.
- **Social preview:** `assets/social-preview.png` (1280×640) — upload manually in Settings → General.
- **First release:** tag `v0.1.0-alpha`, mark as pre-release; roadmap milestones v0.2 (streaming API + language pack) → v0.5 (multi-engine routing, per-session voices) → v1.0 (stable API, PyPI).
- **Folder-structure mapping vs the spec:** the spec's generic `models/ + inference/` = our `engine/`; `config/` = `config.py`; `utils/` split into `audio/` + `voices/` (domain names beat generic ones); `streaming/` will be created with the v0.2 feature, not before; `benchmarks/` and `scripts/` added; `cli/` stays `cli.py` until it outgrows one file. Don't restructure working code to match the template — grow into it.

## Immediate TODO (in order)

1. `git init -b main`, create GitHub repo **sharad52/klyvion**, push, then run
   `scripts/setup_github.sh`; upload assets/social-preview.png; verify remaining
   placeholder URLs point to sharad52/klyvion
2. Check `klyvion` availability on PyPI; publish when ready
3. Do one real end-to-end run with the neural engine installed
   (`pip install -e ".[all]"` then `klyvion say "test" --voice man`) — CI
   never exercises the real model
4. Deploy per deploy/DEPLOYMENT.md
5. Roadmap ideas discussed: Gradio Space free demo, per-session voice
   scoping, language routing engine (XTTS + Piper per language),
   Nepali via Piper (Tier C), Dockerfile CUDA variant
