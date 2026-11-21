"""In-game knowledge base loaded from data/wiki/*.md.

Russian pages are the base set. English pages live in data/wiki/en/ and
override them when the language setting starts with "en". Missing English
pages fall back to the Russian text.
"""

from __future__ import annotations

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

EN_ALIASES = {
    "command": "commands",
    "vulnerability": "vulnerabilities",
    "mod": "mods",
    "getting-started": "getting-started",
    "getting started": "getting-started",
    "quick start": "getting-started",
    "network": "network",
    "сеть": "network",
    "empire": "empire",
    "империя": "empire",
    "rules": "commands",
}


class WikiService:
    def __init__(self, wiki_dir: Path | None = None, language: str = "en") -> None:
        self.wiki_dir = wiki_dir or (DATA_DIR / "wiki")
        self.language = "en" if language.lower().startswith("en") else "ru"
        self._cache: dict[str, str] | None = None

    def _articles(self) -> dict[str, str]:
        if self._cache is None:
            articles: dict[str, str] = {}
            if self.wiki_dir.is_dir():
                for path in sorted(self.wiki_dir.glob("*.md")):
                    articles[path.stem] = path.read_text(encoding="utf-8")
            if self.language == "en":
                english_dir = self.wiki_dir / "en"
                if english_dir.is_dir():
                    for path in sorted(english_dir.glob("*.md")):
                        articles[path.stem] = path.read_text(encoding="utf-8")
            self._cache = articles
        return self._cache

    def index(self) -> str:
        articles = self._articles()
        if self.language == "en":
            lines = ["[bold cyan]hackmeskay KNOWLEDGE BASE[/bold cyan]", "Available articles:", ""]
            lines += [f"  wiki {name:<18} {self._title(text)}" for name, text in articles.items()]
            lines += ["", "[dim]Search: wiki <word>. Example: wiki vulnerabilities[/dim]"]
        else:
            lines = ["[bold cyan]БАЗА ЗНАНИЙ hackmeskay[/bold cyan]", "Доступные статьи:", ""]
            lines += [f"  wiki {name:<18} {self._title(text)}" for name, text in articles.items()]
            lines += ["", "[dim]Поиск: wiki <слово>. Пример: wiki уязвимости[/dim]"]
        return "\n".join(lines)

    @staticmethod
    def _title(text: str) -> str:
        for line in text.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return "(no title)"

    async def article(self, query: str) -> str:
        articles = self._articles()
        needle = query.lower().strip()
        aliases = {**ALIASES, **EN_ALIASES} if self.language == "en" else ALIASES
        key = aliases.get(needle, needle)
        if key in articles:
            return articles[key]
        if needle:
            hits = [
                (name, text)
                for name, text in articles.items()
                if needle in name.lower() or needle in text.lower()
            ]
            if hits:
                name, text = hits[0]
                prefix = "[dim]found: " if self.language == "en" else "[dim]найдено: "
                return f"{prefix}{name}[/dim]\n{text}"
            if self.language == "en":
                return f"article not found: {query}\n\n{self.index()}"
            return f"статья не найдена: {query}\n\n{self.index()}"
        return self.index()
