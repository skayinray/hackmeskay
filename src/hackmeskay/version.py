"""Единственный источник правды о версии (используется и updater'ом)."""

__version__ = "0.1.1"


def version_tuple(value: str) -> tuple[int, ...]:
    """Сравнимая кортежная версия: 'v0.2.1-beta+build' -> (0, 2, 1)."""
    core = value.strip().lstrip("vV").split("+", 1)[0].split("-", 1)[0]
    return tuple(int(part) if part.isdigit() else 0 for part in core.split("."))
