"""Демонстрация динамического ModManager без запуска всего движка.

Запуск: PYTHONPATH=src python examples/modmanager_demo.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hackmeskay.core.events import EventBus
from hackmeskay.core.modmanager import ModManager
from hackmeskay.core.registry import CommandRegistry

MANIFEST = """{
  "name": "demo_mod",
  "version": "1.0.0",
  "description": "демонстрация горячей подгрузки",
  "entrypoint": "main.py",
  "api_version": "1",
  "commands": ["demo"]
}
"""

PLUGIN = """
from hackmeskay.core.registry import Command

async def setup(ctx):
    async def demo(engine, *args):
        return f"demo-мод отвечает: {' '.join(args) or 'ping'}"
    ctx.registry.register(Command(
        name="demo", handler=demo, help="демо-команда", owner=ctx.manifest.name
    ))

def teardown():
    pass
"""


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        mod_dir = root / "demo_mod"
        mod_dir.mkdir()
        (mod_dir / "manifest.json").write_text(MANIFEST, encoding="utf-8")
        (mod_dir / "main.py").write_text(PLUGIN, encoding="utf-8")

        registry = CommandRegistry()
        bus = EventBus()
        mods = ModManager(mods_dir=root, registry=registry, bus=bus)

        print("до включения:", registry.names())
        print(await mods.enable("demo_mod"))
        print("после включения:", registry.names())
        print(await registry.dispatch("demo привет", None))

        print(await mods.disable("demo_mod"))
        print("после отключения:", registry.names())
        print("файл состояния:", (root / "mods.json").read_text(encoding="utf-8").strip())


if __name__ == "__main__":
    asyncio.run(main())
