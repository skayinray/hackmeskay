"""Ed25519 release signature helpers shared by the client and release scripts.

The client only knows the public key. Signing is done in CI with the private
key stored in the RELEASE_SIGNING_KEY repository secret.
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# Raw Ed25519 public key, base64 encoded.
PUBLIC_KEY_BASE64 = "PgMGi9d7BTVYQy3G5UsL+yNn9ldbkrj1RBrThDA46Fc="
PUBLIC_KEY = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_BASE64))


def canonical_bytes(payload: Mapping[str, Any]) -> bytes:
    """Return the exact byte sequence covered by a manifest signature."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def decode_signature(signature: object) -> bytes:
    """Decode one base64 Ed25519 signature, or raise a clear ValueError."""
    if not isinstance(signature, str) or not signature.strip():
        raise ValueError("missing Ed25519 signature")
    try:
        raw = base64.b64decode(signature.strip(), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid Ed25519 signature encoding") from exc
    if len(raw) != 64:
        raise ValueError(f"invalid Ed25519 signature length: {len(raw)}")
    return raw


def verify_signature(payload: Mapping[str, Any], signature: object) -> None:
    """Verify a signature over canonical JSON. Raise ValueError on failure."""
    try:
        PUBLIC_KEY.verify(decode_signature(signature), canonical_bytes(payload))
    except InvalidSignature as exc:
        raise ValueError("invalid Ed25519 signature") from exc


def verify_bytes(data: bytes, signature: object) -> None:
    """Verify a signature over raw file bytes. Raise ValueError on failure."""
    try:
        PUBLIC_KEY.verify(decode_signature(signature), data)
    except InvalidSignature as exc:
        raise ValueError("invalid Ed25519 file signature") from exc


def verify_manifest(raw: object) -> dict[str, Any]:
    """Verify a release manifest and return its signed payload.

    The ``signature`` field is the only field excluded from the signed bytes.
    """
    if not isinstance(raw, dict):
        raise ValueError("update manifest must be a JSON object")
    signature = raw.get("signature")
    if not signature:
        raise ValueError("update manifest is missing a signature")
    payload = {key: value for key, value in raw.items() if key != "signature"}
    verify_signature(payload, signature)
    return payload
