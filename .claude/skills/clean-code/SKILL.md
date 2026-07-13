---
name: clean-code
description: >-
  Klyvion's engineering standard for clean, object-oriented Python. Read and
  apply this BEFORE analyzing existing code or writing/refactoring any code in
  this repo, so every change follows the same SOLID/OOP conventions. Triggers
  whenever you add a class, module, engine backend, API route, or CLI command,
  or review a diff for quality.
---

# Clean Code & OOP standard for Klyvion

This skill is the single source of truth for *how code should look and be
structured* in Klyvion. When you analyze the codebase or implement a feature,
match these rules. When an existing file already follows a stricter local
pattern, follow the file.

## 0. Prime directives

1. **Match the surrounding code.** Comment density, naming, docstring style,
   and idioms already in a file win over any rule here.
2. **Small, single-purpose units.** A function does one thing; a class models
   one concept. If you can't name it without "and", split it.
3. **Depend on abstractions, not implementations.** The engine layer
   (`engine/base.py::TTSEngine`) is the reference pattern — mimic it.
4. **Fail loudly with typed errors.** Never swallow exceptions or return
   sentinel `None` where a raise is correct.

## 1. SOLID — how it maps to this repo

- **S — Single Responsibility.** `config.py` holds settings; `audio/processing.py`
  does DSP; `voices/registry.py` persists voices. Don't leak responsibilities
  across these seams. A new concern → a new module, not a bag of helpers.
- **O — Open/Closed.** Extend behavior by adding a subclass or registry entry,
  never by editing a working `if/elif` chain. New TTS backend = one
  `TTSEngine` subclass + one line in `engine/__init__.py::_REGISTRY`.
- **L — Liskov Substitution.** Any `TTSEngine` subclass must honor the base
  contract: `synthesize(...)` returns audio, `available_speakers()` returns a
  list. No subclass may narrow accepted inputs or raise where the base promises
  a value.
- **I — Interface Segregation.** Keep abstract base classes minimal (the two
  abstract methods on `TTSEngine` are the ceiling, not the floor). Don't force
  implementers to stub methods they don't use.
- **D — Dependency Inversion.** High-level code (`core.py::Klyvion`, the API,
  the CLI) depends on the `TTSEngine` abstraction and `Settings`, not on XTTS
  or pyttsx3 directly. Inject dependencies through constructors; resolve
  concrete engines via the registry.

## 2. Object-oriented design rules

- **Composition over inheritance.** Inherit only to satisfy an abstract
  contract (e.g. `TTSEngine`). Otherwise compose collaborators.
- **Encapsulate state.** Prefix internal attributes with `_`; expose read-only
  views via `@property` (see `Settings.voices_dir`). No mutable public
  attributes that invariants depend on.
- **Constructors do no heavy work.** Loading a 2 GB model, hitting the network,
  or touching disk belongs in an explicit method or lazy `@property`, not
  `__init__`. Keep object construction cheap and testable.
- **Prefer immutability.** Use `@dataclass` (frozen where practical) for value
  objects. Don't mutate arguments passed in.
- **One public entry class per subsystem** (the Facade pattern — `Klyvion` is
  the facade over engine + voices + audio). Callers use the facade; internals
  stay internal.

## 3. Python specifics (non-negotiable in this repo)

- `from __future__ import annotations` at the top of every module.
- **Full type hints** on all public functions, methods, and dataclass fields.
  `mypy` is a required CI check — keep it clean.
- **Google-style docstrings** on every public module, class, and function
  (see `config.py::Settings` for the house style). Document `Args`, `Returns`,
  `Raises`.
- **Line length 88**; format with `black`; lint with `ruff`. Run both before
  finishing (`ruff check . && black .`).
- **No `print` in library code** — use the `logging` module. `print` is only
  acceptable in the CLI's user-facing output.
- Use `pathlib.Path`, never string path concatenation.
- Guard optional dependencies with `try/except ImportError` at module level and
  raise a clear message telling the user which extra to install (pattern already
  in `api/server.py`).

## 4. Naming

- Classes `PascalCase`; functions/variables `snake_case`; constants
  `UPPER_SNAKE`; internal helpers `_leading_underscore`.
- Names state intent, not type: `voice_registry`, not `vr` or `dict1`.
- Custom exceptions end in `Error` and subclass a project base
  (e.g. `LanguageNotEnabledError`). Raise the specific type, not bare
  `Exception`.

## 5. Error handling & validation

- Validate at the boundary (CLI args, API request models, uploaded samples),
  then trust internal data.
- Never `except:` bare or `except Exception: pass`. Catch the narrowest type,
  add context, and re-raise or log.
- User-facing errors (API/CLI) must be actionable: say what was wrong and how
  to fix it (the language-guide pointer is the model to follow).

## 6. Testing (a change isn't done until tests are)

- Every new public behavior gets a `pytest` test. The suite must stay green
  (currently 16 tests) and must not require a model download — use the
  `FakeEngine` seam.
- Test behavior through the public interface, not private methods.
- One logical assertion per test; name tests `test_<unit>_<condition>_<expectation>`.

## 7. Comments

- Comment *why*, never *what* the code already says. Delete commented-out code.
- No TODOs without a tracked issue reference.

## Review checklist (run before declaring work complete)

- [ ] New backend/behavior added by extension (subclass/registry), not by editing a working branch
- [ ] Public API fully type-hinted + Google docstring
- [ ] No heavy work in `__init__`; dependencies injected
- [ ] Internal state encapsulated; only intended surface is public
- [ ] Typed exceptions, no bare/silent catches, actionable messages
- [ ] `ruff check .` and `black .` clean; `mypy` clean
- [ ] Tests added, run without model download, suite green
- [ ] No secrets, keys, or absolute local paths committed
