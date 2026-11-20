"""ASCII/Unicode-глифы с безопасным фолбэком для CMD/PowerShell."""

from __future__ import annotations

import os
from dataclasses import dataclass

UNICODE = {
    "line": "─",
    "vline": "│",
    "corner": "+",
    "bullet": "•",
    "arrow": "→",
    "box_tl": "╭",
    "box_tr": "╮",
    "box_bl": "╰",
    "box_br": "╯",
}
ASCII = {
    "line": "-",
    "vline": "|",
    "corner": "+",
    "bullet": "*",
    "arrow": "->",
    "box_tl": "+",
    "box_tr": "+",
    "box_bl": "+",
    "box_br": "+",
}


@dataclass(frozen=True)
class Glyphs:
    line: str
    vline: str
    corner: str
    bullet: str
    arrow: str
    box_tl: str
    box_tr: str
    box_bl: str
    box_br: str


def pick_glyphs(ascii_only: bool) -> Glyphs:
    table = ASCII if ascii_only else UNICODE
    return Glyphs(**table)


def should_use_ascii(explicit: bool | None, is_terminal: bool) -> bool:
    forced = os.environ.get("HACKMESKAY_ASCII")
    if forced is not None:
        return forced not in {"0", "false", "no", ""}
    if explicit is not None:
        return explicit
    return not is_terminal


BANNER = r"""
 _                _                         _             

| |__   __ _  ___| | ___ __ ___   ___  ___| | ____ _ _   _ 
| '_ \ / _` |/ __| |/ / '_ ` _ \ / _ \/ __| |/ / _` | | | |
| | | | (_| | (__|   <| | | | | |  __/\__ \   < (_| | |_| |
|_| |_|\__,_|\___|_|\_\_| |_| |_|\___||___/_|\_\__,_|\__, |
                                                     |___/ 
""".strip("\n")
