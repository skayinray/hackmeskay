import base64
import hashlib
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import hackmeskay.release_key as release_key
from hackmeskay.core import updater
from hackmeskay.core.config import DEFAULT_UPDATE_URL
from hackmeskay.core.updater import Asset, UpdateChecker, UpdateInstaller

HTTPS_URL = "https://example.com/app.bin"


@pytest.fixture
def signing_key(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(release_key, "PUBLIC_KEY", private_key.public_key())
    return private_key


def make_asset(part: Path, signing_key, *, with_signature: bool = True) -> Asset:
    data = part.read_bytes()
    raw = {
        "url": HTTPS_URL,
        "sha256": hashlib.sha256(data).hexdigest(),
        "filename": part.name,
        "size": len(data),
    }
    if with_signature:
        raw["signature"] = base64.b64encode(signing_key.sign(data)).decode("ascii")
    return Asset.parse(raw)


def test_asset_parse_rejects_plain_http():
    with pytest.raises(ValueError, match="HTTPS"):
        Asset.parse({"url": "http://example.com/app.bin", "sha256": "0" * 64})


def test_asset_parse_requires_checksum():
    with pytest.raises(ValueError, match="sha256"):
        Asset.parse({"url": HTTPS_URL})


def test_default_manifest_url_uses_github_releases():
    assert DEFAULT_UPDATE_URL == (
        "https://github.com/skayinray/hackmeskay/releases/latest/download/update.json"
    )


def test_checker_rejects_plain_http_manifest_url():
    with pytest.raises(ValueError, match="HTTPS"):
        UpdateChecker("http://example.com/update.json")


def test_verify_accepts_signed_asset(tmp_path, signing_key):
    part = tmp_path / "app.bin"
    part.write_bytes(b"good bytes")
    installer = UpdateInstaller(current_binary=tmp_path / "fake.AppImage")

    installer._verify(part, make_asset(part, signing_key))


def test_verify_rejects_tampered_file(tmp_path, signing_key):
    part = tmp_path / "app.bin"
    part.write_bytes(b"good bytes")
    asset = make_asset(part, signing_key)
    part.write_bytes(b"bad bytezz")
    installer = UpdateInstaller(current_binary=tmp_path / "fake.AppImage")

    with pytest.raises(ValueError, match="SHA-256"):
        installer._verify(part, asset)


def test_verify_requires_asset_signature(tmp_path, signing_key):
    part = tmp_path / "app.bin"
    part.write_bytes(b"good bytes")
    installer = UpdateInstaller(current_binary=tmp_path / "fake.AppImage")

    with pytest.raises(ValueError, match="missing an Ed25519 signature"):
        installer._verify(part, make_asset(part, signing_key, with_signature=False))


def test_verify_rejects_invalid_asset_signature(tmp_path, signing_key):
    part = tmp_path / "app.bin"
    part.write_bytes(b"good bytes")
    raw = {
        "url": HTTPS_URL,
        "sha256": hashlib.sha256(b"good bytes").hexdigest(),
        "filename": part.name,
        "size": len(b"good bytes"),
        "signature": base64.b64encode(b"x" * 64).decode("ascii"),
    }
    installer = UpdateInstaller(current_binary=tmp_path / "fake.AppImage")

    with pytest.raises(ValueError, match="invalid Ed25519 file signature"):
        installer._verify(part, Asset.parse(raw))


def test_zip_traversal_is_rejected(tmp_path, monkeypatch):
    archive = tmp_path / "app.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../evil.txt", "bad")
    protected = tmp_path / "protected"
    protected.mkdir()
    monkeypatch.setattr(updater, "PROTECTED_DIRS", (protected,))
    installer = UpdateInstaller(current_binary=tmp_path / "fake.AppImage")
    installer.staging = tmp_path / "staging"
    asset = Asset(url=HTTPS_URL, sha256="0" * 64, filename="app.zip")

    with pytest.raises(RuntimeError):
        installer._extract_binary(archive, asset)
