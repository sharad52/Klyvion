# Changelog

All notable changes to Klyvion are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0-alpha] - 2026-07-13

### Added
- `Klyvion` Python API: `speak()`, `clone_voice()`, `list_voices()`, `list_languages()`
- Voice presets: `man`, `woman`, `boy`, `girl` (child voices via post-synthesis pitch shift)
- Zero-shot voice cloning from 6–30 s samples (XTTS v2), with sample
  validation/cleanup and persisted voice registry
- Pluggable engine architecture (`TTSEngine` ABC): XTTS v2 (default) and
  pyttsx3 (offline fallback)
- Language registry: English enabled; 16 XTTS-native languages pre-registered
  behind `LanguageNotEnabledError` (see docs/EXTENDING_LANGUAGES.md)
- CLI: `say`, `say-file`, `clone`, `voices`, `languages`, `remove`, `serve`
- FastAPI HTTP server with bundled web UI, CORS, health check, text/upload limits
- Docker image (model baked in), docker-compose, rate-limited nginx config,
  deployment guide for klyvion.sharadbhandari.com.np
- Test suite (FakeEngine, no model download), GitHub Actions CI

[Unreleased]: https://github.com/sharad52/klyvion/compare/v0.1.0-alpha...HEAD
[0.1.0-alpha]: https://github.com/sharad52/klyvion/releases/tag/v0.1.0-alpha
