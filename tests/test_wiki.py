import asyncio
from pathlib import Path

import pytest

from hackmeskay.services.wiki import WikiService

EXPECTED_ENGLISH_PAGES = {
    "commands",
    "empire",
    "getting-started",
    "lore",
    "mods",
    "network",
    "vulnerabilities",
}


@pytest.fixture
def wiki_dir(tmp_path):
    (tmp_path / "commands.md").write_text("# Команды\nRU COMMANDS", encoding="utf-8")
    (tmp_path / "getting-started.md").write_text("# Старт\nRU START", encoding="utf-8")
    english = tmp_path / "en"
    english.mkdir()
    (english / "commands.md").write_text("# Commands\nEN COMMANDS", encoding="utf-8")
    return tmp_path


def test_english_locale_prefers_english_pages(wiki_dir):
    wiki = WikiService(wiki_dir=wiki_dir, language="en")

    assert "EN COMMANDS" in asyncio.run(wiki.article("commands"))
    assert "RU START" in asyncio.run(wiki.article("start"))
    assert "Available articles" in wiki.index()


def test_russian_locale_uses_base_pages(wiki_dir):
    wiki = WikiService(wiki_dir=wiki_dir, language="ru")

    assert "RU COMMANDS" in asyncio.run(wiki.article("commands"))
    assert "EN COMMANDS" not in asyncio.run(wiki.article("commands"))


def test_english_wiki_files_exist():
    wiki_dir = Path(__file__).resolve().parents[1] / "data" / "wiki" / "en"
    pages = {path.stem for path in wiki_dir.glob("*.md")}

    assert EXPECTED_ENGLISH_PAGES <= pages
