"""Точка входа: python -m hackmeskay / сгенерированный .exe / AppImage."""

from __future__ import annotations

import asyncio
import logging
import sys

from .core.config import SettingsStore
from .core.console import GameConsole
from .core.engine import Engine
from .core.events import EventBus
from .core.modmanager import ModManager
from .core.paths import ensure_layout
from .core.registry import CommandRegistry
from .core.state import StateStore
from .core.updater import UpdateManager
from .modes.campaign import CampaignMode
from .modes.lobby import LobbyMode
from .modes.menu import MenuMode
from .modes.sandbox import SandboxMode
from .modes.tutorial import TutorialMode
from .net import NetworkManager, load_or_create_identity
from .net.empire import EmpireState
from .services.wiki import WikiService


def build_engine() -> Engine:
    ensure_layout()
    settings = SettingsStore()
    console = GameConsole(ascii_only=settings.value.ascii_only)
    registry = CommandRegistry()
    bus = EventBus()
    state = StateStore()
    mods = ModManager(registry=registry, bus=bus, settings=settings.value.as_dict())
    updater = UpdateManager(settings.value.update_url, settings)
    wiki = WikiService()
    network = NetworkManager(load_or_create_identity())
    empire = EmpireState()

    engine = Engine(
        console=console,
        registry=registry,
        bus=bus,
        state_store=state,
        settings_store=settings,
        mods=mods,
        updater=updater,
        wiki=wiki,
        network=network,
        empire=empire,
    )
    for mode in (MenuMode(), LobbyMode(), TutorialMode(), CampaignMode(), SandboxMode()):
        engine.register_mode(mode)
    return engine


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    engine = build_engine()
    try:
        asyncio.run(engine.run("menu"))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
