"""In-game база знаний: загружается из data/wiki/*.md, ищет по заголовкам и тексту."""

from __future__ import annotations

import re
from pathlib import Path

from ..core.paths import DATA_DIR

ALIASES = {
    "commands": "commands",
    "команды": "commands",
    "vulnerabilities": "vulnerabilities",
    "уязвимости": "vulnerabilities",
    "mods": "mods",
    "моды": "mods",
    "lore": "lore",
    "лор": "lore",
    "start": "getting-started",
    "старт": "getting-started",
}


class WikiService:
    def __init__(self, wiki_dir: Path | None = None) -> None:
        self.wiki_dir = wiki_dir or (DATA_DIR / "wiki")
        self._cache: dict[str, str] | None = None

    def _articles(self) -> dict[str, str]:
        if self._cache is None:
            self._cache = {}
            if self.wiki_dir.is_dir():
                for path in sorted(self.wiki_dir.glob("*.md")):
                    self._cache[path.stem] = path.read_text(encoding="utf-8")
        return self._cache

    def index(self) -> str:
        articles = self._articles()
        lines = ["[bold cyan]БАЗА ЗНАНИЙ hackmeskay[/bold cyan]", "Доступные статьи:", ""]
        lines += [f"  wiki {name:<18} {self._title(text)}" for name, text in articles.items()]
        lines += ["", "[dim]Поиск: wiki <слово>. Пример: wiki уязвимости[/dim]"]
        return "\n".join(lines)

    @staticmethod
    def _title(text: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return "(без заголовка)"

    async def article(self, query: str) -> str:
        articles = self._articles()
        key = ALIASES.get(query.lower().strip(), query.lower().strip())
        if key in articles:
            return articles[key]
        needle = query.lower().strip()
        if needle:
            hits = [
                (name, text)
                for name, text in articles.items()
                if needle in name.lower() or needle in text.lower()
            ]
            if hits:
                name, text = hits[0]
                return f"[dim]найдено: {name}[/dim]\n{text}"
            return f"статья не найдена: {query}\n\n{self.index()}"
        return self.index()
