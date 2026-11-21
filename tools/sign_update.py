"""Sign a release manifest and its artifacts with the release Ed25519 key.

Usage:
    RELEASE_SIGNING_KEY="<base64 PKCS8 PEM>" python tools/sign_update.py \
        --manifest update.unsigned.json --output update.json FILE [FILE ...]
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hackmeskay.release_key import canonical_bytes  # noqa: E402


def load_private_key(env_name: str = "RELEASE_SIGNING_KEY") -> Ed25519PrivateKey:
    """Read a base64 encoded PKCS8 PEM Ed25519 private key from the environment."""
    encoded = os.environ.get(env_name, "").strip()
    if not encoded:
        raise ValueError(f"{env_name} is not set")
    try:
        pem = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{env_name} is not valid base64") from exc
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError(f"{env_name} must contain an Ed25519 private key")
    return key


def load_unsigned_manifest(path: Path) -> dict[str, Any]:
    """Load a manifest that has no real signature yet."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest must be a JSON object")
    signature = raw.pop("signature", None)
    if signature and not str(signature).startswith("BASE64_"):
        raise ValueError("manifest already has a signature")
    return raw


def sign_file(path: Path, key: Ed25519PrivateKey) -> dict[str, str | int]:
    """Write <path>.sig and return checksum, size and signature for the asset."""
    data = path.read_bytes()
    signature = base64.b64encode(key.sign(data)).decode("ascii")
    Path(str(path) + ".sig").write_text(signature, encoding="ascii")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "signature": signature,
    }


def build_signed_manifest(
    manifest_path: Path, artifacts: list[Path], key: Ed25519PrivateKey
) -> dict[str, Any]:
    """Fill in asset details and add the canonical manifest signature."""
    payload = load_unsigned_manifest(manifest_path)
    assets = payload.get("assets", {})
    for artifact in artifacts:
        details = sign_file(artifact, key)
        matched = False
        for asset in assets.values() if isinstance(assets, dict) else []:
            if not isinstance(asset, dict):
                continue
            if Path(str(asset.get("filename", ""))).name == artifact.name:
                asset.update(details)
                matched = True
        if not matched:
            print(f"warning: no manifest asset matches {artifact.name}", file=sys.stderr)
    payload["signature"] = base64.b64encode(key.sign(canonical_bytes(payload))).decode("ascii")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="unsigned manifest JSON")
    parser.add_argument("--output", type=Path, help="output manifest (default: update.json)")
    parser.add_argument("--key-env", default="RELEASE_SIGNING_KEY", help="private key env name")
    parser.add_argument("artifacts", nargs="*", type=Path, help="files to sign into *.sig")
    args = parser.parse_args(argv)

    try:
        key = load_private_key(args.key_env)
        signed = build_signed_manifest(args.manifest, args.artifacts, key)
        output = args.output or args.manifest.with_name("update.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(signed, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
