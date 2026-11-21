# Virtual vulnerabilities

These are fictional vulnerability classes in the game mesh network. They only
exist in the simulation and are used to complete missions.

| Name | Effect in the game | Countermeasure |
|---|---|---|
| `WEAK-KEY` | node has a dictionary password | `hack <node>` takes 1 to 3 attempts |
| `LOG-LEAK` | password is in a hidden log | `ls -a`, then `cat auth.log` |
| `FW-BYPASS` | firewall accepts a token | `sniff`, then `firewall --bypass <token>` |
| `GHOST-PROC` | another daemon holds a port | `hack <node>` after `connect` |
| `PLAIN-VAULT` | archive has no salt | `decrypt vault.enc` |
| `HONEY-POT` | decoy node | use `net-scan` and do not store a key there |
| `ROT-PWN` | bot changes the password every N ticks | attack right after `bot-status` |

The sandbox bot also uses `WEAK-KEY`, `ROT-PWN` and `VIRUS-PAYLOAD`, so winning
depends on speed rather than one successful hack.
