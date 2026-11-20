"""Зашифрованный transports для комнат.

Фрейм: [magic 4 bytes][length 4 bytes][payload]
 hello:  plaintext JSON с X25519 public key
 further: AESGCM ciphertext, nonce = 8-byte counter + 4-byte direction tag

Ключ: X25519 -> HKDF-SHA256(info=b'hackmeskay-p2p-v1').
Направления используют разные nonce, поэтому counters не конфликтуют.
Реальный IP не передается в multiplayer-сообщениях: только Messenger ID.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b"HMSK"
HEADER = struct.Struct(">4sI")
MAX_FRAME = 1024 * 1024


class ProtocolError(RuntimeError):
    pass


async def send_frame(writer: Any, payload: bytes) -> None:
    if len(payload) > MAX_FRAME:
        raise ProtocolError("слишком большой фрейм")
    writer.write(HEADER.pack(MAGIC, len(payload)) + payload)
    await writer.drain()


async def recv_frame(reader: Any) -> bytes:
    header = await reader.readexactly(HEADER.size)
    magic, length = HEADER.unpack(header)
    if magic != MAGIC or length > MAX_FRAME:
        raise ProtocolError("неверный заголовок фрейма")
    return await reader.readexactly(length)


@dataclass(slots=True)
class Session:
    """Одно зашифрованное соединение. role == 'host' на сервере, 'client' у клиента."""

    reader: Any
    writer: Any
    role: str
    private: X25519PrivateKey | None = None
    key: bytes | None = None
    _send_counter: int = 0
    _recv_counter: int = 0

    def __post_init__(self) -> None:
        if self.role not in {"host", "client"}:
            raise ValueError("role must be host or client")
        self.private = X25519PrivateKey.generate()

    async def handshake(self) -> "Session":
        assert self.private is not None
        public = self.private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        await send_frame(self.writer, json.dumps({"t": "hello", "pub": public.hex()}).encode())
        raw = await recv_frame(self.reader)
        hello = json.loads(raw)
        if hello.get("t") != "hello":
            raise ProtocolError("ожидался hello")
        peer = X25519PublicKey.from_public_bytes(bytes.fromhex(hello["pub"]))
        shared = self.private.exchange(peer)
        self.key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"hackmeskay-p2p-v1"
        ).derive(shared)
        return self

    def _nonce(self, counter: int, direction: str) -> bytes:
        # отправитель определяет тег: host -> 'H', client -> 'C'
        sender_is_host = (self.role == "host") if direction == "send" else (self.role == "client")
        tag = b"H" if sender_is_host else b"C"
        return counter.to_bytes(8, "big") + tag * 4

    async def send(self, message: dict[str, Any]) -> None:
        if self.key is None:
            raise ProtocolError("handshake не выполнен")
        plaintext = json.dumps(message, ensure_ascii=False).encode("utf-8")
        nonce = self._nonce(self._send_counter, "send")
        self._send_counter += 1
        await send_frame(self.writer, AESGCM(self.key).encrypt(nonce, plaintext, None))

    async def recv(self) -> dict[str, Any]:
        if self.key is None:
            raise ProtocolError("handshake не выполнен")
        ciphertext = await recv_frame(self.reader)
        nonce = self._nonce(self._recv_counter, "recv")
        self._recv_counter += 1
        plaintext = AESGCM(self.key).decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)

    async def close(self) -> None:
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except (ConnectionError, OSError):
            pass
