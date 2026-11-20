"""Кроссплатформенное разрешение путей.

Портативный режим (AppImage / .exe): все пользовательские данные лежат РЯДОМ
с бинарником. Режим из исходников: данные лежат в пользовательской директории
(%APPDATA%, XDG_DATA_HOME) либо по переменной HACKMESKAY_HOME.

UPDATER НИКОГДА не пишет в PROTECTED_DIRS.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "hackmeskay"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False)) or bool(getattr(sys, "_MEIPASS", None))


def _base_dir() -> Path:
    # Явный override полезен для разработки/тестов и должен иметь приоритет.
    override = os.environ.get("HACKMESKAY_HOME")
    if override:
        return Path(override).expanduser().resolve()
    # AppImage монтируется в /tmp/.mount_XXX: sys.executable указывает внутрь
    # read-only образа. Настоящий «корень игры» — каталог с самим .AppImage.
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return Path(appimage).resolve().parent
    if is_frozen():
        return Path(sys.executable).resolve().parent
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return root / APP_NAME


BASE_DIR = _base_dir()


def _game_root() -> Path:
    """Корень игры: рядом с бинарником, либо корень репозитория для исходников."""
    override = os.environ.get("HACKMESKAY_HOME")
    if override:
        return Path(override).expanduser().resolve()
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return Path(appimage).resolve().parent
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


GAME_ROOT = _game_root()

# mods/ всегда лежит в корне игры — это требование формата модов
MODS_DIR = GAME_ROOT / "mods"
SAVES_DIR = BASE_DIR / "saves"
CONFIG_DIR = BASE_DIR / "config"
UPDATES_DIR = BASE_DIR / "updates"

# каталоги, которые апдейтер обязан сохранить в неприкосновенности
PROTECTED_DIRS: tuple[Path, ...] = (SAVES_DIR, CONFIG_DIR, MODS_DIR)


def _find_data_dir() -> Path:
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "data")
    here = Path(__file__).resolve()
    candidates.extend(
        [
            here.parents[3] / "data",  # src/hackmeskay/core -> корень проекта
            here.parents[1] / "data",  # установленный пакет
            Path.cwd() / "data",
        ]
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


DATA_DIR = _find_data_dir()


def ensure_layout() -> None:
    """Создать недостающие каталоги и дефолтные JSON (без перезаписи существующих)."""
    for directory in (BASE_DIR, MODS_DIR, SAVES_DIR, CONFIG_DIR, UPDATES_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    mods_state = MODS_DIR / "mods.json"
    if not mods_state.exists():
        mods_state.write_text(
            '{"version": 1, "mods": {"example_mod": {"enabled": true}}}\n',
            encoding="utf-8",
        )

    settings = CONFIG_DIR / "settings.json"
    if not settings.exists():
        settings.write_text(
            '{"ascii_only": false, "tick_rate": 20, "auto_check_updates": true, '
            '"update_url": "https://raw.githubusercontent.com/skayinray/hackmeskay/main/deploy/update.json"}\n',
            encoding="utf-8",
        )

    (BASE_DIR / "history.txt").touch(exist_ok=True)
