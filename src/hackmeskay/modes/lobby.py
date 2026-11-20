"""Сетевое лобби: ASCII-меню комнаты с обязательной командой back."""

from __future__ import annotations

from typing import Any

from ..core.registry import Command
from .base import Mode


class LobbyMode(Mode):
    name = "lobby"
    command_owner = "lobby"
    full_screen = True

    def commands(self) -> list[Command]:
        return [
            Command("back", self._back, "back — назад в главное меню", self.command_owner),
            Command("menu", self._back, "menu — назад в главное меню", self.command_owner),
        ]

    async def _back(self, _engine: Any, *_args: str) -> str:
        await self.engine.switch_mode("menu")
        return ""

    def render(self) -> str:
        network = self.engine.network
        g = self.engine.console.glyphs
        inner = 54

        def plain_len(text: str) -> int:
            return len(self.engine.console.console.render_str(text).plain)

        def row(text: str = "") -> str:
            pad = inner - plain_len(text)
            if pad < 0:
                pad = 0
            return f" {g.vline} {text}{' ' * pad}{g.vline}"

        status = "[green]в комнате[/green]" if network.is_online else "[dim]офлайн[/dim]"
        items = [
            "[bold cyan]СЕТЕВОЕ ЛОББИ[/bold cyan]",
            "",
            f"  [bold]host [port][/bold]         {g.arrow}  создать комнату",
            f"  [bold]join <IP> [port][/bold]    {g.arrow}  подключиться по IP",
            f"  [bold]msg <ID> <текст>[/bold]    {g.arrow}  сообщение по Messenger ID",
            f"  [bold]peers[/bold]               {g.arrow}  участники комнаты",
            f"  [bold]leave[/bold]               {g.arrow}  выйти из комнаты",
            "",
            f"  [bold yellow]back[/bold yellow]                {g.arrow}  назад в главное меню",
        ]

        lines: list[str] = [f"[bold green]{g.line * 20} NETWORK {g.line * 20}[/bold green]", ""]
        lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
        lines.extend(row(item) for item in items)
        lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
        lines.append("")
        lines.append(f" [dim]Messenger ID:[/dim] [bold green]{network.identity}[/bold green]")
        lines.append(f" [dim]Статус:[/dim] {status}")
        if network.is_online:
            peers = network.peer_ids()
            lines.append(f" [dim]Участники:[/dim] " + (", ".join(peers) or "—"))
        lines.append(" [dim]Реальные IP скрыты — общение идёт по Messenger ID[/dim]")
        lines.append(" [dim]Команда 'back' вернёт в главное меню[/dim]")
        return "\n".join(lines)
