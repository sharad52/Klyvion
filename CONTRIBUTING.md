# Contributing to Klyvion

Thanks for your interest! This guide covers everything needed to land a PR.

## Development Setup

```bash
git clone https://github.com/sharad52/klyvion
cd klyvion
python -m venv .venv && source .venv/bin/activate
make install          # fast dev install (tests run without the 2 GB model)
make install-all      # optional: full neural engine
make check            # lint + typecheck + tests — what CI runs
```

Branch model: `main` (protected, releases only) ← `develop` (integration) ←
your branch. Name branches `feature/*`, `bugfix/*`, `hotfix/*`, or
`experiment/*`, e.g. `feature/streaming-api`, `bugfix/audio-buffer`.

## Coding Standards

- Python ≥ 3.10, formatted with **black**, linted with **ruff** (`make format`)
- Type hints on public functions; `mypy klyvion` must pass
- Keep the `TTSEngine` interface minimal — new engine features should be
  optional capabilities, not new required methods
- User-facing errors must say what to do next, not just what failed

## Testing

- `pytest` must stay green; add tests for every behavior change
- Tests must **not** download models — use `FakeEngine`
  (see `tests/test_klyvion.py`)
- Audio quality can't be asserted in CI: for synthesis-affecting changes,
  note in the PR that you listen-tested and with what input

## Pull Requests

- Target `develop`, keep one logical change per PR
- Fill in the PR template (description, related issue, checklist, testing,
  breaking changes, screenshots for UI)
- All status checks (Lint, Tests, Build, Type Check, Security Scan) must pass
- Merges are **squash or rebase only** — write the PR title as a valid
  conventional commit, since it becomes the squashed commit message

## Issue Reporting

Use the issue forms (Bug, Feature, Documentation, Performance).
**Security issues:** never open a public issue — use private vulnerability
reporting (see SECURITY.md). Questions and ideas belong in Discussions.

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(api): add streaming endpoint
fix(audio): eliminate playback delay
docs(readme): improve installation guide
perf(tts): reduce inference latency
test(voices): cover registry name validation
ci: add security scan job
refactor|style|build|chore: ...
```

Breaking changes: add `!` after the type (`feat(api)!:`) and a
`BREAKING CHANGE:` footer, and label the PR `breaking change`.

## Code of Conduct

All participation is governed by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
(Contributor Covenant 2.1).
