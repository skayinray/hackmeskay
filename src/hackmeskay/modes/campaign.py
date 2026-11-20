"""Кампания: 10 миссий описаны DATA_DIR/campaign/missions.json.

Новая миссия = новая запись в JSON, код менять не нужно. Дополнительные
типы objective (не команда, а событие) добавляются через `kind: "event"`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.atomic import read_json
from ..core.events import Event
from ..core.paths import DATA_DIR
from ..core.registry import Command
from .base import Mode


@dataclass(slots=True)
class Objective:
    id: str
    text: str
    kind: str = "command"
    match: str = ""


@dataclass(slots=True)
class Mission:
    id: int
    title: str
    brief: str
    objectives: list[Objective] = field(default_factory=list)
    reward: int = 0

    @classmethod
    def parse(cls, raw: dict[str, Any]) -> "Mission":
        return cls(
            id=int(raw["id"]),
            title=str(raw["title"]),
            brief=str(raw["brief"]),
            objectives=[
                Objective(str(o["id"]), str(o["text"]), str(o.get("kind", "command")), str(o.get("match", "")))
                for o in raw.get("objectives", [])
            ],
            reward=int(raw.get("reward", 0)),
        )


class CampaignMode(Mode):
    name = "campaign"
    command_owner = "campaign"
    full_screen = True

    def __init__(self) -> None:
        super().__init__()
        self.missions: list[Mission] = []
        self.current: Mission | None = None
        self.done: set[str] = set()

    async def on_enter(self, mission: str | None = None, **payload: Any) -> None:
        path = DATA_DIR / "campaign" / "missions.json"
        raw = read_json(path, None)
        if not isinstance(raw, dict):
            raise RuntimeError(f"не найден файл миссий: {path}")
        self.missions = [Mission.parse(item) for item in raw.get("missions", [])]
        self.done = set(self.engine.state.value.current_objectives)
        if mission:
            msg = await self.start(str(mission))
            if msg:
                self.engine.notice = msg

    def commands(self) -> list[Command]:
        return [
            Command("back", self._back, "back — назад в главное меню", self.command_owner),
            Command("menu", self._back, "menu — назад в главное меню", self.command_owner),
            Command("mission", self._mission, "mission list|start <n>|status|abort", self.command_owner),
            Command("ls", self._ls, "ls — список файлов узла", self.command_owner),
            Command("cat", self._cat, "cat <файл> — прочитать файл", self.command_owner),
            Command("net-scan", self._net_scan, "net-scan — разведка сети", self.command_owner),
            Command("connect", self._connect, "connect <узел> — подключиться", self.command_owner),
            Command("hack", self._hack, "hack <узел> — взломать узел", self.command_owner),
            Command("sniff", self._sniff, "sniff — перехват трафика", self.command_owner),
            Command("firewall", self._firewall, "firewall --bypass ...", self.command_owner),
            Command("proxy", self._proxy, "proxy — туннелирование", self.command_owner),
            Command("decrypt", self._decrypt, "decrypt <файл> — расшифровать", self.command_owner),
            Command("botnet", self._botnet, "botnet --coordinate — финальная миссия", self.command_owner),
        ]

    async def _back(self, _engine: Any, *_args: str) -> str:
        self.current = None
        self.done.clear()
        await self.engine.state.mutate(current_objectives=[])
        await self.engine.switch_mode("menu")
        return ""

    async def _mission(self, _engine: Any, *args: str) -> str:
        action = args[0].lower() if args else "list"
        if action == "list":
            # список уже показан на экране кампании
            return ""
        if action == "start":
            if len(args) < 2:
                return "использование: mission start <n>"
            return await self.start(args[1])
        if action == "status":
            if not self.current:
                return "активная миссия отсутствует"
            # прогресс уже виден на экране активной миссии
            return ""
        if action == "abort":
            self.current = None
            self.done.clear()
            await self.engine.state.mutate(current_objectives=[])
            return "[yellow]миссия прервана[/yellow]"
        return "использование: mission list | mission start <n> | mission status | mission abort"

    async def start(self, number: str) -> str:
        try:
            mission = next(m for m in self.missions if m.id == int(number))
        except (StopIteration, ValueError):
            return f"миссия {number} не найдена"
        if mission.id > self.engine.state.value.campaign_index + 1:
            return "[yellow]сначала заверши предыдущие миссии[/yellow]"
        self.current = mission
        self.done.clear()
        self.engine.mark_dirty()
        return f"[cyan]миссия запущена:[/cyan] {mission.id}. {mission.title}"

    # заглушки команд: они нужны как триггеры objective, а не как реальные утилиты
    async def _ls(self, _e: Any, *a: str) -> str:
        return "auth.log  .secret  mesh.conf" if self.current and self.current.id == 1 else "mesh.conf  nodes.json"

    async def _cat(self, _e: Any, *a: str) -> str:
        return "DEBUG password=swordfish hidden_in_log" if self.current and self.current.id == 1 else "(пусто)"

    async def _net_scan(self, _e: Any, *_a: str) -> str:
        return "обнаружены: node-01, node-02, mail-gw, firewall-01"

    async def _connect(self, _e: Any, *a: str) -> str:
        return f"сессия: {a[0] if a else 'node-01'}"

    async def _hack(self, _e: Any, *a: str) -> str:
        return f"[green]узел {a[0] if a else 'node-01'} взломан[/green]"

    async def _sniff(self, _e: Any, *_a: str) -> str:
        return "перехвачено 42 пакета, найден токен FW-BYPASS-77"

    async def _firewall(self, _e: Any, *a: str) -> str:
        return "файрвол обойден" if "--bypass" in a else "использование: firewall --bypass <token>"

    async def _proxy(self, _e: Any, *_a: str) -> str:
        return "туннель установлен"

    async def _decrypt(self, _e: Any, *a: str) -> str:
        return f"расшифровано: {a[0] if a else 'vault.enc'}"

    async def _botnet(self, _e: Any, *a: str) -> str:
        return "рой ботов скоординирован: 64 узла атакуют синхронно"

    async def on_event(self, event: Event) -> None:
        if event.topic != "command.executed" or not self.current:
            return
        line = str(event.payload.get("line", "")).lower()
        notes: list[str] = []
        for objective in self.current.objectives:
            if objective.id in self.done or not objective.match:
                continue
            if objective.kind == "command" and line.startswith(objective.match.lower()):
                self.done.add(objective.id)
                notes.append(f"[green]выполнено:[/green] {objective.text}")
        if notes:
            await self.engine.state.mutate(current_objectives=list(self.done))
            self.engine.mark_dirty()
            if len(self.done) == len(self.current.objectives):
                msg = await self._complete()
                notes.append(msg)
            self.engine.notice = "\n".join(
                part for part in [self.engine.notice, *notes] if part
            )

    async def _complete(self) -> str:
        assert self.current is not None
        mission = self.current
        state = self.engine.state.value
        completed = sorted(set(state.completed_missions) | {mission.id})
        await self.engine.state.mutate(
            completed_missions=completed,
            campaign_index=max(state.campaign_index, mission.id),
            credits=state.credits + mission.reward,
            current_objectives=[],
        )
        msg = f"[bold green]МИССИЯ {mission.id} ВЫПОЛНЕНА[/bold green] +{mission.reward} кредитов"
        self.current = None
        self.done.clear()
        return msg

    def _progress_text(self) -> str:
        if not self.current:
            return "выбери миссию: mission list / mission start <n>"
        lines = [f"[cyan]{self.current.id}. {self.current.title}[/cyan]"]
        for objective in self.current.objectives:
            mark = "[green]x[/green]" if objective.id in self.done else "[ ]"
            lines.append(f"  {mark} {objective.text}")
        return "\n".join(lines)

    def render(self) -> str:
        g = self.engine.console.glyphs
        inner = 60

        def plain_len(text: str) -> int:
            return len(self.engine.console.console.render_str(text).plain)

        def row(text: str = "") -> str:
            pad = inner - plain_len(text)
            if pad < 0:
                pad = 0
            return f" {g.vline} {text}{' ' * pad}{g.vline}"

        lines: list[str] = [f"[bold green]{g.line * 20} CAMPAIGN {g.line * 20}[/bold green]", ""]

        if not self.current:
            state = self.engine.state.value
            lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
            lines.append(row("[bold cyan]КАМПАНИЯ[/bold cyan]  [dim]виртуальный mesh[/dim]"))
            lines.append(row(""))
            lines.append(row("[dim]Доступные миссии:[/dim]"))
            for m in self.missions[:10]:
                unlocked = m.id <= state.campaign_index + 1
                if m.id in state.completed_missions:
                    mark = "[green]OK[/green]"
                elif unlocked:
                    mark = "[yellow]доступна[/yellow]"
                else:
                    mark = "[dim]закрыта[/dim]"
                lines.append(row(f"  {m.id:>2}. {m.title[:38]:<38} {mark}"))
            lines.append(row(""))
            lines.append(row(f"[dim]Команды:[/dim] mission start <n>  |  [bold yellow]back[/bold yellow]"))
            lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
            lines.append("")
            lines.append(" [dim]Введите 'back' чтобы вернуться в главное меню[/dim]")
            return "\n".join(lines)

        lines.append(f" {g.box_tl}{g.line * (inner + 1)}{g.box_tr}")
        lines.append(row(f"[bold cyan]МИССИЯ {self.current.id}:[/bold cyan] {self.current.title[:44]}"))
        lines.append(row(""))
        for part in self.current.brief.splitlines()[:2]:
            lines.append(row(f"[dim]{part[:inner]}[/dim]"))
        lines.append(row(""))
        for objective in self.current.objectives:
            done = objective.id in self.done
            mark = "[green]✔[/green]" if done else "[dim]·[/dim]"
            text = objective.text[: inner - 6]
            if done:
                lines.append(row(f"  {mark} [green]{text}[/green]"))
            else:
                lines.append(row(f"  {mark} {text}"))
        lines.append(row(""))
        lines.append(row(f"[dim]Команды: mission status|abort |[/dim] [bold yellow]back[/bold yellow]"))
        lines.append(f" {g.box_bl}{g.line * (inner + 1)}{g.box_br}")
        return "\n".join(lines)
