"""Clone a custom voice from a recording, then use it.

Usage: python examples/clone_voice.py my_recording.wav
"""

import sys
from klyvion import Klyvion

sample = sys.argv[1] if len(sys.argv) > 1 else "my_recording.wav"

tts = Klyvion()
preset = tts.clone_voice("myvoice", sample, description="Demo cloned voice")
print(f"Created voice '{preset.name}'")

out = tts.speak(
    "This sentence is spoken with the cloned voice.",
    voice="myvoice",
    out_path="outputs/cloned_demo.wav",
)
print(f"Wrote {out}")
