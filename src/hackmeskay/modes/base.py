"""Базовый класс игрового режима."""

from __future__ import annotations

from typing import Any

from ..core.events import Event
from ..core.registry import Command


class Mode:
    name = "base"
    command_owner = "mode"

    def __init__(self) -> None:
        self.engine: Any = None

    def attach(self, engine: Any) -> None:
        self.engine = engine

    def commands(self) -> list[Command]:
        return []

    async def enter(self, **payload: Any) -> None:
        if self.engine:
            self.engine.registry.register_many(self.commands())
            self.engine.bus.subscribe("tick", self.on_event, owner=self.command_owner)
            self.engine.bus.subscribe("command.executed", self.on_event, owner=self.command_owner)
        await self.on_enter(**payload)

    async def exit(self) -> None:
        await self.on_exit()
        if self.engine:
            self.engine.registry.unregister_owner(self.command_owner)
            self.engine.bus.unsubscribe_owner(self.command_owner)

    async def on_enter(self, **payload: Any) -> None:
        pass

    async def on_exit(self) -> None:
        pass

    async def on_event(self, event: Event) -> None:
        pass

    def render(self) -> str:
        return ""
