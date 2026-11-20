"""Пример мода: показывает горячую регистрацию/выгрузку команды."""

from hackmeskay.core.registry import Command


async def setup(ctx):
    async def ping(engine, *args):
        return f"pong от {ctx.manifest.name}@{ctx.manifest.version} (аргументы: {', '.join(args) or '—'})"

    ctx.registry.register(
        Command(name="ping", handler=ping, help="mod: ping — проверка мода", owner=ctx.manifest.name)
    )


def teardown():
    # реестр команд и подписки на события ModManager снимает сам
    pass
