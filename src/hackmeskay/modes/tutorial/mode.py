"""TutorialMode — пошаговый тренажёр, изолированный от остальных режимов."""

from __future__ import annotations

from typing import Any

from ...core.events import Event
from ...core.registry import Command
from ..base import Mode
from .steps import TUTORIAL_STEPS, TutorialStep


class TutorialMode(Mode):
    name = "tutorial"
    command_owner = "tutorial"
    full_screen = True

    def __init__(self) -> None:
        super().__init__()
        self.index = 0
        self.cwd = "/home/operator"
        self.nodes: list[str] = []
        self.connected: str | None = None
        self.scan_target = "10.60.0.2"
        self.finished = False

    @property
    def step(self) -> TutorialStep:
        return TUTORIAL_STEPS[min(self.index, len(TUTORIAL_STEPS) - 1)]

    def commands(self) -> list[Command]:
        return [
            Command("back", self._back, "back — назад в главное меню", self.command_owner),
            Command("menu", self._back, "menu — назад в главное меню", self.command_owner),
            Command("ls", self._ls, "ls [-a] — список файлов", self.command_owner),
            Command("cd", self._cd, "cd <путь> — сменить каталог", self.command_owner),
            Command("net-scan", self._net_scan, "net-scan — найти узлы", self.command_owner),
            Command("connect", self._connect, "connect <узел> — подключиться", self.command_owner),
            Command("hack", self._hack, "hack <узел> — взломать узел", self.command_owner),
            Command("skip", self._skip, "skip — пропустить шаг", self.command_owner),
        ]

    async def _back(self, _engine: Any, *_args: str) -> str:
        await self.engine.switch_mode("menu")
        return ""

    async def on_enter(self, **payload: Any) -> None:
        self.index = int(self.engine.state.value.tutorial_step)
        self.finished = self.engine.state.value.tutorial_done
        empire = getattr(self.engine, "empire", None)
        network = getattr(self.engine, "network", None)
        if empire and network:
            gateway = empire.build_empire(str(network.identity))
            self.scan_target = gateway.game_ip
        self.engine.notice = "[cyan]Тренажёр запущен. Следуй подсказкам на экране.[/cyan]"

    async def _ls(self, _engine: Any, *args: str) -> str:
        files = [".profile", "auth.log"] if "-a" in args else ["readme.txt", "notes.md"]
        return "  ".join(files)

    async def _cd(self, _engine: Any, *args: str) -> str:
        self.cwd = args[0] if args else "/"
        return f"текущий каталог: {self.cwd}"

    async def _net_scan(self, _engine: Any, *_args: str) -> str:
        self.nodes = ["node-01", "node-02", "mail-gw"]
        return "обнаружены узлы: " + ", ".join(self.nodes)

    async def _connect(self, _engine: Any, *args: str) -> str:
        node = args[0] if args else "node-01"
        if node not in self.nodes:
            return f"[yellow]сначала выполни net-scan; узел {node} не в списке[/yellow]"
        self.connected = node
        return f"сессия открыта: {node}"

    async def _hack(self, _engine: Any, *args: str) -> str:
        node = args[0] if args else self.connected
        if not node:
            return "[yellow]сначала подключись: connect node-01[/yellow]"
        return f"[green]пароль узла {node} подобран: 'swordfish'[/green]"

    async def _skip(self, _engine: Any, *_args: str) -> str:
        msg = await self._advance(prefix="[yellow]шаг пропущен[/yellow]")
        return msg

    async def on_event(self, event: Event) -> None:
        if event.topic != "command.executed" or self.finished:
            return
        line = str(event.payload.get("line", ""))
        cmd = line.strip().split()[0].lower().lstrip("/") if line.strip() else ""
        if cmd in {"skip", "back", "menu"}:
            return
        if not self.step.validator(line):
            self.engine.notice = "\n".join(
                part for part in [self.engine.notice, f"[yellow]подсказка:[/yellow] {self.step.hint}"] if part
            )
            return
        msg = await self._advance()
        if msg:
            self.engine.notice = "\n".join(part for part in [self.engine.notice, msg] if part)
        self.engine.mark_dirty()

    async def _advance(self, prefix: str = "") -> str:
        notes: list[str] = []
        if prefix:
            notes.append(prefix)
        notes.append(f"[green]{self.step.success}[/green]")
        self.index += 1
        await self.engine.state.mutate(tutorial_step=self.index)
        if self.index >= len(TUTORIAL_STEPS):
            self.finished = True
            await self.engine.state.mutate(
                tutorial_done=True, credits=self.engine.state.value.credits + 50
            )
            notes.append("[bold green]ОБУЧЕНИЕ ЗАВЕРШЕНО (+50 кредитов)[/bold green]")
            await self.engine.switch_mode("menu")
            return "\n".join(notes)
        return "\n".join(notes)

    def render(self) -> str:
        g = self.engine.console.glyphs
        inner = 58

        def plain_len(text: str) -> int:
            return len(self.engine.console.console.render_str(text).plain)

        def row(text: str = "") -> str:
            pad = inner - plain_len(text)
            if pad < 0:
                pad = 0
            return f" {g.vline} {text}{' ' * pad}{g.vline}"

        lines: list[str] = [f"[bold green]{g.line * 20} TUTORIAL {g.line * 19}[/bold green]", ""]

        if self.finished:
            lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
            lines.append(row("[bold green]Обучение пройдено[/bold green]"))
            lines.append(row(""))
            lines.append(row("Введите [bold]campaign[/bold] или [bold yellow]back[/bold yellow] для выхода в меню"))
            lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
            return "\n".join(lines)

        step = self.step
        lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
        lines.append(row(f"[bold cyan]{step.title}[/bold cyan]"))
        lines.append(row(""))
        lines.append(row(f" {g.bullet} каталог:         {self.cwd}"))
        lines.append(row(f" {g.bullet} найденные узлы:  {', '.join(self.nodes) or '—'}"))
        lines.append(row(f" {g.bullet} активная сессия: {self.connected or '—'}"))
        lines.append(row(f" {g.bullet} цель для /scan:  [yellow]{self.scan_target}[/yellow]"))
        lines.append(row(""))
        lines.append(row(f"[dim]Цель шага:[/dim] [bold yellow]{step.command}[/bold yellow]"))
        lines.append(row(f"[dim]{step.hint[:inner-2]}[/dim]"))
        lines.append(row(""))
        lines.append(row(f"[dim]Команды шага, skip — пропустить, [bold yellow]back[/bold yellow] — меню[/dim]"))
        lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
        return "\n".join(lines)
