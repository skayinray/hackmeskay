"""Комнаты LAN: асинхронный сервер хоста и клиент.

Хост слушает на выбранном порту, каждый клиент проходит X25519-handshake
и регистрирует свой Messenger ID. Дальше сообщения адресуются по ID,
реальный IP хранится только внутри Peer и никогда не попадает в UI.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from .identity import MessengerID
from .protocol import ProtocolError, Session

log = logging.getLogger("hackmeskay.net")


@dataclass(slots=True)
class NetMessage:
    kind: str  # chat | system | event | peers
    sender: str
    recipient: str
    text: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Peer:
    messenger_id: str
    session: Session
    tasks: set[asyncio.Task[Any]] = field(default_factory=set)


class RoomHost:
    """Хост комнаты: asyncio.start_server + маршрутизация по Messenger ID."""

    def __init__(self, identity: MessengerID, inbound: asyncio.Queue[NetMessage], port: int = 45678) -> None:
        self.identity = identity
        self.inbound = inbound
        self.port = port
        self.peers: dict[str, Peer] = {}
        self._server: asyncio.AbstractServer | None = None

    async def start(self, bind: str = "0.0.0.0") -> "RoomHost":
        self._server = await asyncio.start_server(self._handle_client, host=bind, port=self.port)
        if self.port == 0:
            self.port = self._server.sockets[0].getsockname()[1]
        asyncio.create_task(self._server.serve_forever(), name="room-server")
        await self.notify("комната создана", f"порт {self.port}; ваш ID: {self.identity}")
        return self

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for peer in list(self.peers.values()):
            await peer.session.close()
        self.peers.clear()

    async def _handle_client(self, reader: Any, writer: Any) -> None:
        session = Session(reader, writer, role="host")
        peer_id = "?"
        try:
            await session.handshake()
            first = await session.recv()
            if first.get("t") != "register":
                raise ProtocolError("ожидался register")
            peer_id = str(first["id"])
            if peer_id in self.peers or peer_id == str(self.identity):
                await session.send({"t": "error", "text": "Messenger ID уже занят"})
                raise ProtocolError("дубликат Messenger ID")
            self.peers[peer_id] = Peer(peer_id, session)
            await self.notify("system", f"{peer_id} подключился")
            await self._send_peer_list()
            while True:
                message = await session.recv()
                await self._route(peer_id, message)
        except (ProtocolError, asyncio.IncompleteReadError, ConnectionResetError, OSError) as exc:
            log.info("клиент %s отключился: %s", peer_id, exc)
        finally:
            self.peers.pop(peer_id, None)
            await session.close()
            if peer_id != "?":
                await self.notify("system", f"{peer_id} вышел из комнаты")
                await self._send_peer_list()

    async def _route(self, sender_id: str, message: dict[str, Any]) -> None:
        kind = message.get("t")
        if kind == "chat":
            recipient = str(message.get("to", ""))
            text = str(message.get("text", ""))[:4000]
            if recipient == str(self.identity):
                await self.inbound.put(NetMessage("chat", sender_id, recipient, text))
            elif recipient in self.peers:
                # поле from всегда подменяется на авторизованный ID
                await self.peers[recipient].session.send(
                    {"t": "chat", "from": sender_id, "to": recipient, "text": text}
                )
            else:
                await self.peers[sender_id].session.send(
                    {"t": "system", "text": f"нет участника с ID {recipient}"}
                )
        elif kind == "event":
            for peer_id, peer in self.peers.items():
                if peer_id != sender_id:
                    await peer.session.send(
                        {"t": "event", "from": sender_id, "payload": message.get("payload", {})}
                    )
            await self.inbound.put(
                NetMessage("event", sender_id, "*", payload=dict(message.get("payload", {})))
            )
        elif kind == "peers":
            await self._send_peer_list()

    async def _send_peer_list(self) -> None:
        ids = [str(self.identity), *self.peers.keys()]
        for peer in self.peers.values():
            await peer.session.send({"t": "peers", "ids": ids})

    async def notify(self, kind: str, text: str) -> None:
        await self.inbound.put(NetMessage(kind, "host", "*", text))

    async def send_chat(self, to: str, text: str) -> bool:
        if to in self.peers:
            await self.peers[to].session.send(
                {"t": "chat", "from": str(self.identity), "to": to, "text": text}
            )
            return True
        return False

    async def broadcast_event(self, payload: dict[str, Any]) -> None:
        for peer in self.peers.values():
            await peer.session.send({"t": "event", "from": str(self.identity), "payload": payload})

    def peer_ids(self) -> list[str]:
        return [str(self.identity), *self.peers.keys()]


class RoomClient:
    """Клиент комнаты: подключение по реальному IP, дальше только Messenger ID."""

    def __init__(self, identity: MessengerID, host: str, inbound: asyncio.Queue[NetMessage], port: int = 45678) -> None:
        if not host.strip():
            raise ValueError("не указан IP хоста")
        self.identity = identity
        self.host = host.strip()
        self.port = port
        self.inbound = inbound
        self.session: Session | None = None
        self.peer_ids: list[str] = []
        self._task: asyncio.Task[Any] | None = None

    async def connect(self) -> "RoomClient":
        reader, writer = await asyncio.open_connection(self.host, self.port)
        self.session = await Session(reader, writer, role="client").handshake()
        await self.session.send({"t": "register", "id": str(self.identity)})
        self._task = asyncio.create_task(self._read_loop(), name="room-client")
        await self.inbound.put(NetMessage("system", "host", "*", f"подключено к комнате {self.host}"))
        return self

    async def _read_loop(self) -> None:
        assert self.session is not None
        try:
            while True:
                message = await self.session.recv()
                kind = message.get("t")
                if kind == "chat":
                    await self.inbound.put(
                        NetMessage("chat", str(message.get("from", "?")),
                                   str(message.get("to", "?")), str(message.get("text", "")))
                    )
                elif kind == "peers":
                    self.peer_ids = [str(i) for i in message.get("ids", [])]
                    await self.inbound.put(NetMessage("peers", "host", "*", ", ".join(self.peer_ids)))
                elif kind == "event":
                    await self.inbound.put(
                        NetMessage("event", str(message.get("from", "?")), "*",
                                   payload=dict(message.get("payload", {})))
                    )
                else:
                    await self.inbound.put(NetMessage("system", "host", "*", str(message.get("text", ""))))
        except (ProtocolError, asyncio.IncompleteReadError, ConnectionResetError, OSError) as exc:
            await self.inbound.put(NetMessage("system", "host", "*", f"соединение потеряно: {exc}"))

    async def send_chat(self, to: str, text: str) -> None:
        if self.session is None:
            raise RuntimeError("нет подключения к комнате")
        await self.session.send(
            {"t": "chat", "from": str(self.identity), "to": to, "text": text[:4000]}
        )

    async def broadcast_event(self, payload: dict[str, Any]) -> None:
        if self.session is None:
            raise RuntimeError("нет подключения к комнате")
        await self.session.send({"t": "event", "from": str(self.identity), "payload": payload})

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self.session:
            await self.session.close()
            self.session = None


class NetworkManager:
    """Фасад, который использует движок и консоль."""

    def __init__(self, identity: MessengerID, inbound: asyncio.Queue[NetMessage] | None = None) -> None:
        self.identity = identity
        self.inbound = inbound or asyncio.Queue()
        self.current: RoomHost | RoomClient | None = None

    @property
    def is_online(self) -> bool:
        return self.current is not None

    async def host(self, port: int = 45678, bind: str = "0.0.0.0") -> str:
        if self.current:
            return "сначала выйди из комнаты: leave"
        self.current = await RoomHost(self.identity, self.inbound, port).start(bind)
        return f"комната создана на порту {port}; ваш Messenger ID: {self.identity}"

    async def join(self, ip: str, port: int = 45678) -> str:
        if self.current:
            return "сначала выйди из комнаты: leave"
        client = RoomClient(self.identity, ip, self.inbound, port)
        await client.connect()
        self.current = client
        return f"подключено к {ip}; ваш Messenger ID: {self.identity}"

    async def leave(self) -> str:
        if not self.current:
            return "вы не в комнате"
        if isinstance(self.current, RoomHost):
            await self.current.stop()
        else:
            await self.current.close()
        self.current = None
        return "вы вышли из комнаты"

    async def send(self, to: str, text: str) -> str:
        if not self.current:
            return "нет подключения к комнате"
        if isinstance(self.current, RoomHost):
            ok = await self.current.send_chat(to, text)
            return "сообщение отправлено" if ok else f"нет участника {to}"
        await self.current.send_chat(to, text)
        return "сообщение отправлено"

    async def broadcast_event(self, payload: dict[str, Any]) -> None:
        if self.current:
            await self.current.broadcast_event(payload)

    def peer_ids(self) -> list[str]:
        if isinstance(self.current, RoomHost):
            return self.current.peer_ids()
        if isinstance(self.current, RoomClient):
            return self.current.peer_ids
        return []
