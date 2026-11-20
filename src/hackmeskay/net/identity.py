"""Постоянный уникальный Messenger ID игрока.

Хранится в config/identity.json (защищённая апдейтером директория).
Формат: skay_user_<10 символов из алфавита 0-9a-z>.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import asdict, dataclass

from ..core.atomic import read_json, write_json_atomic
from ..core.paths import CONFIG_DIR

ALPHABET = string.ascii_lowercase + string.digits
PREFIX = "skay_user_"
SUFFIX_LEN = 10


@dataclass(frozen=True, slots=True)
class MessengerID:
    value: str

    @classmethod
    def generate(cls) -> "MessengerID":
        return cls(PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(SUFFIX_LEN)))

    def __str__(self) -> str:
        return self.value


def load_or_create_identity() -> MessengerID:
    path = CONFIG_DIR / "identity.json"
    raw = read_json(path, {})
    value = (raw.get("messenger_id") or raw.get("value")) if isinstance(raw, dict) else None
    if isinstance(value, str) and value.startswith(PREFIX) and len(value) == len(PREFIX) + SUFFIX_LEN:
        if all(ch in ALPHABET for ch in value[len(PREFIX):]):
            return MessengerID(value)
    identity = MessengerID.generate()
    write_json_atomic(path, {"messenger_id": str(identity)})
    return identity
