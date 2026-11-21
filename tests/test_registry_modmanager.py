import asyncio
import json

from hackmeskay.core.modmanager import ModManager
from hackmeskay.core.registry import Command, CommandRegistry


def test_registry_dispatch_and_owner_removal():
    registry = CommandRegistry()

    async def handler(_engine, *args):
        return " ".join(("ok", *args))

    registry.register(Command(name="ping", handler=handler, owner="demo", aliases=("pong",)))
    assert registry.get("pong").name == "ping"
    assert asyncio.run(registry.dispatch("/ping one", None)) == "ok one"

    registry.unregister_owner("demo")
    assert registry.get("ping") is None
    assert registry.get("pong") is None


def test_modmanager_enable_and_disable(tmp_path):
    mod_dir = tmp_path / "demo_mod"
    mod_dir.mkdir()
    (mod_dir / "manifest.json").write_text(
        json.dumps({"name": "demo_mod", "version": "1.0.0", "entrypoint": "main.py"}),
        encoding="utf-8",
    )
    (mod_dir / "main.py").write_text(
        "from hackmeskay.core.registry import Command\n"
        "async def setup(ctx):\n"
        "    async def hello(engine, *args):\n"
        "        return 'hello'\n"
        "    ctx.registry.register(Command(name='hello', handler=hello, "
        "owner=ctx.manifest.name))\n",
        encoding="utf-8",
    )
    registry = CommandRegistry()
    manager = ModManager(mods_dir=tmp_path, registry=registry)

    async def scenario():
        assert manager.discover()["demo_mod"].version == "1.0.0"
        await manager.enable("demo_mod")
        assert registry.get("hello") is not None
        assert await registry.dispatch("hello", None) == "hello"
        await manager.disable("demo_mod")
        assert registry.get("hello") is None

    asyncio.run(scenario())
