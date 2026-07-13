"""Command-line interface.

Examples:
    klyvion say "Hello world" --voice man -o hello.wav
    klyvion say-file article.txt --voice woman
    klyvion clone alex ./alex_sample.wav
    klyvion voices
    klyvion remove alex
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from klyvion import Klyvion, __version__


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="klyvion",
        description="Multi-voice text-to-speech with voice cloning.",
    )
    p.add_argument("--version", action="version", version=f"klyvion {__version__}")
    p.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    sub = p.add_subparsers(dest="command", required=True)

    say = sub.add_parser("say", help="Synthesize a line of text.")
    say.add_argument("text", help="Text to speak.")
    _add_synth_args(say)

    say_file = sub.add_parser("say-file", help="Synthesize a whole text file.")
    say_file.add_argument("path", type=Path, help="UTF-8 text file.")
    _add_synth_args(say_file)

    clone = sub.add_parser("clone", help="Create a custom voice from a recording.")
    clone.add_argument("name", help="Name for the new voice.")
    clone.add_argument("sample", type=Path, help="WAV/MP3/FLAC recording (6-30 s).")
    clone.add_argument("--description", default="", help="Optional description.")

    sub.add_parser("voices", help="List all available voices.")

    langs = sub.add_parser("languages", help="List supported languages.")
    langs.add_argument(
        "--all", action="store_true", help="Include languages not yet enabled."
    )

    remove = sub.add_parser("remove", help="Delete a custom voice.")
    remove.add_argument("name")

    serve = sub.add_parser("serve", help="Start the HTTP API server.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    return p


def _add_synth_args(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--voice", default="woman", help="Voice name (default: woman).")
    sp.add_argument("-o", "--out", type=Path, default=None, help="Output WAV path.")
    sp.add_argument("--language", default=None, help="Language code (default: en).")
    sp.add_argument("--speed", type=float, default=None, help="Speed multiplier.")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    tts = Klyvion()
    try:
        if args.command == "say":
            out = tts.speak(
                args.text,
                voice=args.voice,
                out_path=args.out,
                language=args.language,
                speed=args.speed,
            )
            print(out)

        elif args.command == "say-file":
            text = args.path.read_text(encoding="utf-8")
            out = tts.speak(
                text,
                voice=args.voice,
                out_path=args.out,
                language=args.language,
                speed=args.speed,
            )
            print(out)

        elif args.command == "clone":
            preset = tts.clone_voice(
                args.name, args.sample, description=args.description
            )
            print(f"Voice '{preset.name}' created. Try:")
            print(f'  klyvion say "Hello!" --voice {preset.name}')

        elif args.command == "voices":
            for v in tts.list_voices():
                tag = "custom" if v.kind == "custom" else "preset"
                print(f"{v.name:<15} [{tag}]  {v.description}")

        elif args.command == "languages":
            for lang in tts.list_languages(include_disabled=args.all):
                state = (
                    "enabled"
                    if lang.enabled
                    else (
                        "engine-native, not enabled"
                        if lang.engine_native
                        else "needs new engine"
                    )
                )
                print(f"{lang.code:<7} {lang.name:<22} [{state}]")

        elif args.command == "remove":
            tts.remove_voice(args.name)
            print(f"Removed voice '{args.name}'.")

        elif args.command == "serve":
            import uvicorn

            from klyvion.api.server import create_app

            uvicorn.run(create_app(), host=args.host, port=args.port)

    except (ValueError, KeyError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        tts.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
