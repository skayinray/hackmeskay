# Security policy

## Update trust model

Release updates are signed with an Ed25519 key. The client embeds only the
public key (`src/hackmeskay/release_key.py`).

The release manifest is signed over every field except `signature`, using
canonical JSON (sorted keys, compact separators, UTF-8). The updater also
requires a SHA-256 checksum, a size, and a base64 Ed25519 signature for each
asset. The asset signature covers the downloaded file bytes. URLs must use
HTTPS. A missing, malformed or invalid signature stops the update with a clear
error.

A valid signature means the file was signed with the release key. It does not
mean the binary has no bugs. `tools/sign_update.py` is the only supported way
to create a manifest and artifact `.sig` files, and it reads the private key
from the `RELEASE_SIGNING_KEY` environment variable.

## Reporting a vulnerability

Please use the private vulnerability reporting form on the repository Security
tab: https://github.com/skayinray/hackmeskay/security/advisories/new

If private reporting is not available, open an issue with a short description
and ask for a private contact. Do not publish working exploit steps in a public
issue. Include the game version, platform, and the command or input that
triggered the problem.
