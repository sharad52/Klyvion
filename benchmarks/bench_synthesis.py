"""Measure synthesis latency and real-time factor.

Requires the neural engine: pip install -e ".[neural]"
"""

import time
import wave
from pathlib import Path

from klyvion import Klyvion

SENTENCES = [
    "Hello, this is a short benchmark sentence.",
    "Klyvion converts text into natural sounding speech, "
    "and this sentence is deliberately a little bit longer "
    "to measure how latency scales with input length.",
]


def audio_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def main() -> None:
    tts = Klyvion()
    print(f"{'chars':>6} {'synth_s':>8} {'audio_s':>8} {'RTF':>6}")
    for text in SENTENCES:
        out = Path(f"/tmp/bench_{len(text)}.wav")
        t0 = time.perf_counter()
        tts.speak(text, voice="woman", out_path=out)
        dt = time.perf_counter() - t0
        dur = audio_seconds(out)
        print(f"{len(text):>6} {dt:>8.2f} {dur:>8.2f} {dt / dur:>6.2f}")


if __name__ == "__main__":
    main()
