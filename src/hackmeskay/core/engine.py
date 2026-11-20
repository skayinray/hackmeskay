"""Ядро: один asyncio-loop, параллельные задачи и стек режимов.

Задачи: ввод, разбор команд, рендер, тики, события p2p-мессенджера,
фоновые сетевые события и watcher модов.
Режимы: menu -> tutorial | campaign | sandbox. wiki/mod/update/help и
сетевые команды — глобальные, доступны из любого режима.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from typing import Any

from .events import Event, EventBus
from .registry import Command, CommandRegistry, UnknownCommand

log = logging.getLogger("hackmeskay.engine")


class Engine:
    def __init__(self, *, console: Any, registry: CommandRegistry, bus: EventBus,
                 state_store: Any, settings_store: Any, mods: Any,
                 updater: Any, wiki: Any, network: Any = None, empire: Any = None) -> None:
        self.console = console
        self.registry = registry
        self.bus = bus
        self.state = state_store
        self.settings = settings_store
        self.mods = mods
        self.updater = updater
        self.wiki = wiki
        self.network = network
        self.empire = empire

        self.modes: dict[str, Any] = {}
        self.stack: list[Any] = []
        self._dirty = asyncio.Event()
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task[Any]] = []
        self._rendered_once = False
        self.notice: str = ""  # последнее сообщение для полноэкранных режимов

    # ---------- жизненный цикл ----------

    def register_mode(self, mode: Any) -> None:
        self.modes[mode.name] = mode
        mode.attach(self)

    @property
    def active_mode(self) -> Any | None:
        return self.stack[-1] if self.stack else None

    def mark_dirty(self) -> None:
        self._dirty.set()

    async def switch_mode(self, name: str, **payload: Any) -> str:
        """Полная замена текущего режима (меню <-> режим)."""
        if name not in self.modes:
            return f"неизвестный режим: {name}"
        while self.stack:
            old = self.stack.pop()
            await old.exit()
        new = self.modes[name]
        self.notice = ""
        await new.enter(**payload)
        self.stack.append(new)
        await self.state.mutate(mode=name)
        self.mark_dirty()
        await self.bus.publish(Event("mode.changed", {"name": name}))
        return f"режим: {name}"

    async def push_mode(self, name: str, **payload: Any) -> str:
        """Overlay-режим (например, wiki поверх sandbox)."""
        if name not in self.modes:
            return f"неизвестный режим: {name}"
        mode = self.modes[name]
        await mode.enter(**payload)
        self.stack.append(mode)
        self.mark_dirty()
        return f"режим: {name}"

    async def pop_mode(self) -> str:
        if len(self.stack) <= 1:
            return "нельзя выйти из единственного режима"
        mode = self.stack.pop()
        await mode.exit()
        self.mark_dirty()
        return f"возврат в {self.stack[-1].name}"

    async def run(self, initial_mode: str = "menu") -> None:
        self._install_global_commands()
        self._install_signals()
        await self.mods.boot()
        await self.switch_mode(initial_mode)
        self.render_current()
        self._tasks = [
            asyncio.create_task(self._input_loop(), name="input"),
            asyncio.create_task(self._tick_loop(), name="tick"),
            asyncio.create_task(self._render_loop(), name="render"),
            asyncio.create_task(self._network_loop(), name="p2p-events"),
            asyncio.create_task(self.mods.watch(self._stop), name="mod-watch"),
        ]
        try:
            await self._stop.wait()
        finally:
            for task in self._tasks:
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)
            await self.shutdown()

    async def shutdown(self) -> None:
        while self.stack:
            await self.stack.pop().exit()
        await self.mods.shutdown()
        if self.network and self.network.is_online:
            await self.network.leave()
        self.state.value.save()
        self.console.print("[dim] соединение закрыто. до встречи в mesh.[/dim]")

    def request_stop(self) -> None:
        self._stop.set()

    # ---------- циклы ----------

    async def _input_loop(self) -> None:
        """Чтение и выполнение команд последовательно.

        Следующий prompt показывается только после вывода/перерисовки,
        иначе prompt_toolkit-строка ввода перемешивается с выводом.
        """
        while not self._stop.is_set():
            mode = self.active_mode
            prompt = f"hack@mesh:{mode.name if mode else '?'}> "
            try:
                line = await self.console.readline(prompt)
            except (EOFError, KeyboardInterrupt):
                self.request_stop()
                break
            except Exception as exc:
                log.exception("ошибка ввода")
                self.console.print(f"[red]ввод: {exc}[/red]")
                break

            line = line.strip()
            if not line:
                # Пустой ввод: просто перерисовать полноэкранный режим заново,
                # чтобы экран всегда оставался чистым и актуальным.
                if self.active_mode and getattr(self.active_mode, "full_screen", False):
                    self.render_current()
                continue

            self.notice = ""
            output: str | None = None
            try:
                output = await self.registry.dispatch(line, self)
            except UnknownCommand as exc:
                output = f"[red]{exc}[/red]\n[dim]help — список команд[/dim]"
            except Exception as exc:
                log.exception("команда '%s' упала", line)
                output = f"[red]ошибка: {exc}[/red]"

            # обработчики on_event могут добавить заметку (прогресс миссии и т.п.)
            await self.bus.publish(Event("command.executed", {"line": line}))
            handler_notice = self.notice

            if self._stop.is_set():
                if output:
                    self.console.print(output)
                if handler_notice:
                    self.console.print(handler_notice)
                break

            mode = self.active_mode
            if mode and getattr(mode, "full_screen", False):
                parts: list[str] = []
                if output and not output.startswith("режим: "):
                    parts.append(output)
                if handler_notice:
                    parts.append(handler_notice)
                self.notice = "\n".join(parts)
                # Полная перерисовка экрана после каждого действия — без «каши».
                self.render_current()
            else:
                self.notice = ""
                self.mark_dirty()
                if output:
                    self.console.print(output)
                if handler_notice:
                    self.console.print(handler_notice)

    async def _network_loop(self) -> None:
        """Входящие p2p-сообщения и события не блокируют ввод игрока."""
        if self.network is None:
            await self._stop.wait()
            return
        while not self._stop.is_set():
            message = await self.network.inbound.get()
            await self.bus.publish(Event("net.message", {"message": message}))
            if message.kind == "chat":
                self.console.print(f"[cyan][{message.sender} -> {message.recipient}][/cyan] {message.text}")
            elif message.kind == "event":
                self.console.print(f"[magenta][сеть] {message.payload}[/magenta]")
            else:
                self.console.print(f"[dim]* {message.text}[/dim]")
            # В полноэкранных режимах не триггерим перерисовку: она ломает ввод.
            # Сообщение печатается через patch_stdout-aware print (console.file=sys.stdout).
            if not (self.active_mode and getattr(self.active_mode, "full_screen", False)):
                self.mark_dirty()
            elif self.network:
                # показать сообщение под экраном в безопасный момент? нет:
                # мы в фоновой задаче; просто сохраним как notice не стоит.
                # сообщение уже выведено поверх prompt через patch_stdout.
                pass

    async def _tick_loop(self) -> None:
        rate = max(1, int(getattr(self.settings.value, "tick_rate", 20)))
        period = 1.0 / rate
        last = time.monotonic()
        while not self._stop.is_set():
            await asyncio.sleep(period)
            now = time.monotonic()
            await self.bus.publish(Event("tick", {"dt": now - last}))
            last = now

    def render_current(self) -> None:
        mode = self.active_mode
        if mode is None:
            return
        try:
            frame = mode.render()
        except Exception as exc:
            log.exception("ошибка рендера")
            frame = f"[red]render error: {exc}[/red]"
        if not frame:
            return

        if getattr(mode, "full_screen", False):
            # Каждый выбор/действие: полный сброс экрана и чистая отрисовка,
            # чтобы старый вывод не смешивался с новым.
            self.console.clear_screen()
            self.console.print(frame)
            if self.notice:
                self.console.print()
                self.console.rule("результат")
                self.console.print(self.notice)
                self.notice = ""
            self._rendered_once = True
            return

        if self._rendered_once:
            self.console.rule(mode.name.upper())
        self.console.print(frame)
        self._rendered_once = True

    async def _render_loop(self) -> None:
        last_mode_id: int | None = None
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(self._dirty.wait(), timeout=0.25)
            except asyncio.TimeoutError:
                continue
            self._dirty.clear()
            mode = self.active_mode
            if mode is None:
                continue
            mode_id = id(mode)
            if getattr(mode, "full_screen", False):
                # Полноэкранные режимы перерисовываются из _input_loop в
                # безопасный момент (между prompt'ами), чтобы не ломать ввод.
                last_mode_id = mode_id
                continue

            try:
                frame = mode.render()
            except Exception as exc:
                log.exception("ошибка рендера")
                frame = f"[red]render error: {exc}[/red]"
            if not frame:
                continue
            if self._rendered_once and mode_id == last_mode_id:
                self.console.rule(mode.name.upper())
            self.console.print(frame)
            self._rendered_once = True
            last_mode_id = mode_id

    # ---------- сигналы ----------

    def _install_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.request_stop)
            except (NotImplementedError, RuntimeError, ValueError):
                try:
                    signal.signal(sig, lambda *_: self.request_stop())
                except (ValueError, OSError):
                    pass  # Windows разрешает сигналы только в главном потоке

    # ---------- глобальные команды ----------

    def _install_global_commands(self) -> None:
        self.registry.register_many(
            [
                Command("help", self._cmd_help, "help [тема] — команды или статья wiki", "core"),
                Command("wiki", self._cmd_wiki, "wiki [тема] — база знаний", "core"),
                Command("mod", self._cmd_mod, "mod list|enable|disable|reload <name>", "core"),
                Command("update", self._cmd_update, "update check|install", "core"),
                Command("mode", self._cmd_mode, "mode menu|lobby|tutorial|campaign|sandbox", "core"),
                Command("id", self._cmd_id, "id — ваш Messenger ID", "core"),
                Command("host", self._cmd_host, "host [port] — создать комнату", "core", ("create-room",)),
                Command("join", self._cmd_join, "join <ip> [port] — присоединиться по IP", "core", ("join-room",)),
                Command("msg", self._cmd_msg, "msg <MessengerID> <текст> — личное сообщение", "core", ("say",)),
                Command("peers", self._cmd_peers, "peers — участники комнаты", "core"),
                Command("leave", self._cmd_leave, "leave — выйти из комнаты", "core"),
                Command("empire", self._cmd_empire, "empire [build|status|rootkit]", "core"),
                Command("scan", self._cmd_scan, "/scan <игровой-IP> — разведка узла", "core"),
                Command("trace", self._cmd_trace, "/trace <игровой-IP> — распутать VPN-цепочку", "core"),
                Command("breach", self._cmd_breach, "breach <игровой-IP> [--captcha] — атака на узел", "core"),
                Command("save", self._cmd_save, "save — записать сейв", "core"),
                Command("quit", self._cmd_quit, "quit — выход", "core", ("exit", "q")),
            ]
        )

    async def _cmd_help(self, _engine: "Engine", *args: str) -> str:
        if args:
            query = " ".join(args).lstrip("/")
            command = self.registry.get(query.split()[0])
            parts: list[str] = []
            if command:
                parts.append(f"[bold cyan]/{command.name}[/bold cyan] — {command.help}")
            article = await self.wiki.article(query)
            parts.append(article)
            return "\n\n".join(parts)
        return (
            "[bold cyan]hackmeskay — команды[/bold cyan]\n"
            + self.registry.help_text()
            + "\n\n[dim]Команды можно вводить и с `/`: /help /scan. "
            "help <команда> показывает справку и статью wiki.[/dim]"
        )

    async def _cmd_wiki(self, _engine: "Engine", *args: str) -> str:
        if not args:
            return self.wiki.index()
        return await self.wiki.article(" ".join(args))

    async def _cmd_mod(self, _engine: "Engine", *args: str) -> str:
        return await self.mods.handle(list(args))

    async def _cmd_update(self, _engine: "Engine", *args: str) -> str:
        action = args[0].lower() if args else "check"
        if action == "check":
            return await self.updater.check(force=True)
        if action == "install":
            return await self.updater.install()
        return "использование: update check | update install"

    async def _cmd_mode(self, _engine: "Engine", *args: str) -> str:
        if not args:
            return ", ".join(self.modes)
        return await self.switch_mode(args[0].lower())

    # ---------- сеть и империя ----------

    async def _cmd_id(self, _engine: "Engine", *_args: str) -> str:
        assert self.network
        return f"ваш Messenger ID: [bold green]{self.network.identity}[/bold green]"

    async def _cmd_host(self, _engine: "Engine", *args: str) -> str:
        assert self.network
        port = int(args[0]) if args and args[0].isdigit() else 45678
        try:
            return await self.network.host(port)
        except OSError as exc:
            return f"[red]не удалось создать комнату: {exc}[/red]"

    async def _cmd_join(self, _engine: "Engine", *args: str) -> str:
        assert self.network
        if not args:
            return "использование: join <IP-хоста> [port]"
        port = int(args[1]) if len(args) > 1 and args[1].isdigit() else 45678
        try:
            return await self.network.join(args[0], port)
        except (OSError, ConnectionError) as exc:
            return f"[red]подключение не удалось: {exc}[/red]"

    async def _cmd_msg(self, _engine: "Engine", *args: str) -> str:
        assert self.network
        if len(args) < 2:
            return "использование: msg <MessengerID> <текст>"
        return await self.network.send(args[0], " ".join(args[1:]))

    async def _cmd_peers(self, _engine: "Engine", *_args: str) -> str:
        assert self.network
        peers = self.network.peer_ids()
        return "участники: " + (", ".join(peers) or "(только вы)")

    async def _cmd_leave(self, _engine: "Engine", *_args: str) -> str:
        assert self.network
        return await self.network.leave()

    async def _cmd_empire(self, _engine: "Engine", *args: str) -> str:
        assert self.empire and self.network
        owner = str(self.network.identity)
        action = args[0].lower() if args else "status"
        if action == "build":
            gateway = self.empire.build_empire(owner)
            return f"империя построена. gateway: {gateway.game_ip}\n{self.empire.status(owner)}"
        if action == "rootkit":
            node_id = args[1] if len(args) > 1 else ""
            return self.empire.install_rootkit(node_id, owner)
        return self.empire.status(owner)

    async def _cmd_scan(self, _engine: "Engine", *args: str) -> str:
        assert self.empire and self.network
        if not args:
            return "использование: /scan <игровой-IP>"
        result = self.empire.scan(args[0], str(self.network.identity))
        if self.network.is_online:
            await self.network.broadcast_event({"kind": "scan", "target": args[0]})
        if "error" in result:
            return f"[yellow]{result['error']}[/yellow]"
        lines = [f"цель: {result['ip']}"]
        lines += [f"  {name:<12} {version}" for name, version in result["services"].items()]
        lines.append("уязвимости: " + (", ".join(result["vulnerabilities"]) or "не найдены"))
        if result.get("forged"):
            lines.append("[red]ВНИМАНИЕ: логи подменены руткитом[/red]")
        return "\n".join(lines)

    async def _cmd_trace(self, _engine: "Engine", *args: str) -> str:
        assert self.empire and self.network
        if not args:
            return "использование: /trace <игровой-IP>"
        chain = self.empire.trace(args[0], str(self.network.identity))
        return " -> ".join(chain)

    async def _cmd_breach(self, _engine: "Engine", *args: str) -> str:
        assert self.empire and self.network
        if not args:
            return "использование: breach <игровой-IP> [--captcha]"
        result = self.empire.breach(args[0], str(self.network.identity), bypass_captcha="--captcha" in args)
        if self.network.is_online:
            await self.network.broadcast_event({"kind": "breach", "target": args[0], "ok": result["ok"]})
        return f"[green]узел захвачен: {result['node']}[/green]" if result["ok"] else f"[yellow]{result['reason']}[/yellow]"

    async def _cmd_save(self, _engine: "Engine", *_args: str) -> str:
        self.state.value.save()
        return "сейв сохранён в saves/state.json"

    async def _cmd_quit(self, _engine: "Engine", *_args: str) -> str:
        self.request_stop()
        return "выход..."
