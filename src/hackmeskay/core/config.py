from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from typing import Any

from .atomic import read_json, write_json_atomic
from .paths import CONFIG_DIR

DEFAULT_UPDATE_URL = (
    "https://raw.githubusercontent.com/skayinray/hackmeskay/main/deploy/update.json"
)


@dataclass
class Settings:
    ascii_only: bool = False
    tick_rate: int = 20
    auto_check_updates: bool = True
    update_url: str = DEFAULT_UPDATE_URL
    language: str = "ru"

    @classmethod
    def load(cls) -> "Settings":
        raw = read_json(CONFIG_DIR / "settings.json", {})
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        write_json_atomic(CONFIG_DIR / "settings.json", asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SettingsStore:
    """Сериализованный доступ к настройкам из разных задач."""

    def __init__(self) -> None:
        self.value = Settings.load()
        self._lock = asyncio.Lock()

    async def update(self, **changes: Any) -> Settings:
        async with self._lock:
            for key, value in changes.items():
                if hasattr(self.value, key):
                    setattr(self.value, key, value)
            self.value.save()
            return self.value
