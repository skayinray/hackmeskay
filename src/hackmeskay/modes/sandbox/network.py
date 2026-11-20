"""Виртуальная сеть песочницы (полностью симулированная)."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


@dataclass
class Node:
    id: str
    ip: str
    password: str
    firewall: int
    owner: str = "neutral"
    discovered: bool = False
    infected: bool = False
    breached: bool = False


class VirtualNetwork:
    def __init__(self, seed: int = 1337, size: int = 10) -> None:
        self.rng = random.Random(seed)
        words = ["swordfish", "dragon", "shadow", "neon", "cipher", "zero", "echo", "nova", "ghost", "flux"]
        self.nodes: dict[str, Node] = {
            f"node-{i:02d}": Node(
                id=f"node-{i:02d}",
                ip=f"10.13.{i // 8}.{10 + i}",
                password=self.rng.choice(words),
                firewall=self.rng.randint(1, 5),
            )
            for i in range(size)
        }
        self.nodes["bot-core"] = Node("bot-core", "10.13.99.1", "rootkit", 5, owner="bot")

    def scan(self, actor: str = "player") -> list[Node]:
        for node in self.nodes.values():
            if actor == "bot" or self.rng.random() > 0.25:
                node.discovered = True
        return [n for n in self.nodes.values() if n.discovered]

    def connect(self, node_id: str, password: str) -> bool:
        node = self.nodes.get(node_id)
        if not node or password != node.password:
            return False
        node.breached = True
        return True

    def brute(self, node_id: str, actor: str = "player") -> bool:
        node = self.nodes.get(node_id)
        if not node:
            return False
        success = self.rng.random() > min(0.85, 0.25 + node.firewall * 0.12)
        node.breached = success
        node.owner = actor if success else node.owner
        return success

    def rotate_password(self, node_id: str) -> str:
        node = self.nodes[node_id]
        node.password = f"rot-{self.rng.randint(1000, 9999)}"
        node.breached = False
        return node.password

    def infect(self, node_id: str) -> None:
        self.nodes[node_id].infected = True

    def clean(self, node_id: str) -> bool:
        node = self.nodes.get(node_id)
        if node and node.infected:
            node.infected = False
            return True
        return False

    def stats(self) -> dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "player": sum(n.owner == "player" for n in self.nodes.values()),
            "bot": sum(n.owner == "bot" for n in self.nodes.values()),
            "infected": sum(n.infected for n in self.nodes.values()),
        }
