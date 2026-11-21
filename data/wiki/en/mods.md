# Writing mods

A mod is a folder `mods/<name>/` with `manifest.json` and `main.py`.

## manifest.json

```json
{
  "name": "my_mod",
  "version": "0.1.0",
  "description": "My first mod",
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
    # ModManager removes registrations and subscriptions; clean up only your
    # own resources here.
    pass
```

Use `mod list`, `mod enable my_mod`, `mod disable my_mod` and
`mod reload my_mod` to manage mods. State is written to `mods/mods.json`.
When a mod is disabled its commands disappear from `help` immediately, without
a restart.

Mod names may use Latin letters, digits, `_`, `-` and `.`. They must not start
with a digit.
