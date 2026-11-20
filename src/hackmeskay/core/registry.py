"""Реестр консольных команд с понятием владельца (owner).

owner == имя мода или режим. Это ключ к динамической выгрузке:
`registry.unregister_owner("my_mod")` мгновенно убирает все команды мода.
"""

from __future__ import annotations

import inspect
import re
import shlex
import sys
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

SAFE_COMMAND = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

Handler = Callable[..., Awaitable[str | None] | str | None]


@dataclass(slots=True)
class Command:
    name: str
    handler: Handler
    help: str = ""
    owner: str = "core"
    aliases: tuple[str, ...] = field(default_factory=tuple)


class UnknownCommand(LookupError):
    pass


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, Command] = {}
        self._aliases: dict[str, str] = {}
        self._owners: dict[str, set[str]] = {}

    def register(self, command: Command) -> None:
        if not SAFE_COMMAND.fullmatch(command.name):
            raise ValueError(f"invalid command name: {command.name!r}")
        for alias in command.aliases:
            if not SAFE_COMMAND.fullmatch(alias):
                raise ValueError(f"invalid alias: {alias!r}")
        self._commands[command.name] = command
        self._owners.setdefault(command.owner, set()).add(command.name)
        for alias in command.aliases:
            self._aliases[alias] = command.name
            self._owners.setdefault(command.owner, set()).add(alias)

    def register_many(self, commands: list[Command]) -> None:
        for command in commands:
            self.register(command)

    def unregister_owner(self, owner: str) -> None:
        for name in self._owners.pop(owner, ()):
            canonical = self._aliases.pop(name, name)
            self._commands.pop(name, None)
            self._commands.pop(canonical, None)

    def get(self, name: str) -> Command | None:
        canonical = self._aliases.get(name, name)
        return self._commands.get(canonical)

    def names(self, owner: str | None = None) -> list[str]:
        if owner is None:
            return sorted(set(self._commands) | set(self._aliases))
        return sorted(n for n in self._owners.get(owner, ()) if n in self._commands or n in self._aliases)

    def help_text(self, owner: str | None = None) -> str:
        rows: list[str] = []
        seen: set[str] = set()
        for name in self.names(owner):
            command = self.get(name)
            if command is None or command.name in seen:
                continue
            seen.add(command.name)
            rows.append(f"  {command.name:<18} {command.help}")
        return "\n".join(rows) or "  (нет доступных команд)"

    async def dispatch(self, line: str, ctx: Any) -> str:
        line = line.strip()
        if not line:
            return ""
        # в игре допустимы оба стиля: `scan ...` и `/scan ...`
        if line.startswith("/"):
            line = line[1:].lstrip()
        try:
            tokens = shlex.split(line, posix=sys.platform != "win32")
        except ValueError:
            tokens = line.split()
        if not tokens:
            return ""
        command = self.get(tokens[0].lower())
        if command is None:
            raise UnknownCommand(f"неизвестная команда: {tokens[0]}")
        result = command.handler(ctx, *tokens[1:])
        if inspect.isawaitable(result):
            result = await result
        return "" if result is None else str(result)
