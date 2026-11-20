"""AI-бот песочницы: циклично сканирует, брутфорсит, меняет пароли и кидает вирусы."""

from __future__ import annotations

import asyncio
import random
from typing import Any

from ...core.events import Event


class SandboxBot:
    def __init__(self, network: Any, bus: Any, difficulty: int = 1) -> None:
        self.net = network
        self.bus = bus
        self.difficulty = max(1, min(5, difficulty))
        self.rng = random.Random(9000 + self.difficulty)
        self.tick = 0
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self.run(), name="sandbox-bot")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _say(self, text: str) -> None:
        await self.bus.publish(Event("bot.action", {"text": text}))

    async def run(self) -> None:
        base = max(1.2, 6.0 - self.difficulty * 0.9)
        while True:
            self.tick += 1
            phase = self.tick % 4
            if phase == 0:
                found = self.net.scan("bot")
                await self._say(f"bot: net-scan -> {len(found)} узлов в зоне видимости")
            elif phase == 1:
                candidates = [n.id for n in self.net.nodes.values() if n.owner != "bot"]
                target = self.rng.choice(candidates) if candidates else None
                if target and self.net.brute(target, "bot"):
                    await self._say(f"bot: брутфорс успешен — {target} перехвачен")
                elif target:
                    await self._say(f"bot: брутфорс {target} безуспешен")
            elif phase == 2:
                targets = [n.id for n in self.net.nodes.values() if n.owner == "bot"]
                if targets:
                    node = self.rng.choice(targets)
                    self.net.rotate_password(node)
                    await self._say(f"bot: ротация пароля на {node}")
            else:
                targets = [n.id for n in self.net.nodes.values() if n.owner != "bot"]
                if targets and self.rng.random() < 0.5 + self.difficulty * 0.08:
                    victim = self.rng.choice(targets)
                    self.net.infect(victim)
                    await self._say(f"bot: вирус запущен на {victim}")
            await asyncio.sleep(base + self.rng.uniform(-0.3, 0.6))

    def is_defeated(self) -> bool:
        stats = self.net.stats()
        return stats["bot"] == 0 and stats["infected"] == 0
