"""Серверная империя — полностью виртуальная сеть.

Реальные сокеты здесь не используются: /scan, /trace, руткиты и вирусы
работают с SQLite-деревом нод. Игровые IP выдаются из диапазона 10.60.0.0/16
и не имеют отношения к сетевым интерфейсам машины.
"""

from __future__ import annotations

import json
import random
import secrets
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.paths import SAVES_DIR

KIND_GATEWAY = "gateway"
KIND_VPN = "vpn"
KIND_MAINFRAME = "mainframe"


@dataclass(slots=True)
class VNode:
    id: str
    owner: str
    kind: str
    game_ip: str
    firewall: int = 1
    captcha: bool = False
    rootkit: bool = False
    parent: str | None = None
    services: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)


class EmpireState:
    """SQLite-хранилище империй + операции разведки/взлома."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (SAVES_DIR / "empire.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._rng = random.Random()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL,
                    game_ip TEXT UNIQUE NOT NULL, firewall INTEGER NOT NULL,
                    captcha INTEGER NOT NULL, rootkit INTEGER NOT NULL,
                    parent TEXT, services TEXT NOT NULL, files TEXT NOT NULL
                )"""
            )

    def _row_to_node(self, row: sqlite3.Row) -> VNode:
        return VNode(
            id=row["id"], owner=row["owner"], kind=row["kind"], game_ip=row["game_ip"],
            firewall=int(row["firewall"]), captcha=bool(row["captcha"]),
            rootkit=bool(row["rootkit"]), parent=row["parent"],
            services=json.loads(row["services"]), files=json.loads(row["files"]),
        )

    def _new_game_ip(self, conn: sqlite3.Connection) -> str:
        while True:
            ip = f"10.60.{self._rng.randint(0, 255)}.{self._rng.randint(2, 254)}"
            if conn.execute("SELECT 1 FROM nodes WHERE game_ip=?", (ip,)).fetchone() is None:
                return ip

    def build_empire(self, owner: str) -> VNode:
        """Создать стартовую империю: gateway -> vpn -> mainframe."""
        with self._connect() as conn:
            if conn.execute("SELECT 1 FROM nodes WHERE owner=?", (owner,)).fetchone():
                return self._row_to_node(
                    conn.execute("SELECT * FROM nodes WHERE owner=? AND kind='gateway'", (owner,)).fetchone()
                )
            gateway = self.create_node(owner, KIND_GATEWAY, firewall=2, captcha=True)
            vpn = self.create_node(owner, KIND_VPN, parent=gateway.id, firewall=3)
            mainframe = self.create_node(owner, KIND_MAINFRAME, parent=vpn.id, firewall=5)
            self.write_file(mainframe.id, "/vault/wallet.key", "GM(next)-private-key-PLACEHOLDER")
            self.write_file(mainframe.id, "/etc/motd", "добро пожаловать в Серверную Империю")
            return gateway

    def create_node(
        self, owner: str, kind: str, *, parent: str | None = None,
        firewall: int = 1, captcha: bool = False, services: dict[str, str] | None = None,
    ) -> VNode:
        if kind not in {KIND_GATEWAY, KIND_VPN, KIND_MAINFRAME}:
            raise ValueError(f"неизвестный тип ноды: {kind}")
        node_id = f"{owner[:6]}-{secrets.token_hex(3)}"
        default_services = {
            KIND_GATEWAY: {"nginx": "1.24.0", "ssh": "OpenSSH_9.3"},
            KIND_VPN: {"wireguard": "1.0.20230315", "c2": "mesh/0.9"},
            KIND_MAINFRAME: {"postgres": "15.4", "vault": "1.15.0", "ssh": "OpenSSH_8.9"},
        }
        with self._connect() as conn:
            ip = self._new_game_ip(conn)
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?,?,?)",
                (node_id, owner, kind, ip, firewall, int(captcha), 0, parent,
                 json.dumps(services or default_services[kind]), "{}"),
            )
        return self.get_node(node_id)  # type: ignore[return-value]

    def get_node(self, node_id: str) -> VNode | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE id=?", (node_id,)).fetchone()
        return self._row_to_node(row) if row else None

    def by_ip(self, game_ip: str) -> VNode | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE game_ip=?", (game_ip,)).fetchone()
        return self._row_to_node(row) if row else None

    def visible_nodes(self, observer: str | None = None) -> list[VNode]:
        """Сканирование видит только gateway'и (и свои ноды)."""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM nodes").fetchall()
        return [
            self._row_to_node(row) for row in rows
            if row["kind"] == KIND_GATEWAY or (observer and row["owner"] == observer)
        ]

    # ---------- механики ----------

    def scan(self, game_ip: str, observer: str) -> dict[str, Any]:
        """Симуляция /scan: версии сервисов и уязвимости. Не делает реальных запросов."""
        node = self.by_ip(game_ip)
        if node is None or (node.kind != KIND_GATEWAY and node.owner != observer):
            return {"error": "узел не найден (скрыт за VPN)"}
        if node.rootkit:
            # руткит подменяет логи и выдает ложный след
            return {
                "ip": game_ip, "forged": True, "services": {"nginx": "1.0.0"},
                "vulnerabilities": [], "hint": "логи подменены руткитом — /trace покажет обман",
            }
        vulns = []
        if node.firewall <= 2:
            vulns.append("WEAK-KEY")
        if node.captcha:
            vulns.append("CAPTCHA-BYPASS")
        if "OpenSSH_8" in " ".join(node.services.values()):
            vulns.append("OLD-SSH")
        return {"ip": game_ip, "services": node.services, "vulnerabilities": vulns,
                "firewall": node.firewall, "captcha": node.captcha}

    def trace(self, game_ip: str, observer: str) -> list[str]:
        """Распутывание VPN/C2-цепочки до Mainframe (только свои/взломанные ноды)."""
        node = self.by_ip(game_ip)
        if node is None or (node.owner != observer and node.kind != KIND_GATEWAY):
            return ["цепочка недоступна"]
        chain = [f"{node.kind}:{node.game_ip}"]
        if node.rootkit:
            chain.append("forged-log:10.60.0.1 (ложный след)")
        current = node
        # цепочка строится от gateway вглубь: gateway -> vpn/c2 -> mainframe
        with self._connect() as conn:
            for _ in range(16):  # защита от циклов
                row = conn.execute("SELECT * FROM nodes WHERE parent=?", (current.id,)).fetchone()
                if row is None:
                    break
                current = self._row_to_node(row)
                chain.append(f"{current.kind}:{current.game_ip}")
        return chain

    def breach(self, game_ip: str, attacker: str, *, bypass_captcha: bool = False) -> dict[str, Any]:
        node = self.by_ip(game_ip)
        if node is None or node.owner == attacker:
            return {"ok": False, "reason": "узел недоступен"}
        if node.captcha and not bypass_captcha:
            return {"ok": False, "reason": "нужен CAPTCHA-BYPASS"}
        chance = max(0.15, 0.85 - node.firewall * 0.12)
        if secrets.randbelow(1000) / 1000 > chance:
            return {"ok": False, "reason": "атака отражена файрволом"}
        with self._connect() as conn:
            conn.execute("UPDATE nodes SET owner=? WHERE id=?", (attacker, node.id))
        return {"ok": True, "node": node.id, "kind": node.kind, "ip": node.game_ip}

    def install_rootkit(self, node_id: str, owner: str) -> str:
        node = self.get_node(node_id)
        if not node or node.owner != owner:
            return "нет прав на установку руткита"
        with self._connect() as conn:
            conn.execute("UPDATE nodes SET rootkit=1 WHERE id=?", (node_id,))
        return "руткит установлен: логи врага будут подменены"

    def write_file(self, node_id: str, path: str, content: str) -> None:
        node = self.get_node(node_id)
        if not node:
            return
        node.files[path] = content
        with self._connect() as conn:
            conn.execute("UPDATE nodes SET files=? WHERE id=?", (json.dumps(node.files), node_id))

    def read_file(self, node_id: str, path: str) -> str | None:
        node = self.get_node(node_id)
        return node.files.get(path) if node else None

    def status(self, owner: str) -> str:
        with self._connect() as conn:
            rows = conn.execute("SELECT kind, game_ip, rootkit FROM nodes WHERE owner=?", (owner,)).fetchall()
        return "; ".join(f"{r['kind']}:{r['game_ip']}{' [rootkit]' if r['rootkit'] else ''}" for r in rows) or "империя не построена"
