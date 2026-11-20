"""Главное меню."""

from __future__ import annotations

from ..core.registry import Command
from ..ui.theme import BANNER
from .base import Mode


class MenuMode(Mode):
    name = "menu"
    command_owner = "menu"
    full_screen = True

    def commands(self) -> list[Command]:
        return [
            Command("play", self._play, "play — продолжить кампанию", self.command_owner),
            Command("tutorial", self._tutorial, "tutorial — режим обучения", self.command_owner),
            Command("campaign", self._campaign, "campaign [n] — кампания/список миссий", self.command_owner),
            Command("sandbox", self._sandbox, "sandbox [1-5] — соло против бота", self.command_owner),
            Command("network", self._network, "network — сетевое лобби (создать/присоединиться)", self.command_owner),
            Command("about", self._about, "about — о проекте", self.command_owner),
        ]

    async def _play(self, _engine: object, *_args: str) -> str:
        await self.engine.switch_mode("campaign")
        return ""

    async def _tutorial(self, _engine: object, *_args: str) -> str:
        await self.engine.switch_mode("tutorial")
        return ""

    async def _campaign(self, _engine: object, *args: str) -> str:
        await self.engine.switch_mode("campaign", mission=args[0] if args else None)
        return ""

    async def _sandbox(self, _engine: object, *args: str) -> str:
        difficulty = int(args[0]) if args and args[0].isdigit() else 1
        await self.engine.switch_mode("sandbox", difficulty=difficulty)
        return ""

    async def _network(self, _engine: object, *_args: str) -> str:
        # лобби — отдельный режим с собственной отрисовкой и командой back
        await self.engine.switch_mode("lobby")
        return ""

    async def _about(self, _engine: object, *_args: str) -> str:
        return (
            "[bold green]hackmeskay[/bold green] — текстовая хакерская MMO. "
            "Всё происходит в виртуальной сети: никаких реальных атак.\n"
            "Режимы: tutorial, campaign (10 миссий), sandbox (AI-бот).\n"
            "Моды: mod list / enable / disable. Обновления: update check / install."
        )

    def render(self) -> str:
        state = self.engine.state.value
        g = self.engine.console.glyphs
        progress = f"{len(state.completed_missions)}/10"
        inner = 46

        def plain_len(text: str) -> int:
            return len(self.engine.console.console.render_str(text).plain)

        def row(text: str = "") -> str:
            pad = inner - plain_len(text)
            if pad < 0:
                pad = 0
            return f" {g.vline} {text}{' ' * pad}{g.vline}"

        items = [
            "[bold cyan]ГЛАВНОЕ МЕНЮ[/bold cyan]",
            "",
            f"  [bold]play[/bold]      {g.arrow}  продолжить кампанию",
            f"  [bold]tutorial[/bold]  {g.arrow}  обучение",
            f"  [bold]campaign[/bold]  {g.arrow}  10 миссий",
            f"  [bold]sandbox[/bold]   {g.arrow}  соло против AI-бота",
            f"  [bold]network[/bold]   {g.arrow}  сетевая игра (LAN/p2p)",
            f"  [bold]wiki[/bold]      {g.arrow}  база знаний",
            f"  [bold]mod[/bold]       {g.arrow}  менеджер модов",
            f"  [bold]update[/bold]    {g.arrow}  проверка обновлений",
            f"  [bold]quit[/bold]      {g.arrow}  выход",
        ]

        lines: list[str] = [f"[bold green]{BANNER}[/bold green]", ""]
        lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
        lines.extend(row(item) for item in items)
        lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
        lines.append("")
        lines.append(
            f" [dim]кредиты:[/dim] [bold]{state.credits}[/bold]"
            f"   [dim]кампания:[/dim] [bold]{progress}[/bold]"
            f"   [dim]моды:[/dim] [bold]{len(self.engine.mods._loaded)}[/bold]"
        )
        lines.append(" [dim]введите команду и нажмите Enter[/dim]")
        return "\n".join(lines)
