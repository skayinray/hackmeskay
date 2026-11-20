"""Мини-шина событий. Подписки привязаны к owner'у — это позволяет моду/режиму
отписаться одной командой при выгрузке.
"""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("hackmeskay.events")

Handler = Callable[["Event"], Awaitable[None] | None]


@dataclass(frozen=True, slots=True)
class Event:
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[tuple[Handler, str]]] = {}
        self._owners: dict[str, list[tuple[str, Handler]]] = {}

    def subscribe(self, topic: str, handler: Handler, owner: str = "core") -> None:
        self._subs.setdefault(topic, []).append((handler, owner))
        self._owners.setdefault(owner, []).append((topic, handler))

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        self._subs[topic] = [pair for pair in self._subs.get(topic, []) if pair[0] is not handler]

    def unsubscribe_owner(self, owner: str) -> None:
        for topic, handler in self._owners.pop(owner, []):
            self.unsubscribe(topic, handler)

    async def publish(self, event: Event) -> None:
        handlers = list(self._subs.get(event.topic, ())) + list(self._subs.get("*", ()))
        for handler, owner in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # один плохой подписчик не роняет движок
                log.exception("event handler failed: topic=%s owner=%s", event.topic, owner)
