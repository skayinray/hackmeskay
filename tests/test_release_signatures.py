import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import hackmeskay.release_key as release_key
from hackmeskay.core.updater import ReleaseInfo

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def signing_key(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    monkeypatch.setattr(release_key, "PUBLIC_KEY", private_key.public_key())
    return private_key


def signature_for(private_key, payload):
    return base64.b64encode(private_key.sign(release_key.canonical_bytes(payload))).decode("ascii")


def test_canonical_bytes_uses_sorted_compact_utf8():
    assert release_key.canonical_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode("utf-8")


def test_manifest_signature_valid(signing_key):
    payload = {"version": "0.2.0", "notes": "test release", "assets": {}}
    raw = dict(payload)
    raw["signature"] = signature_for(signing_key, payload)

    info = ReleaseInfo.parse(raw)

    assert info.version == "0.2.0"
    assert info.notes == "test release"


def test_manifest_signature_rejects_tampering(signing_key):
    payload = {"version": "0.2.0", "notes": "original", "assets": {}}
    raw = dict(payload)
    raw["signature"] = signature_for(signing_key, payload)
    raw["notes"] = "changed"

    with pytest.raises(ValueError, match="invalid Ed25519 signature"):
        ReleaseInfo.parse(raw)


def test_manifest_signature_rejects_missing_signature(signing_key):
    with pytest.raises(ValueError, match="missing a signature"):
        ReleaseInfo.parse({"version": "0.2.0", "assets": {}})


def test_manifest_signature_rejects_malformed_signature(signing_key):
    raw = {"version": "0.2.0", "assets": {}, "signature": "not-base64"}

    with pytest.raises(ValueError, match="invalid Ed25519 signature encoding"):
        ReleaseInfo.parse(raw)


def test_file_signature_valid_and_tampered(signing_key):
    data = b"artifact bytes"
    signature = base64.b64encode(signing_key.sign(data)).decode("ascii")

    release_key.verify_bytes(data, signature)
    with pytest.raises(ValueError, match="invalid Ed25519 file signature"):
        release_key.verify_bytes(b"other bytes", signature)


def load_sign_update_module():
    path = ROOT / "tools" / "sign_update.py"
    spec = importlib.util.spec_from_file_location("sign_update", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sign_update_script_signs_manifest_and_artifact(signing_key, tmp_path, monkeypatch):
    module = load_sign_update_module()
    manifest = tmp_path / "update.unsigned.json"
    manifest.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "assets": {
                    "linux": {
                        "url": "https://example.com/app.bin",
                        "filename": "app.bin",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    artifact = tmp_path / "app.bin"
    artifact.write_bytes(b"artifact bytes")
    pem = signing_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    monkeypatch.setenv("RELEASE_SIGNING_KEY", base64.b64encode(pem).decode("ascii"))
    output = tmp_path / "update.json"

    assert module.main(["--manifest", str(manifest), "--output", str(output), str(artifact)]) == 0

    signed = json.loads(output.read_text(encoding="utf-8"))
    asset = signed["assets"]["linux"]
    release_key.verify_manifest(signed)
    release_key.verify_bytes(artifact.read_bytes(), asset["signature"])
    assert asset["sha256"] == hashlib.sha256(b"artifact bytes").hexdigest()
    assert asset["size"] == len(b"artifact bytes")
    assert (tmp_path / "app.bin.sig").read_text(encoding="ascii") == asset["signature"]
