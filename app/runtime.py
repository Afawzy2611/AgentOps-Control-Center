import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeInfo:
    name: str
    available: bool


def _agents_sdk_available() -> bool:
    try:
        import agents  # noqa: F401
    except ImportError:
        return False
    return True


def get_runtime() -> RuntimeInfo:
    name = os.getenv("AGENT_RUNTIME", "deterministic").strip().lower()
    if name not in {"deterministic", "agents_sdk"}:
        name = "deterministic"
    return RuntimeInfo(name=name, available=True if name == "deterministic" else _agents_sdk_available())
