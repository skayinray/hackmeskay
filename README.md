# hackmeskay

A terminal game about a fictional mesh network. All scanning, hacking and
network play happens inside the game. The project does not provide real attack
tools. It runs on Linux and Windows.

## Run from source

```bash
cd hackmeskay
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export PYTHONPATH=src            # Windows: $env:PYTHONPATH="src"
python -m hackmeskay
```

The default wiki language is `en`. Set `language` to `ru` in
`config/settings.json` to switch back to the original Russian pages.

## Commands

Global: `help`, `wiki [topic]`, `mod list|enable|disable|reload <name>`,
`update check|install`, `mode menu|tutorial|campaign|sandbox`, `save`, `quit`.

Network: `network`, `host [port]`, `join <IP> [port]`, `id`, `peers`,
`msg <MessengerID> <text>`, `leave`. Most commands also accept a leading `/`.

Empire: `empire build|status|rootkit`, `/scan <game-ip>`, `/trace <game-ip>`,
`breach <game-ip> [--captcha]`. These commands use a local SQLite model and do
not send requests to the given IP addresses.

Menu: `play`, `tutorial`, `campaign [n]`, `sandbox [1-5]`.
Campaign: `mission list|start <n>|status|abort`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Build

```bash
# Windows
powershell -ExecutionPolicy Bypass -File build/build_windows.ps1

# Linux (needs appimagetool in PATH or APPIMAGETOOL set)
bash build/build_linux.sh
```

Binaries are written to `dist/`. The build scripts call PyInstaller with
`--add-data data:data`. The checked-in spec files are kept for reference; the
Windows spec contains absolute paths from a developer machine, so CI uses the
scripts. macOS builds are a manual step and are not published by CI.

## Updates

The client reads a signed manifest from
`https://github.com/skayinray/hackmeskay/releases/latest/download/update.json`.
The default is set in `core/config.py`. Existing `config/settings.json` files
keep their saved `update_url`, so set it to the URL above if it still points to
the old raw file.

An update is accepted only when the manifest Ed25519 signature, each asset
signature, the SHA-256 checksum and the size all match. Asset URLs must use
HTTPS. Saves, config, mods and history stay next to the binary and are never
replaced by an update. `deploy/update.json.example` shows the manifest format.

To build a release manifest, populate an unsigned template and run:

```bash
RELEASE_SIGNING_KEY="<base64 PKCS8 Ed25519 private key>" \
  python tools/sign_update.py --manifest update.unsigned.json --output update.json \
  dist/hackmeskay.exe dist/hackmeskay-x86_64.AppImage
```

The script writes `update.json` and a `.sig` file next to each artifact. See
`SECURITY.md` for the trust model and vulnerability reporting.
