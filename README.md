# hackmeskay

Терминальная хакерская MMO (Linux + Windows). Вся «атака» происходит внутри
виртуальной сети mesh — это игра, а не набор реальных утилит.

## Запуск из исходников

```bash
cd hackmeskay
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PYTHONPATH=src                                # Windows: $env:PYTHONPATH="src"
python -m hackmeskay
```

## Структура

```
hackmeskay/
├── src/hackmeskay/
│   ├── core/          paths, config, state, events, registry, console,
│   │                  modmanager, updater, engine, atomic
│   ├── modes/         base, menu, campaign, tutorial/, sandbox/
│   ├── net/           identity.py, protocol.py, room.py, empire.py
│   ├── services/      wiki.py
│   └── ui/            theme.py
├── examples/          modmanager_demo.py
├── data/              campaign/missions.json, wiki/*.md
├── mods/              mods.json + папки модов            ← не трогает updater
├── saves/             state.json                         ← не трогает updater
├── config/            settings.json                      ← не трогает updater
├── deploy/            update.json (сервер обновлений)
└── build/             скрипты PyInstaller/AppImage
```

## Команды

`help`, `wiki [тема]`, `mod list|enable|disable|reload <name>`,
`update check|install`, `mode menu|tutorial|campaign|sandbox`, `save`, `quit`.

Сеть: `network`, `host [port]`, `join <IP> [port]`, `id`, `peers`,
`msg <MessengerID> <текст>`, `leave`. Империя: `empire build|status|rootkit`,
`/scan <игровой-IP>`, `/trace <игровой-IP>`, `breach <IP> [--captcha]`.
Команды принимаются и с префиксом `/` (`/help /scan`).

В меню: `play`, `tutorial`, `campaign [n]`, `sandbox [1-5]`.
В кампании: `mission list|start <n>|status|abort` и тематические команды.

## Сборка

- Windows: `powershell -ExecutionPolicy Bypass -File build/build_windows.ps1`
- Linux: `bash build/build_linux.sh` (нужен `appimagetool`)

Готовые бинарники появляются в `dist/`. Папки `mods/`, `saves/`, `config/`
создаются рядом с бинарником при первом запуске и никогда не перезаписываются
при обновлении.

## Обновления

Задай `update_url` в `config/settings.json` (или в `core/config.py` по умолчанию).
Формат — `deploy/update.json`. Апдейтер проверяет SHA-256 и размер, делает backup,
на Linux меняет AppImage атомарно, на Windows ставит замену через отдельный
detached PowerShell-процесс после выхода игры. Сейвы/конфиги/моды изолированы.
Для продакшена добавь подпись релиза (TODO в `updater._verify`).
