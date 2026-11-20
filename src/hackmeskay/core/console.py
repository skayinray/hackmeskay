"""Обёртка над Rich + prompt_toolkit.

На Windows явно включаем ANSI через colorama, чтобы цвета работали и в CMD,
и в PowerShell, и в Windows Terminal. При не-терминале/принудительном флаге
используем только ASCII.
"""

from __future__ import annotations

import asyncio
import os
import sys

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ..ui.theme import Glyphs, pick_glyphs, should_use_ascii
from .paths import BASE_DIR


class GameConsole:
    def __init__(self, ascii_only: bool | None = None) -> None:
        if sys.platform == "win32":
            try:
                from colorama import just_fix_windows_console

                just_fix_windows_console()
            except ImportError:
                pass
            # Wine/pipe и cp1251/cp866 консоли не умеют Unicode-рамки и баннер.
            # Принудительный UTF-8 + replace предотвращает UnicodeEncodeError.
            for stream in (sys.stdout, sys.stderr):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        self.console = Console(
            file=sys.stdout,
            highlight=False,
            markup=True,
            soft_wrap=False,
            emoji=False,
            legacy_windows=False,
            safe_box=True,
        )
        self.ascii_only = should_use_ascii(ascii_only, self.console.is_terminal)
        self.glyphs: Glyphs = pick_glyphs(self.ascii_only)
        self.session: PromptSession[str] | None = None
        if sys.stdin.isatty() and sys.stdout.isatty():
            try:
                self.session = PromptSession(
                    history=FileHistory(str(BASE_DIR / "history.txt")),
                    enable_history_search=True,
                    multiline=False,
                )
            except Exception:
                # unusual terminals: plain input fallback
                self.session = None

    def _bind_stream(self) -> None:
        # prompt_toolkit.patch_stdout подменяет sys.stdout во время ввода;
        # Console должен писать в актуальный поток, иначе вывод ломает prompt.
        self.console.file = sys.stdout

    def clear_screen(self) -> None:
        """Полностью чистит терминал и ставит курсор в самый верх.

        Вызывайте только в безопасный момент (не во время активного ввода),
        иначе prompt_toolkit-строка ввода может повредиться.
        """
        self._bind_stream()
        try:
            self.console.clear(home=True)
        except Exception:
            # ANSI: очистить экран и курсор в (1,1)
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    def print(self, message: object = "", **kwargs: object) -> None:
        self._bind_stream()
        self.console.print(message, **kwargs)

    def rule(self, title: str = "") -> None:
        self._bind_stream()
        char = self.glyphs.line
        width = max(20, min(self.console.width, 78))
        if title:
            label = f" {title} "
            side = max(2, (width - len(label)) // 2)
            tail = max(2, width - side - len(label))
            self.console.print(f"[dim cyan]{char * side}{label}{char * tail}[/dim cyan]")
        else:
            self.console.print(f"[dim cyan]{char * width}[/dim cyan]")

    def panel(self, text: str, title: str = "", style: str = "green") -> None:
        self._bind_stream()
        self.console.print(Panel(Text.from_markup(text), title=title, border_style=style, expand=False))

    async def readline(self, prompt: str = "hack@mesh:~> ") -> str:
        if self.session is None:
            return await asyncio.to_thread(input, prompt)
        with patch_stdout():
            return await self.session.prompt_async(prompt)
