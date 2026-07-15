"""
Klyvion — Open-source multi-voice Text-to-Speech toolkit.

High-level usage:

    from klyvion import Klyvion

    tts = Klyvion()                       # loads default engine (XTTS v2)
    tts.speak("Hello world", voice="man", out_path="hello.wav")

    # Clone a custom voice from a user-provided sample
    tts.clone_voice(name="alex", sample_path="my_recording.wav")
    tts.speak("Now I sound like Alex!", voice="alex", out_path="alex.wav")
"""

from klyvion.config import Settings, get_settings
from klyvion.core import Klyvion
from klyvion.voices.registry import VoiceRegistry, VoicePreset
from klyvion import normalizers  # noqa: F401  (registers text normalizers)

__all__ = [
    "Klyvion",
    "VoiceRegistry",
    "VoicePreset",
    "Settings",
    "get_settings",
]

__version__ = "0.1.0"
