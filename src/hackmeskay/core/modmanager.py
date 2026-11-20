"""Менеджер модов/плагинов hackmeskay.

Возможности:
  * discovery по папкам mods/<name>/manifest.json;
  * JSON-состояние mods/mods.json (enabled/disabled) с атомарной записью;
  * горячее включение/выключение: setup(ctx)/teardown() + снятие регистраций
    команд и подписок по owner'у + удаление модулей из sys.modules;
  * CLI: `mod list`, `mod enable <name>`, `mod disable <name>`, `mod reload <name>`;
  * фоновый watcher: изменения manifest.json перезагружают включённый мод.

Ограничение Python: «выгрузить» уже исполненный байткод полностью нельзя.
Мы убираем все ссылки (sys.modules, реестр команд, шину), поэтому мод
перестаёт влиять на игру; для жёсткой изоляции нужно запускать моды в
отдельном процессе (subprocess + RPC) — интерфейс ModContext это позволяет.
"""

from __future__ import annotations

import asyncio
import importlib.util
import inspect
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Awaitable, Callable

from .atomic import read_json, write_json_atomic
from .events import Event
from .paths import MODS_DIR

log = logging.getLogger("hackmeskay.mods")

SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
MODULE_PREFIX = "hackmeskay_mod_"


@dataclass(slots=True)
class ModManifest:
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: str = ""
    entrypoint: str = "main.py"
    api_version: str = "1"
    commands: tuple[str, ...] = ()
    enabled_by_default: bool = False

    @classmethod
    def from_dir(cls, mod_dir: Path) -> "ModManifest":
        raw = read_json(mod_dir / "manifest.json", None)
        if not isinstance(raw, dict):
            raise ValueError("manifest.json отсутствует или не объект")
        name = str(raw.get("name", mod_dir.name))
        if not SAFE_NAME.fullmatch(name) or name != mod_dir.name:
            raise ValueError(f"небезопасное имя мода: {name!r}")
        entrypoint = Path(str(raw.get("entrypoint", "main.py")))
        if entrypoint.is_absolute() or ".." in entrypoint.parts:
            raise ValueError("entrypoint должен быть относительным путём")
        return cls(
            name=name,
            version=str(raw.get("version", "0.0.0")),
            description=str(raw.get("description", "")),
            author=str(raw.get("author", "")),
            entrypoint=str(entrypoint),
            api_version=str(raw.get("api_version", "1")),
            commands=tuple(str(c) for c in raw.get("commands", [])),
            enabled_by_default=bool(raw.get("enabled_by_default", False)),
        )


@dataclass(slots=True)
class ModContext:
    """API, передаваемое моду в setup(ctx)."""

    engine: Any
    registry: Any
    bus: Any
    log: logging.Logger
    config: dict[str, Any]
    manifest: ModManifest
    mod_dir: Path

    async def emit(self, topic: str, **payload: Any) -> None:
        await self.bus.publish(Event(topic, payload))


@dataclass
class LoadedMod:
    manifest: ModManifest
    module: ModuleType
    context: ModContext
    mtime: float


Result = Awaitable[str | None] | str | None


class ModManager:
    """Динамический менеджер плагинов. Все публичные методы идемпотентны."""

    def __init__(
        self,
        mods_dir: Path = MODS_DIR,
        registry: Any = None,
        bus: Any = None,
        engine: Any = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        self.mods_dir = mods_dir
        self.state_file = mods_dir / "mods.json"
        self.registry = registry
        self.bus = bus
        self.engine = engine
        self.settings = settings or {}
        self._state: dict[str, bool] = {}
        self._loaded: dict[str, LoadedMod] = {}
        self._lock = asyncio.Lock()
        self._load_state()

    # ---------- состояние ----------

    def _load_state(self) -> None:
        raw = read_json(self.state_file, {"version": 1, "mods": {}})
        mods = raw.get("mods", {}) if isinstance(raw, dict) else {}
        self._state = {
            name: bool(info.get("enabled", False)) if isinstance(info, dict) else bool(info)
            for name, info in mods.items()
            if SAFE_NAME.fullmatch(str(name))
        }

    def _save_state(self) -> None:
        write_json_atomic(
            self.state_file,
            {"version": 1, "mods": {name: {"enabled": enabled} for name, enabled in self._state.items()}},
        )

    # ---------- discovery ----------

    def discover(self) -> dict[str, ModManifest]:
        found: dict[str, ModManifest] = {}
        if not self.mods_dir.is_dir():
            return found
        for child in sorted(self.mods_dir.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            try:
                found[child.name] = ModManifest.from_dir(child)
            except Exception as exc:
                log.warning("мод пропущен: %s", child.name)
                log.debug("причина: %s", exc)
        return found

    def is_enabled(self, name: str) -> bool:
        return self._state.get(name, False)

    def list_mods(self) -> list[tuple[str, str, bool, bool, str]]:
        rows = []
        for name, manifest in self.discover().items():
            if name not in self._state and manifest.enabled_by_default:
                self._state[name] = True
                self._save_state()
            rows.append(
                (
                    name,
                    manifest.version,
                    self.is_enabled(name),
                    name in self._loaded,
                    manifest.description,
                )
            )
        return rows

    # ---------- загрузка ----------

    def _import(self, manifest: ModManifest) -> ModuleType:
        module_name = f"{MODULE_PREFIX}{manifest.name}"
        entrypoint = (self.mods_dir / manifest.name / manifest.entrypoint).resolve()
        if not entrypoint.is_file():
            raise FileNotFoundError(entrypoint)
        # submodule_search_locations позволяет моду использовать `from .helpers import ...`
        spec = importlib.util.spec_from_file_location(
            module_name, entrypoint, submodule_search_locations=[str(entrypoint.parent)]
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"не удалось импортировать {entrypoint}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        return module

    def _purge_module(self, name: str) -> None:
        prefix = f"{MODULE_PREFIX}{name}"
        for key in [k for k in sys.modules if k == prefix or k.startswith(prefix + ".")]:
            sys.modules.pop(key, None)
        importlib.invalidate_caches()

    async def enable(self, name: str) -> str:
        if not SAFE_NAME.fullmatch(name):
            return f"недопустимое имя мода: {name!r}"
        async with self._lock:
            if name in self._loaded:
                self._state[name] = True
                self._save_state()
                return f"мод уже включён: {name}"
            manifest = self.discover().get(name)
            if manifest is None:
                return f"мод не найден: {name}"
            mod_dir = self.mods_dir / name
            manifest_path = mod_dir / "manifest.json"
            context = ModContext(
                engine=self.engine,
                registry=self.registry,
                bus=self.bus,
                log=log.getChild(name),
                config=dict(self.settings),
                manifest=manifest,
                mod_dir=mod_dir,
            )
            try:
                module = self._import(manifest)
                setup = getattr(module, "setup", None)
                if not callable(setup):
                    raise RuntimeError("в моду нет setup(ctx)")
                result: Result = setup(context)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                self._purge_module(name)
                log.exception("не удалось включить мод %s", name)
                return f"ошибка включения {name}: {exc}"

            self._loaded[name] = LoadedMod(
                manifest=manifest,
                module=module,
                context=context,
                mtime=manifest_path.stat().st_mtime if manifest_path.exists() else 0.0,
            )
            self._state[name] = True
            self._save_state()
            if self.bus is not None:
                await self.bus.publish(Event("mod.enabled", {"name": name, "version": manifest.version}))
            return f"[green]включён[/green] {name}@{manifest.version}"

    async def disable(self, name: str, *, persist: bool = True) -> str:
        """Выгрузить мод. persist=False — не менять сохранённый флаг (для shutdown)."""
        if not SAFE_NAME.fullmatch(name):
            return f"недопустимое имя мода: {name!r}"
        async with self._lock:
            loaded = self._loaded.pop(name, None)
            if persist:
                self._state[name] = False
                self._save_state()
            if loaded is None:
                return f"мод отключён (не был загружен): {name}"

            # порядок важен: сначала запретить новые вызовы, потом гасить код
            if self.registry is not None:
                self.registry.unregister_owner(name)
            if self.bus is not None:
                teardown = getattr(loaded.module, "teardown", None)
                if callable(teardown):
                    try:
                        result = teardown()
                        if inspect.isawaitable(result):
                            await asyncio.wait_for(result, timeout=5)
                    except Exception as exc:
                        log.warning("teardown мода %s завершился ошибкой: %s", name, exc)
                self.bus.unsubscribe_owner(name)
            self._purge_module(name)
            if self.bus is not None:
                await self.bus.publish(Event("mod.disabled", {"name": name}))
            return f"[yellow]отключён[/yellow] {name} — команды выгружены"

    async def reload(self, name: str) -> str:
        await self.disable(name)
        return await self.enable(name)

    async def boot(self) -> None:
        """Включить все моды с enabled=true (вызывается при старте движка)."""
        for name, enabled in list(self._state.items()):
            if enabled:
                await self.enable(name)

    async def shutdown(self) -> None:
        """Снять код модов при выходе, но сохранить их включённое состояние."""
        for name in list(self._loaded):
            await self.disable(name, persist=False)

    # ---------- CLI ----------

    async def handle(self, args: list[str]) -> str:
        action = args[0].lower() if args else "list"
        if action == "list":
            lines = [f"{'ИМЯ':<20}{'ВЕРСИЯ':<10}{'СТАТУС':<12}{'ЗАГРУЖЕН':<10}ОПИСАНИЕ"]
            lines.append("-" * 72)
            for name, version, enabled, loaded, description in self.list_mods():
                status = "[green]вкл[/green]" if enabled else "[dim]выкл[/dim]"
                live = "да" if loaded else "нет"
                lines.append(f"{name:<20}{version:<10}{status:<22}{live:<10}{description}")
            return "\n".join(lines) or "моды не найдены"
        if action in {"enable", "disable", "reload"}:
            if len(args) < 2:
                return f"использование: mod {action} <name>"
            method: Callable[[str], Awaitable[str]] = getattr(self, action)
            return await method(args[1])
        if action == "discover":
            return ", ".join(self.discover()) or "(пусто)"
        return "использование: mod list | mod enable <name> | mod disable <name> | mod reload <name>"

    # ---------- горячее наблюдение за файлами ----------

    async def watch(self, stop: asyncio.Event, interval: float = 1.5) -> None:
        while not stop.is_set():
            try:
                for name, loaded in list(self._loaded.items()):
                    path = self.mods_dir / name / "manifest.json"
                    mtime = path.stat().st_mtime if path.is_file() else 0.0
                    if mtime != loaded.mtime:
                        await self.reload(name)
                for name, manifest in self.discover().items():
                    if name not in self._state and manifest.enabled_by_default:
                        await self.enable(name)
            except Exception:
                log.exception("ошибка в mod watcher")
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass
