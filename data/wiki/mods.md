# Как писать моды

Мод — это папка `mods/<name>/` с файлами `manifest.json` и `main.py`.

## manifest.json
```json
{
  "name": "my_mod",
  "version": "0.1.0",
  "description": "Мой первый мод",
  "author": "operator",
  "entrypoint": "main.py",
  "api_version": "1",
  "commands": ["ping"],
  "enabled_by_default": false
}
```

## main.py
```python
from hackmeskay.core.registry import Command

async def setup(ctx):
    async def ping(engine, *args):
        return "pong"

    ctx.registry.register(
        Command(name="ping", handler=ping, help="mod: ping", owner=ctx.manifest.name)
    )
    ctx.bus.subscribe("tick", lambda event: None, owner=ctx.manifest.name)

def teardown():
    # реестр и подписки снимает ModManager; здесь — только свои ресурсы
    pass
```

Управление: `mod list`, `mod enable my_mod`, `mod disable my_mod`,
`mod reload my_mod`. Состояние пишется в `mods/mods.json`.
При `disable` команды исчезают из `help` мгновенно, без перезапуска.

Имя мода: латиница, цифры, `_`, `-`, `.`; не начинается с цифры.
