"""Игровое состояние. Пишется ТОЛЬКО в saves/ — зона, которую не трогает апдейтер."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field

from .atomic import read_json, write_json_atomic
from .paths import SAVES_DIR


@dataclass
class GameState:
    mode: str = "menu"
    tutorial_step: int = 0
    tutorial_done: bool = False
    campaign_index: int = 0
    completed_missions: list[int] = field(default_factory=list)
    current_objectives: list[str] = field(default_factory=list)
    credits: int = 0
    sandbox_difficulty: int = 1
    sandbox_wins: int = 0

    @classmethod
    def load(cls) -> "GameState":
        raw = read_json(SAVES_DIR / "state.json", {})
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        write_json_atomic(SAVES_DIR / "state.json", asdict(self))


class StateStore:
    def __init__(self) -> None:
        self.value = GameState.load()
        self._lock = asyncio.Lock()

    async def mutate(self, **changes: object) -> GameState:
        async with self._lock:
            for key, value in changes.items():
                if hasattr(self.value, key):
                    setattr(self.value, key, value)
            self.value.save()
            return self.value
