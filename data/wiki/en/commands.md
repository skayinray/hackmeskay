# Command syntax

Type commands in lower case and separate arguments with spaces. Quoting is
supported, for example `connect "node 01"`.

## Global commands

| Command | Purpose |
|---|---|
| `help [topic]` | list commands or open a help topic |
| `wiki [topic]` | open the knowledge base |
| `mod list\|enable\|disable\|reload <name>` | manage mods |
| `update check\|install` | check for or install updates |
| `mode <name>` | switch directly to another mode |
| `save` / `quit` | save progress / exit |

## Commands in game modes

- `ls [-a]` lists files, with `-a` showing hidden files.
- `cd <path>` changes the current directory.
- `net-scan` discovers nodes on the virtual network.
- `connect <node> [password]` opens a session.
- `hack <node> [--brute|--swarm]` guesses a node key.
- `sniff`, `firewall --bypass <token>`, `proxy`, `decrypt <file>` are used in
  the campaign.
- `virus-clean <node>`, `bot-status` are used in the sandbox.
