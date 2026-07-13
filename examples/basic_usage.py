"""Synthesize the same sentence with all four preset voices."""

from klyvion import Klyvion

tts = Klyvion()
sentence = "Klyvion turns text into natural sounding speech."

for voice in ("man", "woman", "boy", "girl"):
    path = tts.speak(sentence, voice=voice, out_path=f"outputs/{voice}.wav")
    print(f"{voice:>6} -> {path}")
