"""Engine factory: turn a settings string into a concrete engine."""

from __future__ import annotations

from klyvion.engine.base import TTSEngine

_REGISTRY: dict[str, str] = {
    "xtts": "klyvion.engine.xtts_engine:XTTSEngine",
    "pyttsx3": "klyvion.engine.pyttsx3_engine:Pyttsx3Engine",
}


def create_engine(name: str, device: str = "auto") -> TTSEngine:
    """Instantiate an engine by name ("xtts" or "pyttsx3")."""
    try:
        target = _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown engine '{name}'. Available: {', '.join(sorted(_REGISTRY))}"
        ) from None

    module_path, class_name = target.split(":")
    module = __import__(module_path, fromlist=[class_name])
    engine_cls = getattr(module, class_name)
    return engine_cls(device=device)


__all__ = ["TTSEngine", "create_engine"]
