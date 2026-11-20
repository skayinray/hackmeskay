"""SandboxMode — бесконечная локальная игра против бота."""

from __future__ import annotations

from typing import Any

from ...core.events import Event
from ...core.registry import Command
from ..base import Mode
from .bot import SandboxBot
from .network import VirtualNetwork


class SandboxMode(Mode):
    name = "sandbox"
    command_owner = "sandbox"
    full_screen = True

    def __init__(self) -> None:
        super().__init__()
        self.net: VirtualNetwork | None = None
        self.bot: SandboxBot | None = None
        self.log: list[str] = []

    async def on_enter(self, difficulty: int = 1, **payload: Any) -> None:
        self.net = VirtualNetwork()
        self.log = ["песочница инициализирована"]
        self.bot = SandboxBot(self.net, self.engine.bus, difficulty=int(difficulty))
        self.engine.bus.subscribe("bot.action", self.on_event, owner=self.command_owner)
        await self.bot.start()

    async def on_exit(self) -> None:
        if self.bot:
            await self.bot.stop()
            self.bot = None
        self.net = None

    def commands(self) -> list[Command]:
        return [
            Command("back", self._go, "back — вернуться в меню", self.command_owner),
            Command("menu", self._go, "menu — вернуться в меню", self.command_owner),
            Command("net-scan", self._scan, "net-scan — разведка", self.command_owner),
            Command("connect", self._connect, "connect <узел> <пароль> — подключиться", self.command_owner),
            Command("hack", self._hack, "hack <узел> — брутфорс", self.command_owner),
            Command("virus-clean", self._clean, "virus-clean <узел> — лечить узел", self.command_owner),
            Command("bot-status", self._status, "bot-status — статистика", self.command_owner),
            Command("go", self._go, "go — вернуться в меню", self.command_owner),
        ]

    async def _scan(self, _engine: Any, *_args: str) -> str:
        assert self.net
        nodes = self.net.scan("player")
        return "обнаружены:\n" + "\n".join(
            f"  {n.id:<12}{n.ip:<14} fw={n.firewall} {'[red]INFECTED[/red]' if n.infected else ''}"
            for n in nodes
        )

    async def _connect(self, _engine: Any, *args: str) -> str:
        assert self.net
        if len(args) < 2:
            return "использование: connect <узел> <пароль>"
        ok = self.net.connect(args[0], args[1])
        return f"[green]сессия открыта: {args[0]}[/green]" if ok else "[red]неверный пароль[/red]"

    async def _hack(self, _engine: Any, *args: str) -> str:
        assert self.net
        node = args[0] if args else "node-00"
        ok = self.net.brute(node, "player")
        return f"[green]{node} захвачен[/green]" if ok else f"[yellow]отказ: {node} защищён[/yellow]"

    async def _clean(self, _engine: Any, *args: str) -> str:
        assert self.net
        node = args[0] if args else ""
        return f"узел {node} очищен" if self.net.clean(node) else "вирус не найден"

    async def _status(self, _engine: Any, *_args: str) -> str:
        assert self.net and self.bot
        stats = self.net.stats()
        return (
            f"уровень бота: {self.bot.difficulty} | узлы: {stats['nodes']} | "
            f"игрок: {stats['player']} | бот: {stats['bot']} | заражено: {stats['infected']}"
        )

    async def _go(self, _engine: Any, *_args: str) -> str:
        await self.engine.switch_mode("menu")
        return ""

    async def on_event(self, event: Event) -> None:
        if event.topic != "bot.action":
            return
        text = str(event.payload.get("text", ""))
        self.log.append(text)
        self.log = self.log[-8:]
        # В полноэкранном режиме не печатаем в активный prompt —
        # лог видно на экране после следующего действия.
        if self.bot and self.bot.is_defeated():
            await self.engine.state.mutate(
                sandbox_wins=self.engine.state.value.sandbox_wins + 1,
                credits=self.engine.state.value.credits + 120,
            )
            self.engine.notice = "[bold green]СЕТЬ БОТА УНИЧТОЖЕНА +120[/bold green]"
            await self.engine.switch_mode("menu")

    def render(self) -> str:
        assert self.net
        stats = self.net.stats()
        g = self.engine.console.glyphs
        inner = 60

        def plain_len(text: str) -> int:
            return len(self.engine.console.console.render_str(text).plain)

        def row(text: str = "") -> str:
            pad = inner - plain_len(text)
            if pad < 0:
                pad = 0
            return f" {g.vline} {text}{' ' * pad}{g.vline}"

        lvl = self.bot.difficulty if self.bot else 1
        lines: list[str] = [f"[bold green]{g.line * 20} SANDBOX {g.line * 20}[/bold green]", ""]
        lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
        lines.append(row(f"[bold cyan]ПЕСОЧНИЦА[/bold cyan]  [dim]уровень бота {lvl}[/dim]"))
        lines.append(row(
            f"[dim]игрок:[/dim] {stats['player']}  [dim]бот:[/dim] {stats['bot']}  "
            f"[dim]заражено:[/dim] {stats['infected']}  [dim]узлов:[/dim] {stats['nodes']}"
        ))
        lines.append(row(""))
        lines.append(row("[dim]Последние действия бота:[/dim]"))
        entries = self.log[-4:] or ["—"]
        for entry in entries:
            lines.append(row(f"  {g.bullet} {entry[:inner - 6]}"))
        lines.append(row(""))
        lines.append(row(f"[dim]Команды:[/dim] net-scan connect hack virus-clean bot-status"))
        lines.append(row(f"         [bold yellow]back[/bold yellow] {g.arrow} главное меню"))
        lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
        return "\n".join(lines)
