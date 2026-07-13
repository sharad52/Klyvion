# Extending Klyvion to Other Languages

Klyvion v0.1 ships English-only, but the architecture was built for
multilingual support from day one. This guide explains exactly where language
lives in the codebase and how to add a new one, from a 5-minute change to a
full custom-model integration.

## Where language lives in the code

Language touches exactly four places — nothing else needs to change:

```
klyvion/languages.py      # the registry: which languages are enabled
klyvion/core.py           # validates + normalizes text before synthesis
klyvion/engine/*.py       # the engine that must actually speak it
tests/                       # per-language smoke tests
```

Every synthesis call flows through `languages.validate()` (rejects disabled
codes with a helpful error) and `languages.normalize_text()` (per-language
text cleanup hook). This means adding a language never requires touching the
CLI, the HTTP API, or the voice registry — they inherit it automatically.

## The three tiers

Before starting, identify which tier your target language falls into. Run
`klyvion languages --all` to see the current status of every known code.

| Tier | Meaning | Effort |
|------|---------|--------|
| **A** | XTTS v2 speaks it natively, Latin-like text | ~5 minutes |
| **B** | XTTS-native, but text needs normalization (numbers, dates, script quirks) | hours–days |
| **C** | Not in XTTS at all (e.g. Nepali, Bengali, Swahili) | days–weeks |

XTTS v2 natively supports: `en es fr de it pt pl tr ru nl cs ar zh-cn ja hu ko hi`.

---

## Tier A: enabling an engine-native language

Example: enabling **Spanish**.

**Step 1.** In `klyvion/languages.py`, flip the flag:

```python
"es": Language("es", "Spanish", enabled=True, engine_native=True),
```

**Step 2.** Add a smoke test in `tests/test_languages.py`:

```python
def test_spanish_enabled(forge):
    out = forge.speak("Hola, ¿cómo estás?", voice="woman", language="es",
                      out_path=forge.settings.output_dir / "es.wav")
    assert out.exists()
```

**Step 3.** Listen-test manually with real audio (CI can't judge quality):

```bash
klyvion say "El rápido zorro marrón salta sobre el perro perezoso." \
    --voice man --language es -o es_test.wav
```

Check: numbers ("1995", "3,50 €"), abbreviations ("Sr.", "etc."), and
question intonation. If any of these sound wrong, the language is actually
Tier B — continue below.

**Step 4 (recommended).** Add native reference samples. The preset voices
(`man`, `woman`, ...) are English studio speakers; they *will* speak Spanish,
but with a slight accent. For accent-free presets, add per-language reference
WAVs under `assets/reference_voices/es/` and register them as presets, or
document that users should clone a native speaker's voice.

That's it. The CLI (`--language es`), the Python API and the HTTP endpoint all
work immediately.

---

## Tier B: languages needing text normalization

TTS models are bad at reading raw digits, dates, currencies, and
abbreviations — especially outside English. The fix is a **text normalizer**:
a function that expands "Dr. Müller zahlte 42 €" into
"Doktor Müller zahlte zweiundvierzig Euro" *before* the model sees it.

Klyvion has a plugin hook for exactly this:

```python
# klyvion/normalizers/de.py
from klyvion.languages import register_normalizer

def normalize_german(text: str) -> str:
    text = expand_numbers_de(text)        # 42 -> zweiundvierzig
    text = expand_abbreviations_de(text)  # Dr. -> Doktor
    text = expand_currency_de(text)       # 42 € -> zweiundvierzig Euro
    return text

register_normalizer("de", normalize_german)
```

Don't write number expansion by hand — use existing libraries:

- **num2words** — number-to-words in 40+ languages (MIT)
- **anyascii / unidecode** — transliteration fallback
- For CJK languages, a word segmenter helps prosody (e.g. **jieba** for
  Chinese, **fugashi/MeCab** for Japanese)

Checklist for a Tier B PR:

1. Enable the language in `languages.py` (as in Tier A)
2. Add the normalizer module and `register_normalizer()` call
3. Import the normalizer in `klyvion/__init__.py` so registration runs
4. Unit-test the normalizer *as pure text-in/text-out* — these tests are fast
   and need no model:

```python
def test_german_numbers():
    assert normalize_german("42 €") == "zweiundvierzig Euro"
```

5. Listen-test with sentences containing digits, dates, ordinals, units,
   URLs, and mixed-language fragments (English loanwords are common failure
   points)

**Right-to-left scripts (Arabic, Hebrew):** the model handles RTL text
directly — do *not* reverse the string. Do normalize Arabic-Indic digits
(٤٢ → expanded words) and strip tatweel/kashida characters.

---

## Tier C: languages the engine doesn't support

For languages absent from XTTS (Nepali, Bengali, Vietnamese, Swahili, ...)
you have three paths, in increasing order of effort:

### Path 1: swap in an engine that already supports it

Check whether [Piper](https://github.com/rhasspy/piper) (Apache-2.0-licensed, 30+
languages), Meta MMS-TTS (1,100+ languages, CC-BY-NC), or Facebook's
fairseq models cover your language. If yes, write a new engine class — this
is the seam the project was designed around:

```python
# klyvion/engine/piper_engine.py
from klyvion.engine.base import TTSEngine

class PiperEngine(TTSEngine):
    supports_cloning = False   # Piper has fixed voices

    def __init__(self, device="auto"):
        ...load the .onnx voice model...

    def synthesize(self, text, out_path, *, speaker=None,
                   speaker_wav=None, language="en", speed=1.0):
        ...run inference, write WAV...
        return out_path

    def available_speakers(self):
        return ["ne_NP-google-medium"]
```

Register it in `klyvion/engine/__init__.py`:

```python
_REGISTRY["piper"] = "klyvion.engine.piper_engine:PiperEngine"
```

Then mark the language enabled with `engine_native=False` and document which
engine it requires. Users select it with `KLYVION_ENGINE=piper`.

**Mixed deployments:** a future improvement (good first issue!) is a routing
engine that picks a backend per language — XTTS for its 17, Piper for the
rest — behind a single `TTSEngine` facade.

### Path 2: fine-tune XTTS on the new language

XTTS can be fine-tuned on new languages given ~50-200 hours of transcribed
speech. This preserves voice cloning. Rough recipe:

1. Collect a corpus: Common Voice (Mozilla) and OpenSLR host free datasets
   for many low-resource languages
2. Extend the tokenizer's character/phoneme coverage for the new script
3. Fine-tune using the coqui-tts training recipes (GPU required, days of
   training)
4. Ship the checkpoint and load it in `XTTSEngine` via a custom model path

This is research-adjacent work — open a GitHub Discussion first so effort
isn't duplicated.

### Path 3: phoneme bridging (quick, lossy)

As a stopgap, transliterate the language into the phonetics of a supported
one (e.g. romanized Nepali spoken through the Hindi voice, since the
phonologies overlap). Quality is mediocre but sometimes acceptable for
prototypes. Implement it as a normalizer that transliterates, and document
the limitation loudly.

---

## Language-aware voice presets

`VoicePreset` is language-agnostic today. When you add languages, consider
these optional enhancements (all backward-compatible):

- Add a `language: str | None` field to `VoicePreset` so a cloned voice
  remembers its speaker's native language as the synthesis default
- Namespace preset reference audio as
  `assets/reference_voices/<lang>/<preset>.wav`
- Warn (don't fail) when a voice cloned from language X is asked to speak
  language Y — XTTS supports *cross-lingual* cloning and it usually works,
  but with an accent

## Testing standards for language PRs

Every language PR should include:

1. **Registry test** — the code validates and appears in `klyvion languages`
2. **Normalizer unit tests** (if Tier B) — pure text, no model, runs in CI
3. **A pinned "golden sentences" file** — `tests/golden/<code>.txt` with
   10-20 tricky sentences (numbers, dates, questions, loanwords) used for
   manual listen-testing before release
4. **README note** — add the language to the supported table

CI never downloads the 2 GB model, so audio quality checks stay manual.
A maintainer will listen-test before merging.

## FAQ

**Why not just enable all 17 XTTS languages right now?**
Because "the model accepts the code" ≠ "the output is good". Each language
needs normalization review and listen-testing. Shipping them enabled-but-bad
hurts users more than a clear "not yet" error, which is what
`LanguageNotEnabledError` gives them today (with a pointer to this guide).

**Can one sentence mix languages?**
XTTS handles short code-switching (an English brand name inside a German
sentence) reasonably. Full bilingual sentences need sentence-splitting by
language and per-segment synthesis — a nice future feature.

**Does voice cloning work across languages?**
Yes — clone from an English recording, synthesize in French. The timbre
transfers; the accent will sound slightly non-native.
