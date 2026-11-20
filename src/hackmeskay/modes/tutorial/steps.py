"""Шаги обучения. Добавление шага = новая запись в TUTORIAL_STEPS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class TutorialStep:
    id: str
    title: str
    command: str
    hint: str
    success: str
    validator: Callable[[str], bool]


def _first_is(expected: str):
    def check(line: str) -> bool:
        parts = line.strip().lower().split()
        return bool(parts) and parts[0] == expected

    return check


TUTORIAL_STEPS: tuple[TutorialStep, ...] = (
    TutorialStep(
        id="help",
        title="1/7. Справочник",
        command="/help",
        hint="Введи `/help` — откроется умный справочник по командам.",
        success="Справочник работает. `/help /scan` покажет справку по команде.",
        validator=_first_is("/help"),
    ),
    TutorialStep(
        id="ls",
        title="2/7. Осмотр системы",
        command="ls",
        hint="Введи `ls`, чтобы увидеть файлы в текущем каталоге.",
        success="Правильно. Скрытые файлы видны через `ls -a`.",
        validator=_first_is("ls"),
    ),
    TutorialStep(
        id="cd",
        title="3/7. Навигация",
        command="cd",
        hint="Введи `cd /var/log`, чтобы перейти в каталог логов.",
        success="Переход выполнен. Путь сохранён в сессии.",
        validator=_first_is("cd"),
    ),
    TutorialStep(
        id="scan",
        title="4/7. Разведка Серверной Империи",
        command="/scan",
        hint="Введи `/scan <игровой-IP>` — цель показана в панели ниже.",
        success="Разведка выполнена: видны версии сервисов и уязвимости.",
        validator=_first_is("/scan"),
    ),
    TutorialStep(
        id="net-scan",
        title="5/7. Разведка сети",
        command="net-scan",
        hint="Введи `net-scan` — это найдёт узлы в виртуальной сети mesh.",
        success="Узлы обнаружены. Теперь можно подключиться.",
        validator=_first_is("net-scan"),
    ),
    TutorialStep(
        id="connect",
        title="6/7. Подключение",
        command="connect",
        hint="Введи `connect node-01`, чтобы открыть сессию с узлом.",
        success="Сессия установлена. Осталось подобрать ключ.",
        validator=_first_is("connect"),
    ),
    TutorialStep(
        id="hack",
        title="7/7. Взлом",
        command="hack",
        hint="Введи `hack node-01`, чтобы подобрать пароль виртуального узла.",
        success="Узел взломан. Обучение завершено — кампания открыта.",
        validator=_first_is("hack"),
    ),
)
