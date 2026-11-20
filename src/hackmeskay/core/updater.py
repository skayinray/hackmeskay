"""Безопасная система обновлений.

Гарантии:
  1. Манифест обновления проверяется по схеме; версия сравнивается семантически.
  2. Бинарник качается в *.part с потоковым SHA-256 и проверкой размера.
  3. Целевой путь проверяется: запрещено писать в saves/, config/, mods/.
  4. ZIP-распаковка защищена от path traversal и тоже не трогает protected-диры.
  5. Перед заменой делается backup; при ошибке — rollback.
  6. Windows: running .exe нельзя перезаписать → отдельный detached PowerShell
     скрипт ждёт завершения процесса, меняет файл и перезапускает игру.
  7. Linux: AppImage меняется атомарным os.replace + chmod +x.

Сейвы/конфиги/моды физически лежат вне обновляемого бинарника и никогда
не попадают в архив обновления — isolation by design.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Awaitable, Callable

import aiohttp

from ..version import __version__, version_tuple
from .paths import PROTECTED_DIRS, UPDATES_DIR, is_frozen

log = logging.getLogger("hackmeskay.updater")

USER_AGENT = f"hackmeskay/{__version__} ({platform.system()} {platform.machine()})"
Progress = Callable[[int, int], Awaitable[None] | None]


class PlatformKind(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"


def current_platform() -> PlatformKind:
    return PlatformKind.WINDOWS if sys.platform == "win32" else PlatformKind.LINUX


@dataclass(slots=True)
class Asset:
    url: str
    sha256: str
    filename: str
    size: int = 0
    archive_format: str | None = None  # None = готовый бинарник, "zip" = архив

    @classmethod
    def parse(cls, raw: object) -> "Asset":
        if not isinstance(raw, dict):
            raise ValueError("asset должен быть объектом")
        url = str(raw["url"])
        if not url.startswith(("https://", "http://")):
            raise ValueError(f"небезопасный URL: {url!r}")
        return cls(
            url=url,
            sha256=str(raw.get("sha256", "")).lower(),
            filename=str(raw.get("filename") or Path(url).name),
            size=int(raw.get("size", 0)),
            archive_format=raw.get("archive_format"),
        )


@dataclass(slots=True)
class ReleaseInfo:
    version: str
    notes: str = ""
    published_at: str = ""
    assets: dict[str, Asset] = field(default_factory=dict)

    def asset_for(self, kind: PlatformKind | None = None) -> Asset | None:
        return self.assets.get((kind or current_platform()).value)

    @classmethod
    def parse(cls, raw: object) -> "ReleaseInfo":
        if not isinstance(raw, dict):
            raise ValueError(" manifest обновления должен быть объектом")
        version = str(raw["version"])
        if not version_tuple(version):
            raise ValueError(f"некорректная версия: {version!r}")
        assets = {key: Asset.parse(value) for key, value in dict(raw.get("assets", {})).items()}
        return cls(
            version=version,
            notes=str(raw.get("notes", "")),
            published_at=str(raw.get("published_at", "")),
            assets=assets,
        )


@dataclass(slots=True)
class UpdateResult:
    ok: bool
    message: str
    backup: Path | None = None
    requires_restart: bool = False


class UpdateChecker:
    def __init__(self, manifest_url: str, timeout: int = 10, cache_ttl: float = 300) -> None:
        self.manifest_url = manifest_url
        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self._cached: tuple[float, ReleaseInfo | None] | None = None

    async def check(self, force: bool = False) -> ReleaseInfo | None:
        if not force and self._cached and time.monotonic() - self._cached[0] < self.cache_ttl:
            return self._cached[1]
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                self.manifest_url,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            ) as response:
                response.raise_for_status()
                info = ReleaseInfo.parse(await response.json(content_type=None))
        available = info if version_tuple(info.version) > version_tuple(__version__) else None
        self._cached = (time.monotonic(), available)
        return available


class UpdateInstaller:
    """Скачивание, проверка и подмена бинарника."""

    def __init__(self, current_binary: Path | None = None) -> None:
        appimage = os.environ.get("APPIMAGE")
        self.current = Path(current_binary or appimage or sys.executable).resolve()
        self.downloads = UPDATES_DIR / "downloads"
        self.backups = UPDATES_DIR / "backup"
        self.pending = UPDATES_DIR / "pending"
        self.staging = UPDATES_DIR / "staging"
        self.is_source_run = not is_frozen()

    async def install(self, info: ReleaseInfo, progress: Progress | None = None) -> UpdateResult:
        kind = current_platform()
        asset = info.asset_for(kind)
        if asset is None:
            return UpdateResult(False, f"нет обновления для платформы {kind.value}")

        for directory in (self.downloads, self.backups, self.pending, self.staging):
            directory.mkdir(parents=True, exist_ok=True)

        part = self.downloads / f"{asset.filename}.part"
        try:
            await self._download(asset, part, progress)
            self._verify(part, asset)
            payload = self._extract_binary(part, asset) if asset.archive_format == "zip" else part
            target = self._resolve_target(asset, kind)
            self._assert_safe_target(target)
            self._assert_platform_suffix(target, kind)

            if self.is_source_run:
                manual = self.pending / asset.filename
                shutil.copy2(payload, manual)
                os.chmod(manual, 0o755)
                return UpdateResult(
                    True,
                    f"{info.version} скачано в {manual}. "
                    "Запуск из исходников не подменяет текущий интерпретатор.",
                )

            backup = self._backup_current(target)
            try:
                requires_restart = await self._apply(payload, target, kind, backup)
            except Exception:
                self._rollback(backup, target)
                raise
            return UpdateResult(True, f"обновлено до {info.version}", backup, requires_restart)
        except Exception as exc:
            log.exception("установка обновления прервана")
            return UpdateResult(False, f"ошибка обновления: {exc}")
        finally:
            part.unlink(missing_ok=True)

    # ---------- загрузка и проверка ----------

    async def _download(self, asset: Asset, part: Path, progress: Progress | None) -> None:
        downloaded = 0
        digest = hashlib.sha256()
        timeout = aiohttp.ClientTimeout(total=300, sock_read=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(asset.url, headers={"User-Agent": USER_AGENT}) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", asset.size or 0))
                with part.open("wb") as stream:
                    async for chunk in response.content.iter_chunked(1024 * 256):
                        if not chunk:
                            continue
                        downloaded += len(chunk)
                        if total and downloaded > total * 4:
                            raise RuntimeError("сервер передал слишком много данных")
                        digest.update(chunk)
                        stream.write(chunk)
                        if progress:
                            result = progress(downloaded, total)
                            if asyncio.iscoroutine(result):
                                await result
        if downloaded == 0:
            raise RuntimeError("пустой ответ сервера")

    def _verify(self, part: Path, asset: Asset) -> None:
        if asset.size and part.stat().st_size != asset.size:
            raise RuntimeError(f"размер не совпадает: {part.stat().st_size} != {asset.size}")
        if asset.sha256:
            checksum = hashlib.sha256()
            with part.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    checksum.update(block)
            if checksum.hexdigest() != asset.sha256:
                raise RuntimeError("SHA-256 не совпадает — обновление отклонено")
        # TODO(security): подпись ElGamal/GPG release-ключа: verify_signature(part, sig_url)

    def _extract_binary(self, archive: Path, asset: Asset) -> Path:
        """Безопасная распаковка: без `..`, без абсолютных путей, без protected-дир."""
        if not zipfile.is_zipfile(archive):
            raise RuntimeError("ожидался zip-архив")
        destination = self.staging / asset.filename.replace(".zip", "")
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                name = PurePosixPath(member.filename.replace("\\", "/"))
                if name.is_absolute() or ".." in name.parts:
                    raise RuntimeError(f"небезопасный путь в архиве: {member.filename}")
                target = (destination / Path(*name.parts)).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise RuntimeError("выход за пределы staging-директории")
                if any(target == p or p in target.parents for p in PROTECTED_DIRS):
                    raise RuntimeError("архив пытается перезаписать защищённые данные")
                zf.extract(member, destination)
        suffix = ".exe" if current_platform() is PlatformKind.WINDOWS else ".AppImage"
        binaries = [p for p in destination.rglob("*") if p.is_file() and p.name.endswith(suffix)]
        if len(binaries) != 1:
            raise RuntimeError("в архиве должен быть ровно один бинарник")
        os.chmod(binaries[0], 0o755)
        return binaries[0]

    # ---------- подмена ----------

    def _resolve_target(self, asset: Asset, kind: PlatformKind) -> Path:
        if kind is PlatformKind.WINDOWS:
            if not self.current.name.lower().endswith(".exe"):
                raise RuntimeError("текущий процесс не .exe")
            return self.current
        if not os.access(self.current, os.X_OK):
            raise RuntimeError("текущий исполняемый файл не запущенный AppImage")
        return self.current

    def _assert_safe_target(self, target: Path) -> None:
        resolved = target.resolve()
        for protected in PROTECTED_DIRS:
            root = protected.resolve()
            if resolved == root or root in resolved.parents:
                raise RuntimeError(f"отказано: цель обновления лежит в {root}")
        if not resolved.is_relative_to(UPDATES_DIR.resolve().parent):
            raise RuntimeError("цель обновления вне каталога приложения")

    @staticmethod
    def _assert_platform_suffix(target: Path, kind: PlatformKind) -> None:
        expected = ".exe" if kind is PlatformKind.WINDOWS else ".AppImage"
        if not target.name.lower().endswith(expected.lower()):
            raise RuntimeError(f"неверный тип файла для {kind.value}: ожидался {expected}")

    def _backup_current(self, target: Path) -> Path | None:
        if not target.is_file():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = self.backups / f"{stamp}-{target.stem}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / target.name
        shutil.copy2(target, backup)
        return backup

    def _rollback(self, backup: Path | None, target: Path) -> None:
        if backup and backup.is_file():
            try:
                shutil.copy2(backup, target)
                log.warning("выполнен rollback из %s", backup)
            except OSError as exc:
                log.error("не удалось откатиться: %s", exc)

    async def _apply(self, payload: Path, target: Path, kind: PlatformKind, backup: Path | None) -> bool:
        if kind is PlatformKind.LINUX:
            os.replace(payload, target)
            os.chmod(target, 0o755)
            return False  # можно продолжать в текущем процессе

        # Windows: подменяем через отдельный процесс после выхода игры
        staged = self.pending / payload.name
        shutil.copy2(payload, staged)
        script = self._write_windows_helper()
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
                "-PidToWait",
                str(os.getpid()),
                "-Source",
                str(staged),
                "-Target",
                str(target),
            ],
            creationflags=flags,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
        return True

    def _write_windows_helper(self) -> Path:
        script = self.pending / "apply_update.ps1"
        script.write_text(
            r"""
param([int]$PidToWait, [string]$Source, [string]$Target)
$ErrorActionPreference = 'Stop'
$deadline = (Get-Date).AddSeconds(60)
while (Get-Process -Id $PidToWait -ErrorAction SilentlyContinue) {
    if ((Get-Date) -gt $deadline) { exit 1 }
    Start-Sleep -Milliseconds 200
}
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = "$Target.$stamp.bak"
if (Test-Path -LiteralPath $Target) {
    Copy-Item -LiteralPath $Target -Destination $backup -Force
}
Move-Item -LiteralPath $Source -Destination $Target -Force
Start-Process -FilePath $Target
""",
            encoding="utf-8",
        )
        return script


class UpdateManager:
    """Фасад для движка: `update check` / `update install`."""

    def __init__(self, manifest_url: str, settings_store: object | None = None) -> None:
        self.checker = UpdateChecker(manifest_url)
        self.installer = UpdateInstaller()
        self.settings_store = settings_store

    async def check(self, force: bool = False) -> str:
        try:
            release = await self.checker.check(force=force)
        except aiohttp.ClientError as exc:
            log.warning("проверка обновлений не удалась: %s", exc)
            return f"[red]не удалось проверить обновления: {exc}[/red]"
        except Exception as exc:
            log.exception("ошибка проверки обновлений")
            return f"[red]ошибка проверки обновлений: {exc}[/red]"
        if release is None:
            return f"актуальная версия: {__version__}"
        return (
            f"[yellow]доступно обновление {release.version}[/yellow] "
            f"(текущая {__version__})\n{release.notes}"
        )

    async def install(self, progress: Progress | None = None) -> str:
        try:
            release = await self.checker.check()
        except aiohttp.ClientError as exc:
            log.warning("проверка обновлений не удалась: %s", exc)
            return f"[red]не удалось проверить обновления: {exc}[/red]"
        except Exception as exc:
            log.exception("ошибка проверки обновлений")
            return f"[red]ошибка проверки обновлений: {exc}[/red]"
        if release is None:
            return f"обновление не требуется ({__version__})"
        result = await self.installer.install(release, progress)
        if result.ok and result.requires_restart:
            return result.message + "\nигра закроется — новая версия запустится сама"
        return result.message
